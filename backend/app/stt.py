import os
import speech_recognition as sr
import tempfile
import uuid
import shutil
import warnings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ffmpeg_local_bin = os.path.join(BASE_DIR, "ffmpeg", "bin")

if os.path.exists(ffmpeg_local_bin):
    os.environ["PATH"] = ffmpeg_local_bin + os.pathsep + os.environ["PATH"]

# ตรวจสอบว่ามี ffmpeg ใน System Path หรือไม่
FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None

# นำเข้า pydub หลังจากตั้งค่า PATH
try:
    from pydub import AudioSegment
except ImportError:
    # ในกรณีที่ยังไม่ได้ลง pydub (ป้องกัน Error สำหรับ Tester)
    AudioSegment = None

def transcribe(filepath):
    """
    แปลงเสียงเป็นข้อความ โดยใช้ความปลอดภัยสูงสุดสำหรับการทำงานแบบขนาน
    """
    if not FFMPEG_AVAILABLE:
        return "✖️ ระบบตรวจไม่พบ FFmpeg โปรดติดตั้งในเครื่อง (winget install ffmpeg)"

    # สร้างชื่อไฟล์ WAV แบบสุ่มเพื่อป้องกันไฟล์ชนกัน (Thread-Safe)
    unique_id = str(uuid.uuid4())
    wav_path = os.path.join(tempfile.gettempdir(), f"stt_{unique_id}.wav")
    
    try:
        # ตรวจสอบความพร้อมของ AudioSegment
        if AudioSegment is None:
            return "✖️ ไม่พบไลบรารี pydub โปรดรัน pip install pydub"

        # แปลงไฟล์ต้นฉบับเป็น WAV
        audio = AudioSegment.from_file(filepath)
        audio.export(wav_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            try:
                # ส่งไปประมวลผลที่ Google STT API (ต้องการ Internet)
                return recognizer.recognize_google(audio_data, language="th-TH")
            except sr.UnknownValueError:
                return "❌ ไม่เข้าใจเสียง"
            except sr.RequestError as e:
                return f"✖️ เกิดปัญหาในการเชื่อมต่อ API: {e}"
                
    except Exception as e:
        return f"✖️ ข้อผิดพลาดในการประมวลผลเสียง: {str(e)}"
        
    finally:
        # ลบไฟล์ชั่วคราวอย่างระมัดระวัง
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except:
                pass
        # ลบไฟล์ต้นฉบับที่ส่งเข้ามาหลังจากประมวลผลเสร็จ
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass