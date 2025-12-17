import edge_tts
import re
from typing import AsyncGenerator

LANGUAGE_SETTINGS = {
    "th": {
        #th-TH-NiwatNeural
        #th-TH-PremwadeeNeural
        "voice": "th-TH-NiwatNeural",
        "rate": "+0%",
        "volume": "+5%",
        "pitch": "+0Hz"
    },
    "en": {
        #en-US-AnaNeural
        #en-US-en-US-GuyNeural
        "voice": "en-US-GuyNeural",
        "rate": "-10%",
        "volume": "+3%",
        "pitch": "+0Hz"
    },
    "zh": {
        #zh-CN-XiaoxiaoNeural
        #zh-CN-YunxiNeural
        "voice": "zh-CN-YunxiNeural",
        "rate": "-20%",
        "volume": "+5%",
        "pitch": "-20Hz"
    }
}
async def speak_segment(segment_text: str, settings: dict) -> AsyncGenerator[bytes, None]:
    try:
        communicate = edge_tts.Communicate(
            text=segment_text,
            voice=settings["voice"],
            rate=settings["rate"],
            volume=settings["volume"],
            pitch=settings["pitch"]
        )
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]
    except Exception as e:
        print(f"❌ ไม่สามารถพูด '{segment_text}': {e}")

async def speak(text: str):
    text = preprocess_text(text)
    parts = [p.strip() for p in text.split("//") if p.strip()]
    for part in parts:
        segments = split_text_by_language(part)
        for lang, segment_text in segments:
            settings = LANGUAGE_SETTINGS.get(lang, LANGUAGE_SETTINGS["en"])
            async for chunk in speak_segment(segment_text, settings):
                yield chunk

def preprocess_text(text: str) -> str:
    text = re.sub(r'\([^)]*\)', '', text)

    replacements = {
        r'(?<!\S)www(?=\.)': "world wide web",
        r'\.com\b': "dot com",
        r'\.org\b': "dot org",
        r'\.net\b': "dot net",
        r'\.ac\b': "dot A C",
        r'\.th\b': "dot T H",
        r'\.co\b': "dot C O",
        r'(?<!\S)cmu(?=\.ac\.th)': "C M U",
        r'\.e.g.\b': "for example",
        r'\.i.e.\b': "that is",
        r'\.dept.\b': "department",
    }

    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text.strip()

def split_text_by_language(text):
    pattern = r'([ก-๙]+|[a-zA-Z]+|[0-9]+|[.,!?\'"() ]+|[\u4e00-\u9fff]+)'
    matches = re.finditer(pattern, text)

    segments = []
    current_lang = None
    current_text = ""

    for match in matches:
        segment = match.group()
        if not segment.strip():
            continue

        if re.match(r'^[0-9]+$', segment):
            lang = current_lang if current_lang else "th"
        elif re.search(r'[ก-๙]', segment):
            lang = "th"
        elif re.search(r'[a-zA-Z]', segment):
            lang = "en"
        elif re.search(r'[\u4e00-\u9fff]', segment):
            lang = "zh"
        else:
            lang = current_lang if current_lang else "th"

        if lang == current_lang or current_lang is None:
            current_text += segment
            current_lang = lang
        else:
            segments.append((current_lang, current_text.strip()))
            current_text = segment
            current_lang = lang

    if current_text:
        segments.append((current_lang, current_text.strip()))

    return segments


