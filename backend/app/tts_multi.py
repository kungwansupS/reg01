"""
TTS Multi-Provider Module
ระบบสังเคราะห์เสียง Multi-Provider พร้อม Automatic Fallback

Provider Chain (ลำดับความสำคัญ):
  1. OpenAI TTS      — เสียงเหมือนคนจริงมาก, streaming, ต้องมี API key
  2. Google Cloud TTS — คุณภาพสูง WaveNet/Neural2, ภาษาไทยดีมาก, ต้องมี API key
  3. Edge TTS         — ฟรี Microsoft Edge Online TTS, fallback สุดท้าย

Public API (drop-in replacement สำหรับ tts.py):
  - speak(text)         → AsyncGenerator[bytes, None]   (MP3 streaming)
  - is_tts_available()  → bool
"""

import re
import io
import sys
import asyncio
import logging
import os
import time
import struct
from collections import deque
from typing import AsyncGenerator, List, Tuple, Optional, Dict, Any

import aiohttp

logger = logging.getLogger(__name__)

_WIN32 = sys.platform.startswith("win")


# ============================================================================= #
# ENVIRONMENT HELPERS
# ============================================================================= #
def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default)).strip()


def _env_bool(name: str, default: str = "true") -> bool:
    return _env(name, default).lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: str) -> int:
    try:
        return int(_env(name, default))
    except (TypeError, ValueError):
        return int(default)


# ============================================================================= #
# GLOBAL CONFIGURATION
# ============================================================================= #
TTS_ENABLED = _env_bool("TTS_ENABLED", "true")
TTS_PROVIDER = _env("TTS_PROVIDER", "auto")  # "openai" | "google" | "edge" | "auto"
TTS_DISABLE_ON_NETWORK_ERROR = _env_bool("TTS_DISABLE_ON_NETWORK_ERROR", "true")
TTS_NETWORK_ERROR_COOLDOWN_SECONDS = max(15, _env_int("TTS_NETWORK_ERROR_COOLDOWN_SECONDS", "60"))
TTS_NETWORK_ERROR_DISABLE_THRESHOLD = max(1, _env_int("TTS_NETWORK_ERROR_DISABLE_THRESHOLD", "3"))
TTS_MAX_RETRIES = max(0, _env_int("TTS_MAX_RETRIES", "1"))
TTS_SEGMENT_TIMEOUT_SECONDS = max(5, _env_int("TTS_SEGMENT_TIMEOUT_SECONDS", "15"))

# ─── OpenAI TTS Config ───────────────────────────────────────────────────────
OPENAI_TTS_API_KEY = _env("OPENAI_TTS_API_KEY") or _env("OPENAI_API_KEY")
OPENAI_TTS_BASE_URL = _env("OPENAI_TTS_BASE_URL", "https://api.openai.com/v1")
OPENAI_TTS_MODEL = _env("OPENAI_TTS_MODEL", "tts-1")        # tts-1 | tts-1-hd
OPENAI_TTS_VOICE = _env("OPENAI_TTS_VOICE", "nova")         # alloy|echo|fable|onyx|nova|shimmer
OPENAI_TTS_SPEED = float(_env("OPENAI_TTS_SPEED", "1.0"))
OPENAI_TTS_FORMAT = _env("OPENAI_TTS_FORMAT", "mp3")        # mp3|opus|aac|flac|wav|pcm

