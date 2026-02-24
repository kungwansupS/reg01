"""
TTS Module — edge-tts v7.x
สังเคราะห์เสียงพูดจากข้อความ ผ่าน Microsoft Edge Online TTS

สถาปัตยกรรม:
  1. speak()          — public async generator, yield MP3 chunks ทีละก้อน (true streaming)
  2. _stream_segment  — สร้าง Communicate instance ต่อ segment, stream audio chunks
  3. _with_retry      — retry + exponential backoff ต่อ segment
  4. Circuit Breaker  — ปิด TTS ชั่วคราวเมื่อ network error ต่อเนื่อง
  5. Language Split    — แยกข้อความตามภาษา → เลือก voice ที่เหมาะสม

Public API (ใช้โดย chat_router.py):
  - speak(text)         → AsyncGenerator[bytes, None]
  - is_tts_available()  → bool
"""

import re
import sys
import asyncio
import logging
import os
import time
from collections import deque
from typing import AsyncGenerator, List, Tuple, Optional

import aiohttp
import edge_tts

logger = logging.getLogger(__name__)

# Windows + WindowsSelectorEventLoopPolicy ทำให้ aiohttp async DNS resolver ล้มเหลว
# แก้โดยใช้ ThreadedResolver (resolve DNS ผ่าน thread แทน) + dns_cache
_WIN32 = sys.platform.startswith("win")


