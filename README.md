# ระบบผู้ช่วยพี่เร็ก – สำนักทะเบียนมหาวิทยาลัยเชียงใหม่

## รายละเอียดโครงการ
ระบบนี้ถูกพัฒนาขึ้นเพื่ออำนวยความสะดวกแก่ผู้ใช้งานในการสอบถามข้อมูลจากเอกสารราชการ เช่น ปฏิทินการศึกษา กำหนดวันสำคัญ และขั้นตอนต่าง ๆ ของสำนักทะเบียนมหาวิทยาลัยเชียงใหม่ โดยใช้เทคโนโลยีปัญญาประดิษฐ์ในการประมวลผลและตอบกลับทั้งในรูปแบบข้อความและเสียง รองรับการใช้งานผ่านเว็บเบราว์เซอร์หรือระบบ Kiosk

## คุณสมบัติของระบบ
- รองรับการสื่อสารผ่านข้อความและเสียงพูด
- แปลงเสียงเป็นข้อความด้วย Speech-to-Text (STT)
- วิเคราะห์คำถามและดึงข้อมูลจากเอกสาร PDF ด้วย AI
- ตอบกลับด้วยข้อความและเสียง (Text-to-Speech - TTS)
- รองรับการสนทนาแบบเรียลไทม์ผ่าน WebSocket
- แนะนำท่าทาง (motion) สำหรับการใช้งานร่วมกับโมเดลตัวละครเสมือน

## โครงสร้างระบบ
- Web Server: Quart (ASGI Framework)
- ผู้ให้บริการ LLM: Google Gemini, OpenAI GPT
- การประมวลผล PDF: PyMuPDF, PDFMiner
- Embedding Model: Sentence Transformers (multilingual-e5-small, bge-m3)
- STT: SpeechRecognition + pydub
- TTS: edge-tts (Microsoft Neural Voice)
- ระบบค้นหา: Semantic Search จาก Embedding
- ระบบบทสนทนา: จัดการ Memory และ Session

## ขั้นตอนการทำงาน
1. ผู้ใช้งานพูดหรือพิมพ์คำถามผ่านอินเตอร์เฟส
2. ระบบแปลงเสียงเป็นข้อความ (ถ้ามี)
3. ระบบจัดการและสร้างคำถามสำหรับ AI
4. โมเดล AI วิเคราะห์คำถามและค้นหาข้อมูลจากไฟล์ PDF
5. ระบบสร้างคำตอบ พร้อมแนะนำท่าทาง (motion)
6. ตอบกลับผู้ใช้งานด้วยข้อความและ/หรือเสียง

## การติดตั้งและใช้งาน

### ติดตั้งไลบรารี
1. สร้าง Virtual Environment
2. ติดตั้งไลบรารี:
```bash
python install_requirements.py #cuda suport
```
หรือ

```bash
pip install -r requirements.txt
```

3. เริ่มต้นระบบ:
```bash
python run.py
```

4. url:
```bash
http://localhost:5000/
```

### การใช้งานร่วมกับ Facebook Messenger
สามารถใช้ร่วมกับ Cloudflare Tunnel ได้เลย

## โครงสร้างโปรเจกต์
```
─ run.py                        # จุดเริ่มต้นระบบ (เรียก uvicorn)
─ install_requirements.py       # ตัวติดตั้ง module อัตโนมัติ
backend
├── main.py                     # API หลัก รับคำถามและเสียง
├── pdf_to_txt.py               # แปลง PDF เป็นข้อความ
├── app/
│   ├── tts.py                  # ระบบแปลงข้อความเป็นเสียง
│   ├── stt.py                  # ระบบแปลงเสียงเป็นข้อความ             
│   ├── static/
│   │   └── docs/               # ที่เก็บข้อมุล PDF
│   │   └── quick_use/          # ที่เก็บข้อมูลจาก PDF to txt
│   ├── utils/
│   │   └── llm/                # การเชื่อมต่อโมเดล LLM
│   ├── ffmpeg/                 # ส่วนจำเป็นสำหรับ STT ของระบบ
│   └── prompt/                 # prompt สำหรับ LLM
├── memory/
│   ├── faq_cache.py            # จัดการคำที่ถูกถามบ่อย
│   ├── session.py              # จัดการ session
│   └── memory.py               # สรุปความจำการสนทนา
├── retriever/
│   └── context_selector.py     # ระบบเลือกข้อมูลจาก PDF
├── docs/# โฟลเดอร์ไฟล์ PDF
└── static/quick_use/           # ข้อความที่แปลงจาก PDF
```

## การกำหนดค่าในไฟล์ `.env`
```
GEMINI_API_KEY=your_google_api_key
OPENAI_API_KEY=your_openai_api_key
LLM_PROVIDER=gemini
GEMINI_MODEL_NAME=gemini-2.0-flash
OPENAI_MODEL_NAME=gpt-3.5-turbo

PORT=5000
HOST=0.0.0.0
```

## ข้อแนะนำการใช้งาน
- ควรเตรียมไฟล์ PDF ให้อ่านง่าย และแบ่งหัวข้อชัดเจน
- ใช้ภาษาไทยมาตรฐานในการสอบถาม เพื่อให้ระบบเข้าใจแม่นยำ
- หากระบบตอบไม่ถูกต้อง อาจต้องตรวจสอบข้อความจากการแปลงเสียง

## การต่อยอดใช้งาน
ระบบนี้สามารถนำไปปรับใช้กับ
- ระบบ VTuber หรือ Avatar สำหรับบริการแนะแนว
- เว็บไซต์ของหน่วยงานราชการหรือมหาวิทยาลัย