# ─── Gemini TTS Config (uses Gemini API key, generativelanguage endpoint) ────
GEMINI_TTS_API_KEY = _env("GEMINI_TTS_API_KEY") or _env("GEMINI_API_KEY")
GEMINI_TTS_MODEL = _env("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_TTS_VOICE = _env("GEMINI_TTS_VOICE", "Kore")  # Aoede|Charon|Fenrir|Kore|Puck|etc.

# ─── Edge TTS Config (legacy fallback) ───────────────────────────────────────
EDGE_TTS_VOICE_TH = _env("TTS_VOICE_TH", "th-TH-NiwatNeural")
EDGE_TTS_VOICE_EN = _env("TTS_VOICE_EN", "en-US-GuyNeural")
EDGE_TTS_VOICE_ZH = _env("TTS_VOICE_ZH", "zh-CN-YunxiNeural")
EDGE_TTS_VOICE_JA = _env("TTS_VOICE_JA", "ja-JP-KeitaNeural")
EDGE_TTS_RATE = _env("TTS_RATE_TH", "+0%")
EDGE_TTS_VOLUME = _env("TTS_VOLUME_TH", "+5%")
EDGE_TTS_CONNECT_TIMEOUT = max(3, _env_int("TTS_CONNECT_TIMEOUT", "10"))
EDGE_TTS_RECEIVE_TIMEOUT = max(5, _env_int("TTS_RECEIVE_TIMEOUT", "60"))

EDGE_LANGUAGE_SETTINGS: Dict[str, Dict[str, str]] = {
    "th": {"voice": EDGE_TTS_VOICE_TH, "rate": _env("TTS_RATE_TH", "+0%"), "volume": _env("TTS_VOLUME_TH", "+5%"), "pitch": _env("TTS_PITCH_TH", "+0Hz")},
    "en": {"voice": EDGE_TTS_VOICE_EN, "rate": _env("TTS_RATE_EN", "-10%"), "volume": _env("TTS_VOLUME_EN", "+3%"), "pitch": _env("TTS_PITCH_EN", "+0Hz")},
    "zh": {"voice": EDGE_TTS_VOICE_ZH, "rate": _env("TTS_RATE_ZH", "-20%"), "volume": _env("TTS_VOLUME_ZH", "+5%"), "pitch": _env("TTS_PITCH_ZH", "-20Hz")},
    "ja": {"voice": EDGE_TTS_VOICE_JA, "rate": _env("TTS_RATE_JA", "-10%"), "volume": _env("TTS_VOLUME_JA", "+5%"), "pitch": _env("TTS_PITCH_JA", "+0Hz")},
}



# ============================================================================= #
# CIRCUIT BREAKER (per provider)
# ============================================================================= #
class _CircuitBreaker:
    """Simple circuit breaker per provider"""

    def __init__(self) -> None:
        self._disabled_until: Dict[str, float] = {}
        self._consecutive_errors: Dict[str, int] = {}
        self._last_skip_log: Dict[str, float] = {}

    def is_disabled(self, provider: str) -> bool:
        until = self._disabled_until.get(provider, 0.0)
        return until > time.time()

    def record_success(self, provider: str) -> None:
        self._consecutive_errors[provider] = 0

    def record_error(self, provider: str, exc: BaseException) -> None:
        if not TTS_DISABLE_ON_NETWORK_ERROR:
            return

        # Rate limit errors → short cooldown (10s), don't count toward permanent disable
        err_str = str(exc)
        if err_str.startswith("RATE_LIMIT:"):
            self._disabled_until[provider] = time.time() + 10.0
            logger.info("TTS[%s] rate-limited, pausing 10s", provider)
            return

        count = self._consecutive_errors.get(provider, 0) + 1
        self._consecutive_errors[provider] = count
        if count >= TTS_NETWORK_ERROR_DISABLE_THRESHOLD:
            self._disabled_until[provider] = time.time() + float(TTS_NETWORK_ERROR_COOLDOWN_SECONDS)
            logger.warning(
                "TTS[%s] disabled for %ss after %d errors: %s",
                provider, TTS_NETWORK_ERROR_COOLDOWN_SECONDS, count, exc,
            )

    def log_skip(self, provider: str, reason: str) -> None:
        now = time.time()
        last = self._last_skip_log.get(provider, 0.0)
        if now - last >= 15:
            logger.warning("TTS[%s] skipped: %s", provider, reason)
            self._last_skip_log[provider] = now


_breaker = _CircuitBreaker()


# ============================================================================= #
# PROVIDER AVAILABILITY CHECK
# ============================================================================= #
def _get_available_providers() -> List[str]:
    """Return ordered list of available providers based on config"""
    if TTS_PROVIDER not in ("auto", "openai", "gemini", "edge"):
        logger.warning("Unknown TTS_PROVIDER=%s, using 'auto'", TTS_PROVIDER)

    if TTS_PROVIDER == "openai":
        return ["openai"]
    elif TTS_PROVIDER == "gemini":
        return ["gemini"]
    elif TTS_PROVIDER == "edge":
        return ["edge"]

    # auto: try all in order, skip those without valid API keys
    providers: List[str] = []

    # OpenAI TTS: only if we have a dedicated TTS key, or a real OpenAI key (sk-*)
    # Skip if OPENAI_API_KEY is actually a Groq/other compatible key
    _has_dedicated_tts_key = bool(_env("OPENAI_TTS_API_KEY"))
    _has_real_openai_key = (
        OPENAI_TTS_API_KEY
        and OPENAI_TTS_BASE_URL == "https://api.openai.com/v1"
        and (OPENAI_TTS_API_KEY.startswith("sk-") or _has_dedicated_tts_key)
    )
    if _has_dedicated_tts_key or _has_real_openai_key:
        providers.append("openai")

    if GEMINI_TTS_API_KEY:
        providers.append("gemini")

    providers.append("edge")  # always available (free)
    return providers


def is_tts_available() -> bool:
    """Check if any TTS provider is available"""
    if not TTS_ENABLED:
        return False
    providers = _get_available_providers()
    return any(not _breaker.is_disabled(p) for p in providers)


# ============================================================================= #
# TEXT PREPROCESSING (reuse from tts.py)
# ============================================================================= #
def preprocess_text(text: str) -> str:
    """Clean text before TTS synthesis"""
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'^\[[^\]]+\]\s*', '', text)
    text = re.sub(r'[#*_`]+', '', text)

    replacements = {
        r'(?<!\S)www(?=\.)': "world wide web",
        r'\.com\b': "dot com",
        r'\.org\b': "dot org",
        r'\.net\b': "dot net",
        r'\.ac\b': "dot A C",
        r'\.th\b': "dot T H",
        r'\.co\b': "dot C O",
        r'(?<!\S)cmu(?=\.ac\.th)': "C M U",
        r'\.e\.g\.\b': "for example",
        r'\.i\.e\.\b': "that is",
        r'\.dept\.\b': "department",
        r'\betc\.\b': "et cetera",
        r'\bAPI\b': "A P I",
        r'\bURL\b': "U R L",
        r'\bPDF\b': "P D F",
        r'\bHTML\b': "H T M L",
        r'^\[Bot[^\]]*\]\s*': '',
        r'^\[Admin\]:\s*': '',
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def split_text_by_language(text: str) -> List[Tuple[str, str]]:
    """Split text by language for appropriate voice selection"""
    pattern = r'([ก-๙]+|[a-zA-Z]+|[0-9]+|[.,!?\'"() ]+|[\u4e00-\u9fff]+|[\u3040-\u309F\u30A0-\u30FF]+)'
    matches = re.finditer(pattern, text)

    segments: List[Tuple[str, str]] = []
    current_lang: Optional[str] = None
    current_text = ""

    for match in matches:
        segment = match.group()
        if not segment.strip():
            current_text += segment
            continue

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

        if lang == current_lang or current_lang is None:
            current_text += segment
            current_lang = lang
        else:
            if current_text.strip():
                segments.append((current_lang, current_text.strip()))
            current_text = segment
            current_lang = lang

    if current_text.strip() and current_lang:
        segments.append((current_lang, current_text.strip()))

    if not segments:
        segments = [("th", text)]

    return segments


# Minimal valid MP3 silence frame (~26ms)
_MP3_SILENCE_FRAME = (
    b'\xff\xfb\x90\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00Info\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
)


# ============================================================================= #
# PROVIDER 1: OpenAI TTS (streaming)
# ============================================================================= #
async def _openai_stream_segment(text: str, lang: str = "th") -> AsyncGenerator[bytes, None]:
    """
    Stream audio from OpenAI TTS API.
    Uses streaming response for low-latency first-byte.
    Output: MP3 chunks
    """
    url = f"{OPENAI_TTS_BASE_URL}/audio/speech"
    headers = {
        "Authorization": f"Bearer {OPENAI_TTS_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_TTS_MODEL,
        "voice": OPENAI_TTS_VOICE,
        "input": text,
        "response_format": OPENAI_TTS_FORMAT,
        "speed": OPENAI_TTS_SPEED,
    }

    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    connector = None
    if _WIN32:
        resolver = aiohttp.ThreadedResolver()
        connector = aiohttp.TCPConnector(resolver=resolver, use_dns_cache=True)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"OpenAI TTS error {resp.status}: {body[:200]}")

            async for chunk in resp.content.iter_chunked(4096):
                if chunk:
                    yield chunk