# ----------------------------------------------------------------------------- #
# ENVIRONMENT HELPERS
# ----------------------------------------------------------------------------- #
def _env_bool(name: str, default: str = "true") -> bool:
    return str(os.getenv(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: str) -> int:
    try:
        return int(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        return int(default)


# ----------------------------------------------------------------------------- #
# CONFIGURATION
# ----------------------------------------------------------------------------- #
TTS_ENABLED = _env_bool("TTS_ENABLED", "true")
TTS_DISABLE_ON_NETWORK_ERROR = _env_bool("TTS_DISABLE_ON_NETWORK_ERROR", "true")
TTS_NETWORK_ERROR_COOLDOWN_SECONDS = max(15, _env_int("TTS_NETWORK_ERROR_COOLDOWN_SECONDS", "60"))
TTS_NETWORK_ERROR_DISABLE_THRESHOLD = max(1, _env_int("TTS_NETWORK_ERROR_DISABLE_THRESHOLD", "2"))
TTS_SEGMENT_TIMEOUT_SECONDS = max(5, _env_int("TTS_SEGMENT_TIMEOUT_SECONDS", "15"))
TTS_MAX_RETRIES = max(0, _env_int("TTS_MAX_RETRIES", "2"))
TTS_CONNECT_TIMEOUT = max(3, _env_int("TTS_CONNECT_TIMEOUT", "10"))
TTS_RECEIVE_TIMEOUT = max(5, _env_int("TTS_RECEIVE_TIMEOUT", "60"))

# Minimal valid MP3 silence frame (~26ms, MPEG1 Layer3)
# ใช้คั่นระหว่าง parts แทน raw null bytes ที่ทำให้ MP3 decoder เสีย
_MP3_SILENCE_FRAME = (
    b'\xff\xfb\x90\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00Info\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
)


# ----------------------------------------------------------------------------- #
# VOICE SETTINGS PER LANGUAGE
# ----------------------------------------------------------------------------- #
LANGUAGE_SETTINGS = {
    "th": {
        "voice": os.getenv("TTS_VOICE_TH", "th-TH-NiwatNeural"),
        "rate": os.getenv("TTS_RATE_TH", "+0%"),
        "volume": os.getenv("TTS_VOLUME_TH", "+5%"),
        "pitch": os.getenv("TTS_PITCH_TH", "+0Hz"),
    },
    "en": {
        "voice": os.getenv("TTS_VOICE_EN", "en-US-GuyNeural"),
        "rate": os.getenv("TTS_RATE_EN", "-10%"),
        "volume": os.getenv("TTS_VOLUME_EN", "+3%"),
        "pitch": os.getenv("TTS_PITCH_EN", "+0Hz"),
    },
    "zh": {
        "voice": os.getenv("TTS_VOICE_ZH", "zh-CN-YunxiNeural"),
        "rate": os.getenv("TTS_RATE_ZH", "-20%"),
        "volume": os.getenv("TTS_VOLUME_ZH", "+5%"),
        "pitch": os.getenv("TTS_PITCH_ZH", "-20Hz"),
    },
    "ja": {
        "voice": os.getenv("TTS_VOICE_JA", "ja-JP-KeitaNeural"),
        "rate": os.getenv("TTS_RATE_JA", "-10%"),
        "volume": os.getenv("TTS_VOLUME_JA", "+5%"),
        "pitch": os.getenv("TTS_PITCH_JA", "+0Hz"),
    },
}


# ----------------------------------------------------------------------------- #
# CIRCUIT BREAKER STATE
# ----------------------------------------------------------------------------- #
_tts_disabled_until: float = 0.0
_tts_last_skip_log_ts: float = 0.0
_tts_last_disable_reason: str = ""
_tts_consecutive_network_errors: int = 0


def _is_tts_temporarily_disabled() -> bool:
    return _tts_disabled_until > time.time()


def _mark_tts_temporarily_disabled(reason: str) -> None:
    global _tts_disabled_until, _tts_last_disable_reason
    _tts_disabled_until = time.time() + float(TTS_NETWORK_ERROR_COOLDOWN_SECONDS)
    _tts_last_disable_reason = str(reason or "").strip()


def _log_tts_skip_once(message: str) -> None:
    global _tts_last_skip_log_ts
    now_ts = time.time()
    if now_ts - _tts_last_skip_log_ts >= 15:
        logger.warning(message)
        _tts_last_skip_log_ts = now_ts


def is_tts_available() -> bool:
    """ตรวจสอบว่า TTS พร้อมใช้งานหรือไม่"""
    if not TTS_ENABLED:
        return False
    return not _is_tts_temporarily_disabled()


# ----------------------------------------------------------------------------- #
# NETWORK ERROR DETECTION
# ----------------------------------------------------------------------------- #
def _collect_exception_message(exc: BaseException) -> str:
    """รวบรวม error message จาก exception chain ทั้งหมด"""
    queue: deque = deque([exc])
    visited: set = set()
    parts: list = []
    while queue:
        current = queue.popleft()
        if not current:
            continue
        cid = id(current)
        if cid in visited:
            continue
        visited.add(cid)
        text = str(current).strip()
        if text:
            parts.append(text)
        for nested in (
            getattr(current, "__cause__", None),
            getattr(current, "__context__", None),
            getattr(current, "os_error", None),
        ):
            if isinstance(nested, BaseException):
                queue.append(nested)
    return " | ".join(parts)


def _is_network_error(exc: BaseException) -> bool:
    """ตรวจสอบว่า exception เกิดจาก network/DNS error หรือไม่"""
    raw = _collect_exception_message(exc).lower()
    norm = re.sub(r"[^a-z0-9]+", " ", raw).strip()

    dns_signatures = [
        "temporary failure in name resolution",
        "name or service not known",
        "nodename nor servname provided",
        "getaddrinfo failed",
        "no address associated with hostname",
        "could not resolve host",
    ]
    if any(sig in raw for sig in dns_signatures):
        return True

    # aiohttp connection errors
    conn_signatures = [
        "cannot connect to host",
        "connection refused",
        "connection reset",
        "server disconnected",
        "client connector error",
    ]
    if any(sig in raw for sig in conn_signatures):
        return True

    # DNS-specific patterns
    if "dns" in norm:
        return True
    if "could not contact" in norm and "dns server" in norm:
        return True

    return False


def _is_retryable_error(exc: BaseException) -> bool:
    """ตรวจสอบว่า error สามารถ retry ได้หรือไม่"""
    if _is_network_error(exc):
        return True
    # edge-tts v7 specific: WebSocketError, NoAudioReceived อาจเกิดจาก transient issue
    exc_name = type(exc).__name__
    if exc_name in ("WebSocketError", "NoAudioReceived", "UnexpectedResponse"):
        return True
    if isinstance(exc, (asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    return False


def _record_network_error(exc: BaseException) -> None:
    """บันทึก network error และเปิด circuit breaker ถ้าเกิน threshold"""
    global _tts_consecutive_network_errors
    if not TTS_DISABLE_ON_NETWORK_ERROR:
        return
    if not _is_network_error(exc):
        return

    _tts_consecutive_network_errors += 1
    if _tts_consecutive_network_errors >= TTS_NETWORK_ERROR_DISABLE_THRESHOLD:
        _mark_tts_temporarily_disabled(str(exc))
        logger.warning(
            "TTS temporarily disabled for %ss after %d consecutive network errors: %s",
            TTS_NETWORK_ERROR_COOLDOWN_SECONDS,
            _tts_consecutive_network_errors,
            exc,
        )


def _reset_network_error_counter() -> None:
    """รีเซ็ต counter เมื่อ TTS สำเร็จ"""
    global _tts_consecutive_network_errors
    _tts_consecutive_network_errors = 0


# ----------------------------------------------------------------------------- #
# CORE: STREAM A SINGLE SEGMENT (edge-tts v7)
# ----------------------------------------------------------------------------- #
async def _stream_segment(
    text: str, settings: dict
) -> AsyncGenerator[bytes, None]:
    """
    สร้าง edge_tts.Communicate instance และ stream audio chunks

    edge-tts v7 API:
      - Communicate(text, voice, *, rate, volume, pitch, connect_timeout, receive_timeout)
      - stream() → AsyncGenerator ที่ yield {"type": "audio", "data": bytes} (เรียกได้ครั้งเดียว)
      - output format: audio-24khz-48kbitrate-mono-mp3

    Args:
        text: ข้อความที่ต้องการแปลง
        settings: dict ที่มี voice, rate, volume, pitch

    Yields:
        bytes: MP3 audio data chunks
    """
    connector = None
    if _WIN32:
        resolver = aiohttp.ThreadedResolver()
        connector = aiohttp.TCPConnector(resolver=resolver, use_dns_cache=True)

    communicate = edge_tts.Communicate(
        text=text,
        voice=settings["voice"],
        rate=settings["rate"],
        volume=settings["volume"],
        pitch=settings["pitch"],
        connect_timeout=TTS_CONNECT_TIMEOUT,
        receive_timeout=TTS_RECEIVE_TIMEOUT,
        connector=connector,
    )

    async for chunk in communicate.stream():
        if chunk["type"] == "audio" and chunk["data"]:
            yield chunk["data"]


async def _stream_segment_with_retry(
    text: str, settings: dict
) -> AsyncGenerator[bytes, None]:
    """
    Stream segment พร้อม retry + exponential backoff

    ถ้า segment ล้มเหลว จะ retry สูงสุด TTS_MAX_RETRIES ครั้ง
    โดยรอ 0.5s, 1.0s, 2.0s, ... ระหว่าง retry
    ถ้า circuit breaker เปิด จะหยุดทันที

    Yields:
        bytes: MP3 audio data chunks
    """
    last_exc: Optional[BaseException] = None

    for attempt in range(1 + TTS_MAX_RETRIES):
        if _is_tts_temporarily_disabled():
            return

        try:
            chunk_count = 0
            async for audio_data in _stream_segment(text, settings):
                chunk_count += 1
                yield audio_data

            if chunk_count > 0:
                _reset_network_error_counter()
                return
            else:
                # stream สำเร็จแต่ไม่มี audio data
                logger.warning(
                    "TTS segment returned no audio (attempt %d/%d): '%s...'",
                    attempt + 1, 1 + TTS_MAX_RETRIES, text[:40],
                )
                last_exc = RuntimeError("No audio data received")

        except Exception as exc:
            last_exc = exc
            _record_network_error(exc)

            if _is_tts_temporarily_disabled():
                return

            if not _is_retryable_error(exc):
                logger.error("TTS non-retryable error: %s", exc)
                return

            logger.warning(
                "TTS error (attempt %d/%d): %s",
                attempt + 1, 1 + TTS_MAX_RETRIES, exc,
            )

        # Exponential backoff ก่อน retry
        if attempt < TTS_MAX_RETRIES:
            backoff = min(0.5 * (2 ** attempt), 4.0)
            await asyncio.sleep(backoff)

    # ทุก attempt ล้มเหลว
    if last_exc:
        logger.error(
            "TTS segment failed after %d attempts for '%s...': %s",
            1 + TTS_MAX_RETRIES, text[:40], last_exc,
        )


# ----------------------------------------------------------------------------- #
# PUBLIC API: speak()
# ----------------------------------------------------------------------------- #
async def speak(text: str) -> AsyncGenerator[bytes, None]:
    """
    แปลงข้อความเป็นเสียงพูด รองรับหลายภาษาและ true streaming

    Args:
        text: ข้อความที่ต้องการแปลงเป็นเสียง

    Yields:
        bytes: Audio data chunks (MP3 format, 24kHz 48kbps mono)

    Example:
        >>> async for chunk in speak("สวัสดีครับ // Hello"):
        ...     # ส่ง chunk ไปยัง client
    """
    if not TTS_ENABLED:
        _log_tts_skip_once("TTS disabled by configuration (TTS_ENABLED=false).")
        return

    if _is_tts_temporarily_disabled():
        remaining = max(0, int(_tts_disabled_until - time.time()))
        reason = _tts_last_disable_reason or "network error"
        _log_tts_skip_once(f"TTS temporarily unavailable ({remaining}s left): {reason}")
        return

    if not text or not text.strip():
        logger.warning("Empty text provided to TTS")
        return

    try:
        # ทำความสะอาดข้อความ
        text = preprocess_text(text)

        # แยกส่วนตาม // delimiter
        parts = [p.strip() for p in text.split("//") if p.strip()]

        if not parts:
            logger.warning("No valid parts after preprocessing")
            return

        logger.info("TTS speaking %d part(s)", len(parts))

        # ประมวลผลแต่ละส่วน
        for i, part in enumerate(parts):
            # แบ่งตามภาษา
            segments = split_text_by_language(part)

            logger.debug("Part %d/%d: %d language segments", i + 1, len(parts), len(segments))

            # พูดแต่ละ segment — true streaming (yield ทีละ chunk)
            for lang, segment_text in segments:
                if not segment_text.strip():
                    continue

                settings = LANGUAGE_SETTINGS.get(lang, LANGUAGE_SETTINGS["th"])

                async for audio_chunk in _stream_segment_with_retry(segment_text, settings):
                    yield audio_chunk

                # ถ้า circuit breaker เปิด ให้หยุดทันที
                if _is_tts_temporarily_disabled():
                    return

            # เว้นช่วงเล็กน้อยระหว่าง parts (ถ้ามีหลาย parts)
            if i < len(parts) - 1:
                yield _MP3_SILENCE_FRAME

        logger.info("TTS completed successfully")

    except Exception as e:
        logger.error(f"Critical TTS Error: {e}")
        return


# ----------------------------------------------------------------------------- #
# TEXT PREPROCESSING
# ----------------------------------------------------------------------------- #
def preprocess_text(text: str) -> str:
    """
    ทำความสะอาดและปรับปรุงข้อความก่อนแปลงเป็นเสียง

    Args:
        text: ข้อความต้นฉบับ

    Returns:
        str: ข้อความที่ปรับปรุงแล้ว
    """
    # ลบเนื้อหาในวงเล็บ (ปกติเป็น metadata)
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'^\[[^\]]+\]\s*', '', text)
    text = re.sub(r'[#*_`]+', '', text)

    # แทนที่คำศัพท์ทางเทคนิค/URL
    replacements = {
        # URL components
        r'(?<!\S)www(?=\.)': "world wide web",
        r'\.com\b': "dot com",
        r'\.org\b': "dot org",
        r'\.net\b': "dot net",
        r'\.ac\b': "dot A C",
        r'\.th\b': "dot T H",
        r'\.co\b': "dot C O",
        r'(?<!\S)cmu(?=\.ac\.th)': "C M U",

        # Abbreviations
        r'\.e\.g\.\b': "for example",
        r'\.i\.e\.\b': "that is",
        r'\.dept\.\b': "department",
        r'\betc\.\b': "et cetera",

        # Common tech terms
        r'\bAPI\b': "A P I",
        r'\bURL\b': "U R L",
        r'\bPDF\b': "P D F",
        r'\bHTML\b': "H T M L",

        # Remove generic bot/admin prefixes
        r'^\[Bot[^\]]*\]\s*': '',
        r'^\[Admin\]:\s*': '',
    }

    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # ลบช่องว่างซ้ำซ้อน
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


# ----------------------------------------------------------------------------- #
# LANGUAGE DETECTION & SPLITTING
# ----------------------------------------------------------------------------- #
def split_text_by_language(text: str) -> List[Tuple[str, str]]:
    """
    แยกข้อความตามภาษาเพื่อใช้เสียงที่เหมาะสม

    Args:
        text: ข้อความที่ต้องการแยก

    Returns:
        list: List of tuples (language_code, text_segment)

    Example:
        >>> split_text_by_language("สวัสดี Hello 你好")
        [('th', 'สวัสดี'), ('en', 'Hello'), ('zh', '你好')]
    """
    pattern = r'([ก-๙]+|[a-zA-Z]+|[0-9]+|[.,!?\'"() ]+|[\u4e00-\u9fff]+|[\u3040-\u309F\u30A0-\u30FF]+)'
    matches = re.finditer(pattern, text)

    segments: List[Tuple[str, str]] = []
    current_lang: Optional[str] = None
    current_text = ""

    for match in matches:
        segment = match.group()

        # ข้ามช่องว่าง
        if not segment.strip():
            current_text += segment
            continue

        # กำหนดภาษา
        if re.match(r'^[0-9]+$', segment):
            lang = current_lang if current_lang else "th"
        elif re.search(r'[ก-๙]', segment):
            lang = "th"
        elif re.search(r'[a-zA-Z]', segment):
            lang = "en"
        elif re.search(r'[\u4e00-\u9fff]', segment):
            lang = "zh"
        elif re.search(r'[\u3040-\u309F\u30A0-\u30FF]', segment):
            lang = "ja"
        else:
            lang = current_lang if current_lang else "th"

        # รวม segment ถ้าเป็นภาษาเดียวกัน
        if lang == current_lang or current_lang is None:
            current_text += segment
            current_lang = lang
        else:
            if current_text.strip():
                segments.append((current_lang, current_text.strip()))
            current_text = segment
            current_lang = lang

    # บันทึก segment สุดท้าย
    if current_text.strip() and current_lang:
        segments.append((current_lang, current_text.strip()))

    # Fallback ถ้าไม่มี segments
    if not segments:
        segments = [("th", text)]

    return segments


# ----------------------------------------------------------------------------- #
# ฟังก์ชันสำหรับทดสอบ
# ----------------------------------------------------------------------------- #
async def test_tts():
    """ทดสอบระบบ TTS"""
    test_texts = [
        "สวัสดีครับ",
        "Hello world",
        "สวัสดีครับ // Hello // 你好",
        "ปฏิทินการศึกษา Academic Calendar 2568",
        "",  # Edge case: empty
        "www.cmu.ac.th คือเว็บไซต์ของมหาวิทยาลัยเชียงใหม่",
    ]

    for text in test_texts:
        print(f"\n{'='*60}")
        print(f"Testing: {text[:50]}")
        print("=" * 60)

        chunk_count = 0
        total_bytes = 0
        async for chunk in speak(text):
            chunk_count += 1
            total_bytes += len(chunk)

        print(f"Generated {chunk_count} chunks, {total_bytes:,} bytes")


if __name__ == "__main__":
    asyncio.run(test_tts())
