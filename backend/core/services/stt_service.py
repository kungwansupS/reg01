import os
import tempfile

import speech_recognition as sr
from pydub import AudioSegment


async def transcribe_upload(raw_bytes: bytes, suffix: str = ".webm") -> str:
    if not raw_bytes:
        return ""

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as src:
        src.write(raw_bytes)
        src_path = src.name

    wav_path = src_path + ".wav"
    try:
        audio = AudioSegment.from_file(src_path)
        audio.export(wav_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
        return recognizer.recognize_google(audio_data, language="th-TH")
    except Exception:
        return ""
    finally:
        for path in (src_path, wav_path):
            if os.path.exists(path):
                os.remove(path)