# ============================================================================= #
# PROVIDER 2: Gemini TTS (generativelanguage.googleapis.com)
# ============================================================================= #
def _pcm_to_mp3(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1) -> bytes:
    """Convert raw PCM16 LE audio to MP3 using pydub + ffmpeg"""
    from pydub import AudioSegment
    segment = AudioSegment(
        data=pcm_data,
        sample_width=2,  # 16-bit
        frame_rate=sample_rate,
        channels=channels,
    )
    buf = io.BytesIO()
    segment.export(buf, format="mp3", bitrate="48k")
    return buf.getvalue()


async def _gemini_stream_segment(text: str, lang: str = "th") -> AsyncGenerator[bytes, None]:
    """
    Synthesize audio from Gemini TTS API.
    Uses generativelanguage.googleapis.com endpoint with Gemini API key.
    Output: PCM16 24kHz mono → converted to MP3 for frontend compatibility.
    Auto-detects language, no per-language voice mapping needed.
    """
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_TTS_MODEL}:generateContent?key={GEMINI_TTS_API_KEY}"
    )

    # Gemini TTS needs explicit instruction to read the text as-is
    tts_prompt = f"Say: {text}"

    payload = {
        "contents": [{"parts": [{"text": tts_prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": GEMINI_TTS_VOICE,
                    }
                }
            },
        },
    }

    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    connector = None
    if _WIN32:
        resolver = aiohttp.ThreadedResolver()
        connector = aiohttp.TCPConnector(resolver=resolver, use_dns_cache=True)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        async with session.post(url, json=payload, headers={"Content-Type": "application/json"}) as resp:
            if resp.status != 200:
                body = await resp.text()
                # 429 = rate limit, raise specific error so circuit breaker can distinguish
                err_msg = f"Gemini TTS error {resp.status}: {body[:300]}"
                if resp.status == 429:
                    raise RuntimeError(f"RATE_LIMIT:{err_msg}")
                raise RuntimeError(err_msg)

            data = await resp.json()

            # Extract base64 PCM audio from response
            # Handle various response structures (blocked, empty, etc.)
            audio_b64 = ""
            try:
                candidates = data.get("candidates", [])
                if not candidates:
                    block_reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
                    raise RuntimeError(f"Gemini TTS blocked: {block_reason}")
                candidate = candidates[0]
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                if parts:
                    inline_data = parts[0].get("inlineData", {})
                    audio_b64 = inline_data.get("data", "")
            except (KeyError, IndexError, AttributeError) as e:
                raise RuntimeError(f"Gemini TTS unexpected response: {e}")

            if not audio_b64:
                raise RuntimeError("Gemini TTS returned no audio data")

            import base64
            pcm_bytes = base64.b64decode(audio_b64)

            # Convert PCM16 24kHz mono → MP3
            mp3_bytes = await asyncio.to_thread(_pcm_to_mp3, pcm_bytes, 24000, 1)

            # Yield in chunks for consistency with streaming interface
            chunk_size = 4096
            for i in range(0, len(mp3_bytes), chunk_size):
                yield mp3_bytes[i:i + chunk_size]


