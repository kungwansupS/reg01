import edge_tts
import re
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# ตั้งค่าเสียงสำหรับแต่ละภาษา
LANGUAGE_SETTINGS = {
    "th": {
        # th-TH-NiwatNeural (ผู้ชาย)
        # th-TH-PremwadeeNeural (ผู้หญิง)
        "voice": "th-TH-NiwatNeural",
        "rate": "+0%",
        "volume": "+5%",
        "pitch": "+0Hz"
    },
    "en": {
        # en-US-GuyNeural (ผู้ชาย)
        # en-US-AnaNeural (ผู้หญิง)
        "voice": "en-US-GuyNeural",
        "rate": "-10%",
        "volume": "+3%",
        "pitch": "+0Hz"
    },
    "zh": {
        # zh-CN-YunxiNeural (ผู้ชาย)
        # zh-CN-XiaoxiaoNeural (ผู้หญิง)
        "voice": "zh-CN-YunxiNeural",
        "rate": "-20%",
        "volume": "+5%",
        "pitch": "-20Hz"
    },
    "ja": {
        # ja-JP-KeitaNeural (ผู้ชาย)
        # ja-JP-NanamiNeural (ผู้หญิง)
        "voice": "ja-JP-KeitaNeural",
        "rate": "-10%",
        "volume": "+5%",
        "pitch": "+0Hz"
    }
}

async def speak_segment(segment_text: str, settings: dict) -> AsyncGenerator[bytes, None]:
    """
    แปลงข้อความเป็นเสียงสำหรับ segment เดียว
    
    Args:
        segment_text: ข้อความที่ต้องการแปลง
        settings: ค่าตั้งของเสียง (voice, rate, volume, pitch)
    
    Yields:
        bytes: Audio data chunks
    """
    try:
        communicate = edge_tts.Communicate(
            text=segment_text,
            voice=settings["voice"],
            rate=settings["rate"],
            volume=settings["volume"],
            pitch=settings["pitch"]
        )
        
        chunk_count = 0
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunk_count += 1
                yield chunk["data"]
        
        logger.debug(f"✅ Generated {chunk_count} audio chunks for: '{segment_text[:30]}...'")
        
    except Exception as e:
        logger.error(f"❌ TTS Error for '{segment_text[:30]}...': {e}")
        # ส่ง silent audio เพื่อไม่ให้ stream หยุดทำงาน
        yield b'\x00' * 1024

async def speak(text: str) -> AsyncGenerator[bytes, None]:
    """
    แปลงข้อความเป็นเสียงพูด รองรับหลายภาษาและ streaming
    
    Args:
        text: ข้อความที่ต้องการแปลงเป็นเสียง
    
    Yields:
        bytes: Audio data chunks (MP3 format)
    
    Example:
        >>> async for chunk in speak("สวัสดีครับ // Hello"):
        ...     # ส่ง chunk ไปยัง client
    """
    if not text or not text.strip():
        logger.warning("⚠️ Empty text provided to TTS")
        yield b'\x00' * 1024
        return
    
    try:
        # ทำความสะอาดข้อความ
        text = preprocess_text(text)
        
        # แยกส่วนตาม // delimiter
        parts = [p.strip() for p in text.split("//") if p.strip()]
        
        if not parts:
            logger.warning("⚠️ No valid parts after preprocessing")
            yield b'\x00' * 1024
            return
        
        logger.info(f"🎙️ Speaking {len(parts)} parts")
        
        # ประมวลผลแต่ละส่วน
        for i, part in enumerate(parts):
            # แบ่งตามภาษา
            segments = split_text_by_language(part)
            
            logger.debug(f"Part {i+1}/{len(parts)}: {len(segments)} language segments")
            
            # พูดแต่ละ segment
            for lang, segment_text in segments:
                if not segment_text.strip():
                    continue
                    
                settings = LANGUAGE_SETTINGS.get(lang, LANGUAGE_SETTINGS["th"])
                
                async for chunk in speak_segment(segment_text, settings):
                    yield chunk
            
            # เว้นช่วงเล็กน้อยระหว่าง parts (ถ้ามีหลาย parts)
            if i < len(parts) - 1:
                # ส่ง silence สั้นๆ (0.2 วินาที)
                yield b'\x00' * 512
        
        logger.info("✅ TTS completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Critical TTS Error: {e}")
        yield b'\x00' * 1024

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
        
        # Remove [Bot พี่เร็ก] prefix
        r'^\[Bot พี่เร็ก\]\s*': '',
        r'^\[Admin\]:\s*': '',
    }
    
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # ลบช่องว่างซ้ำซ้อน
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def split_text_by_language(text: str):
    """
    แยกข้อความตามภาษาเพื่อใช้เสียงที่เหมาะสม
    
    Args:
        text: ข้อความที่ต้องการแยก
    
    Returns:
        list: List of tuples (language_code, text_segment)
        
    Example:
        >>> split_text_by_language("สวัสดี Hello 你好")
        [('th', 'สวัสดี '), ('en', 'Hello '), ('zh', '你好')]
    """
    # Pattern สำหรับจับภาษาต่างๆ
    pattern = r'([ก-๙]+|[a-zA-Z]+|[0-9]+|[.,!?\'"() ]+|[\u4e00-\u9fff]+|[\u3040-\u309F\u30A0-\u30FF]+)'
    matches = re.finditer(pattern, text)

    segments = []
    current_lang = None
    current_text = ""

    for match in matches:
        segment = match.group()
        
        # ข้ามช่องว่าง
        if not segment.strip():
            current_text += segment
            continue

        # กำหนดภาษา
        if re.match(r'^[0-9]+$', segment):
            # ตัวเลข - ใช้ภาษาปัจจุบัน
            lang = current_lang if current_lang else "th"
        elif re.search(r'[ก-๙]', segment):
            # ภาษาไทย
            lang = "th"
        elif re.search(r'[a-zA-Z]', segment):
            # ภาษาอังกฤษ
            lang = "en"
        elif re.search(r'[\u4e00-\u9fff]', segment):
            # ภาษาจีน
            lang = "zh"
        elif re.search(r'[\u3040-\u309F\u30A0-\u30FF]', segment):
            # ภาษาญี่ปุ่น
            lang = "ja"
        else:
            # อื่นๆ - ใช้ภาษาปัจจุบัน
            lang = current_lang if current_lang else "th"

        # รวม segment ถ้าเป็นภาษาเดียวกัน
        if lang == current_lang or current_lang is None:
            current_text += segment
            current_lang = lang
        else:
            # บันทึก segment เก่า
            if current_text.strip():
                segments.append((current_lang, current_text.strip()))
            # เริ่ม segment ใหม่
            current_text = segment
            current_lang = lang

    # บันทึก segment สุดท้าย
    if current_text.strip():
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
        "www.cmu.ac.th คือเว็บไซต์ของมหาวิทยาลัยเชียงใหม่"
    ]
    
    for text in test_texts:
        print(f"\n{'='*60}")
        print(f"Testing: {text[:50]}")
        print('='*60)
        
        chunk_count = 0
        async for chunk in speak(text):
            chunk_count += 1
        
        print(f"✅ Generated {chunk_count} chunks")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_tts())