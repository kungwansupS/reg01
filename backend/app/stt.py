import os
import speech_recognition as sr
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ffmpeg_bin = os.path.join(BASE_DIR, "ffmpeg", "bin")

os.environ["PATH"] = ffmpeg_bin + os.pathsep + os.environ["PATH"]

from pydub import AudioSegment

def transcribe(filepath):
    wav_path = os.path.join(tempfile.gettempdir(), "converted.wav")
    AudioSegment.from_file(filepath).export(wav_path, format="wav")

    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_path) as source:
        audio_data = recognizer.record(source)
        try:
            return recognizer.recognize_google(audio_data, language="th-TH")
        except sr.UnknownValueError:
            return "❌ ไม่เข้าใจเสียง"
        except sr.RequestError as e:
            return f"✖️ เกิดปัญหาในการเชื่อมต่อ: {e}"