# ============================================================================= #
# PROVIDER 3: Edge TTS (free fallback)
# ============================================================================= #
async def _edge_stream_segment(text: str, lang: str = "th") -> AsyncGenerator[bytes, None]:
    """Stream audio from Microsoft Edge TTS (free, no API key needed)"""
    import edge_tts

    settings = EDGE_LANGUAGE_SETTINGS.get(lang, EDGE_LANGUAGE_SETTINGS["th"])

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
        connect_timeout=EDGE_TTS_CONNECT_TIMEOUT,
        receive_timeout=EDGE_TTS_RECEIVE_TIMEOUT,
        connector=connector,
    )

    async for chunk in communicate.stream():
        if chunk["type"] == "audio" and chunk["data"]:
            yield chunk["data"]


# ============================================================================= #
# PROVIDER DISPATCH WITH RETRY + FALLBACK
# ============================================================================= #
_PROVIDER_FN = {
    "openai": _openai_stream_segment,
    "gemini": _gemini_stream_segment,
    "edge": _edge_stream_segment,
}


async def _stream_with_provider(
    provider: str, text: str, lang: str
) -> AsyncGenerator[bytes, None]:
    """Stream a single segment with one provider, with retry logic"""
    fn = _PROVIDER_FN[provider]
    last_exc: Optional[BaseException] = None

    for attempt in range(1 + TTS_MAX_RETRIES):
        if _breaker.is_disabled(provider):
            return

        try:
            chunk_count = 0
            async for audio_data in fn(text, lang):
                chunk_count += 1
                yield audio_data

            if chunk_count > 0:
                _breaker.record_success(provider)
                return
            else:
                last_exc = RuntimeError(f"No audio data from {provider}")
                logger.warning("TTS[%s] returned no audio (attempt %d)", provider, attempt + 1)

        except Exception as exc:
            last_exc = exc
            _breaker.record_error(provider, exc)
            logger.warning("TTS[%s] error (attempt %d/%d): %s", provider, attempt + 1, 1 + TTS_MAX_RETRIES, exc)

            if _breaker.is_disabled(provider):
                return

        if attempt < TTS_MAX_RETRIES:
            backoff = min(0.5 * (2 ** attempt), 4.0)
            await asyncio.sleep(backoff)

    if last_exc:
        logger.error("TTS[%s] segment failed after %d attempts: %s", provider, 1 + TTS_MAX_RETRIES, last_exc)


async def _stream_segment_with_fallback(text: str, lang: str) -> AsyncGenerator[bytes, None]:
    """
    Try to stream a text segment through the provider chain.
    Falls back to next provider on failure.
    """
    providers = _get_available_providers()

    for provider in providers:
        if _breaker.is_disabled(provider):
            _breaker.log_skip(provider, f"circuit breaker active")
            continue

        logger.debug("TTS trying provider=%s for lang=%s text='%s...'", provider, lang, text[:30])

        got_audio = False
        try:
            async for chunk in _stream_with_provider(provider, text, lang):
                got_audio = True
                yield chunk
        except Exception as exc:
            logger.warning("TTS[%s] fallback error: %s", provider, exc)

        if got_audio:
            return

        logger.info("TTS[%s] produced no audio, trying next provider...", provider)

    logger.error("All TTS providers failed for text='%s...'", text[:40])


# ============================================================================= #
# PUBLIC API: speak()
# ============================================================================= #
async def speak(text: str) -> AsyncGenerator[bytes, None]:
    """
    Convert text to speech audio using multi-provider system.

    Args:
        text: Text to convert to speech

    Yields:
        bytes: Audio data chunks (MP3 format)

    Example:
        >>> async for chunk in speak("สวัสดีครับ // Hello"):
        ...     # send chunk to client
    """
    if not TTS_ENABLED:
        logger.debug("TTS disabled by configuration")
        return

    if not is_tts_available():
        logger.debug("No TTS providers currently available")
        return

    if not text or not text.strip():
        logger.warning("Empty text provided to TTS")
        return

    try:
        text = preprocess_text(text)

        # Split by // delimiter
        parts = [p.strip() for p in text.split("//") if p.strip()]
        if not parts:
            logger.warning("No valid parts after preprocessing")
            return

        providers = _get_available_providers()
        active_provider = next((p for p in providers if not _breaker.is_disabled(p)), "edge")
        logger.info("TTS speaking %d part(s) via %s (+%d fallbacks)",
                     len(parts), active_provider, len(providers) - 1)

        for i, part in enumerate(parts):
            if not part.strip():
                continue

            # Gemini & OpenAI auto-detect language → send whole part as one call
            # Edge TTS needs per-language splitting for correct voice selection
            got_audio = False
            for provider in _get_available_providers():
                if _breaker.is_disabled(provider):
                    continue

                if provider == "edge":
                    # Edge TTS: split by language for correct voice
                    segments = split_text_by_language(part)
                    for lang, seg_text in segments:
                        if not seg_text.strip():
                            continue
                        async for chunk in _stream_with_provider("edge", seg_text, lang):
                            got_audio = True
                            yield chunk
                else:
                    # Gemini/OpenAI: single call per part (auto-detect language)
                    try:
                        async for chunk in _stream_with_provider(provider, part, "auto"):
                            got_audio = True
                            yield chunk
                    except Exception as exc:
                        logger.warning("TTS[%s] error: %s", provider, exc)

                if got_audio:
                    break

            if not got_audio:
                logger.error("All providers failed for part %d", i + 1)

            if not is_tts_available():
                return

            # Short silence between parts + small delay to avoid rate limits
            if i < len(parts) - 1:
                yield _MP3_SILENCE_FRAME
                await asyncio.sleep(0.5)

        logger.info("TTS completed successfully")

    except Exception as e:
        logger.error(f"Critical TTS Error: {e}")
        return


# ============================================================================= #
# TEST FUNCTION
# ============================================================================= #
async def test_tts():
    """Test TTS multi-provider system"""
    test_texts = [
        "สวัสดีครับ",
        "Hello world",
        "สวัสดีครับ // Hello // 你好",
        "ปฏิทินการศึกษา Academic Calendar 2568",
        "",
        "www.cmu.ac.th คือเว็บไซต์ของมหาวิทยาลัยเชียงใหม่",
    ]

    print(f"TTS Provider: {TTS_PROVIDER}")
    print(f"Available: {_get_available_providers()}")
    print(f"OpenAI key: {'set' if OPENAI_TTS_API_KEY else 'NOT SET'}")
    print(f"Google key: {'set' if GOOGLE_TTS_API_KEY else 'NOT SET'}")
    print()

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
