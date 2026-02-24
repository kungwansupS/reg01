# ระบบผู้ช่วยพี่เร็ก – สำนักทะเบียนมหาวิทยาลัยเชียงใหม่

## ภาพรวมโครงการ

ระบบผู้ช่วยอัจฉริยะสำหรับสำนักทะเบียนมหาวิทยาลัยเชียงใหม่ ที่พัฒนาขึ้นเพื่อให้บริการข้อมูลเกี่ยวกับปฏิทินการศึกษา กำหนดวันสำคัญ และขั้นตอนต่างๆ ของสำนักทะเบียน โดยใช้เทคโนโลยีปัญญาประดิษฐ์ในการประมวลผลและตอบกลับทั้งในรูปแบบข้อความและเสียง

## คุณสมบัติหลัก

### การสื่อสารและอินเตอร์เฟซ
- รองรับการสื่อสารผ่านข้อความและเสียงพูด
- แปลงเสียงเป็นข้อความด้วยระบบ Speech-to-Text
- ตอบกลับด้วยข้อความและเสียงพูด Text-to-Speech
- รองรับการสนทนาแบบเรียลไทม์ผ่าน WebSocket
- ติดต่อผ่านเว็บเบราว์เซอร์หรือระบบ Kiosk

### ระบบปัญญาประดิษฐ์
- วิเคราะห์คำถามและดึงข้อมูลจากเอกสาร PDF ด้วย AI
- รองรับผู้ให้บริการ LLM หลายราย: Google Gemini, OpenAI GPT, Local Models
- ระบบค้นหาแบบ Hybrid Search (Dense + Sparse)
- การจัดการความจำและบทสนทนาอัตโนมัติ
- ระบบเรียนรู้คำถามที่ถูกถามบ่อย (FAQ Cache)

### การจัดการเอกสาร
- ประมวลผลไฟล์ PDF ด้วย PyMuPDF และ PDFMiner
- สร้าง Embeddings ด้วย Sentence Transformers
- จัดเก็บข้อมูลใน Vector Database (ChromaDB)
- ระบบ BM25 Index สำหรับการค้นหาแบบคำสำคัญ

### การจัดการผู้ใช้งาน
- ระบบบริหารจัดการผ่าน Admin Dashboard
- รองรับหลายแพลตฟอร์ม: Web, Facebook Messenger, LINE
- จัดเก็บประวัติการสนทนาใน PostgreSQL Database
- ระบบควบคุมการเปิด-ปิดบอทแบบเฉพาะผู้ใช้

## สถาปัตยกรรมระบบ

### Backend
- **Web Framework**: FastAPI (ASGI Framework)
- **Real-time Communication**: SocketIO
- **Database**: PostgreSQL (Session Management)
- **Vector Store**: ChromaDB

### การประมวลผลภาษา
- **LLM Providers**: 
  - Google Gemini (gemini-3-flash)
  - OpenAI GPT (gpt-5-nano)
  - Local Models (Ollama)
- **Embedding Models**: 
  - BAAI/bge-m3 (CUDA)
  - intfloat/multilingual-e5-small (CPU)
- **Language Detection**: langdetect
- **Token Management**: tiktoken

### การประมวลผลเสียง
- **Speech-to-Text**: SpeechRecognition + pydub
- **Text-to-Speech**: edge-tts (Microsoft Neural Voice)
- **รองรับภาษา**: ไทย, อังกฤษ, จีน, ญี่ปุ่น

### Frontend
- **Model Visualization**: Live2D (Pixi.js)
- **UI Framework**: HTML5, CSS3, JavaScript
- **Admin Dashboard**: Alpine.js, Tailwind CSS

## การติดตั้งและใช้งาน

### ความต้องการของระบบ

#### ซอฟต์แวร์
- Python 3.10.9 หรือสูงกว่า
- Node.js (สำหรับ dependencies บางตัว)
- FFmpeg (สำหรับการประมวลผลเสียง)

#### ฮาร์ดแวร์ (แนะนำ)
- RAM: 8GB ขึ้นไป
- GPU: NVIDIA CUDA-compatible (สำหรับ Embedding ที่เร็วขึ้น)
- Storage: 10GB ว่างขึ้นไป

### ขั้นตอนการติดตั้ง

#### 1. Clone Repository
```bash
git clone https://github.com/your-repo/reg01-system.git
cd reg01-system
```

#### 2. ติดตั้งและเปิดระบบอัตโนมัติ (Windows แนะนำ)

รันไฟล์:
```bat
install\setup_auto.bat
```

สคริปต์จะทำงานดังนี้:
- ตรวจว่ามี `WSL`, `Python 3.11+`, `Docker Desktop` แล้วหรือยัง และติดตั้งให้อัตโนมัติเมื่อไม่พบ
- แจ้งเฉพาะขั้นตอนที่ต้องทำเองจริงๆ (เช่น `docker login`, แก้ไข `backend/.env`)
- ให้ผู้ใช้ยืนยันแล้วตรวจซ้ำก่อนผ่านแต่ละขั้นตอน
- รัน `docker compose up -d --build` และเปิดระบบให้ทันที

#### 3. ติดตั้ง Dependencies (กรณีไม่ใช้ install\setup_auto.bat)

**แบบอัตโนมัติ (แนะนำ):**
```bash
python install\install_requirements.py
```

**แบบแมนนวล:**
```bash
pip install -r requirements.txt
```

#### 4. ตั้งค่าสภาพแวดล้อม

สร้างไฟล์ `.env` ในโฟลเดอร์ `backend/`:
```env
# LLM Provider
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL_NAME=gemini-3-flash

# Server Configuration
PORT=5000
HOST=0.0.0.0
ALLOWED_ORIGINS=*

# RAG System
USE_RETRIEVAL_ENGINE=true

# Facebook Messenger (Optional)
FB_VERIFY_TOKEN=your_verify_token
FB_PAGE_ACCESS_TOKEN=your_page_token
FB_APP_SECRET=your_app_secret
```

#### 5. เตรียมข้อมูล PDF

วางไฟล์ PDF ในโฟลเดอร์:
```
backend/app/static/docs/
```

จากนั้นรันการประมวลผล:
```bash
cd backend
python pdf_to_txt.py
```

#### 6. เริ่มต้นระบบ

**บน Windows:**
```bash
start.bat
```
เมนูจะมี 3 ตัวเลือก:
- `1` Start: ตรวจ Docker และเปิดทุก service
- `2` Tunnel: เปิด Cloudflare Tunnel (`tunnel.py`)
- `3` Install: ตรวจและติดตั้งทุกอย่างให้พร้อมใช้งาน

**บน Linux/Mac:**
```bash
python run.py
```

#### 7. เข้าถึงระบบ

- **หน้าแชท**: http://localhost:3000/
- **Admin Dashboard**: http://localhost:3000/admin
- **Live Voice Chat**: http://localhost:3000/live
- **Dev Console**: http://localhost:3000/dev
- **Backend API**: http://localhost:5000/

## การใช้งาน Admin Dashboard

### การเข้าสู่ระบบ
ใช้ Admin Token ที่ตั้งไว้ใน `.env`:
```env
ADMIN_TOKEN=your-secret-key
```

### ฟีเจอร์หลัก

#### 1. Dashboard
- สถิติการใช้งานระบบ
- กราฟการใช้งานตามแพลตฟอร์ม
- ข้อมูล FAQ ที่ถูกถามบ่อย
- สถานะระบบ Real-time

#### 2. Unified Chat
- ดูการสนทนาจากทุกแพลตฟอร์ม
- ควบคุมการเปิด-ปิดบอทต่อผู้ใช้
- ส่งข้อความตอบกลับด้วยตนเอง
- แสดงสถานะการเชื่อมต่อ

#### 3. File Explorer
- อัปโหลด/ดาวน์โหลดเอกสาร PDF
- จัดการโครงสร้างไฟล์
- แก้ไขไฟล์ข้อความ
- ดูตัวอย่างเอกสาร

#### 4. Audit Logs
- ติดตามการใช้งานทั้งหมด
- ข้อมูลการใช้ Token
- เวลาตอบสนองของระบบ
- Export ข้อมูล Log

#### 5. Database Management
- จัดการ Session ผู้ใช้งาน
- ดูประวัติการสนทนา
- แก้ไข/ลบข้อความ
- ล้างข้อมูลเก่า

## โครงสร้างโปรเจกต์

```
REG-01/
├── backend/
│   ├── main.py                 # จุดเริ่มต้น Application
│   ├── pdf_to_txt.py          # ประมวลผล PDF
│   ├── app/
│   │   ├── config.py          # การตั้งค่าระบบ
│   │   ├── stt.py            # Speech-to-Text
│   │   ├── tts.py            # Text-to-Speech
│   │   ├── prompt/           # Prompt Templates
│   │   ├── static/
│   │   │   ├── docs/         # ไฟล์ PDF ต้นฉบับ
│   │   │   └── quick_use/    # ไฟล์ข้อความที่ประมวลผลแล้ว
│   │   └── utils/
│   │       ├── llm/          # การเชื่อมต่อ LLM
│   │       ├── vector_manager.py
│   │       └── metadata_extractor.py
│   ├── memory/
│   │   ├── session.py        # จัดการ Session
│   │   ├── session_db.py     # PostgreSQL Database
│   │   ├── memory.py         # สรุปบทสนทนา
│   │   └── faq_cache.py      # คำถามที่ถูกถามบ่อย
│   ├── retriever/
│   │   ├── context_selector.py
│   │   └── hybrid_retriever.py
│   └── router/
│       ├── chat_router.py
│       ├── webhook_router.py
│       ├── admin_router.py
│       ├── database_router.py
│       ├── socketio_handlers.py
│       └── background_tasks.py
├── frontend-next/             # Next.js Frontend (React 19 + Tailwind)
│   ├── src/app/              # Pages (/, /live, /admin, /dev)
│   ├── src/components/       # Reusable components
│   ├── src/hooks/            # Custom hooks (TTS, recorder)
│   ├── src/lib/              # Utilities (api, socket, utils)
│   ├── src/providers/        # React context providers
│   └── Dockerfile
├── run.py                     # เริ่มต้นระบบ
├── install/
│   ├── setup_auto.bat         # ติดตั้งอัตโนมัติ + เปิดระบบ
│   └── install_requirements.py # ติดตั้ง Python Dependencies
├── tunnel.py                 # Cloudflare Tunnel
├── start.bat                 # Windows Launcher
└── requirements.txt
```

## การตั้งค่าขั้นสูง

### การใช้งานกับ Facebook Messenger

#### 1. ตั้งค่า Facebook App
- สร้าง Facebook App ที่ developers.facebook.com
- ไปที่ แอพของฉัน > สร้างแอพ

#### 2. ตั้งค่า Webhook
```env
FB_VERIFY_TOKEN=your_custom_token
FB_PAGE_ACCESS_TOKEN=your_page_token
FB_APP_SECRET=your_app_secret
```

#### 3. เริ่ม Cloudflare Tunnel
```bash
python tunnel.py
```

#### 4. ตั้งค่า Webhook URL ใน Facebook
- ไปที่หัวข้อ Messenger > การตั้งค่า Messenger API
- กำหนดค่า Webhooks (URL การเรียกกลับ, ตรวจสอบยืนยันโทเค็น) ใส่ url และ รหัสยืนยัน ที่ได้จาก tunnel.py
- Webhooks (ช่อง Webhooks) กดเปิด messages, messaging_postbacks, messaging_referrals
- กดตรวจสอบการยืนยัน

- Callback URL: https://your-tunnel-url/webhook
- Verify Token: ตามที่ตั้งใน `.env`
- Subscribe to: messages, messaging_postbacks

### การใช้งาน Local LLM (Ollama) - ไม่แนะนำ (ไม่ควรใช้หากไม่จำเป็น)

#### 1. ติดตั้ง Ollama
```bash
# Windows
winget install Ollama.Ollama

# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh
```

#### 2. ดาวน์โหลด Model
```bash
ollama pull iapp/chinda-qwen3-4b
```

#### 3. ตั้งค่า `.env`
```env
LLM_PROVIDER=local
LOCAL_API_KEY=ollama
LOCAL_MODEL_NAME=iapp/chinda-qwen3-4b
LOCAL_BASE_URL=http://localhost:11434/v1
```

### การปรับแต่ง Embedding Model

ระบบจะเลือก Model อัตโนมัติตาม Hardware:
- **CUDA Available**: BAAI/bge-m3 (ประสิทธิภาพสูง)
- **CPU Only**: intfloat/multilingual-e5-small (ประหยัดทรัพยากร)

สำหรับการบังคับใช้ Model เฉพาะ:
```python
# แก้ไขใน backend/app/utils/vector_manager.py
self.model_name = "your-preferred-model"
```

## การแก้ไขปัญหาที่พบบ่อย

### ปัญหา: FFmpeg ไม่พบ
**วิธีแก้:**
```bash
# Windows
winget install ffmpeg

# Linux
sudo apt install ffmpeg

# Mac
brew install ffmpeg
```

### ปัญหา: CUDA Out of Memory
**วิธีแก้:**
- ลดขนาด Batch Size ใน `pdf_to_txt.py`
- ใช้ CPU-based Embedding Model
- ปิดโปรแกรมอื่นที่ใช้ GPU

### ปัญหา: PostgreSQL เชื่อมต่อไม่ได้
**วิธีแก้:**
```bash
# ตรวจสอบว่า PostgreSQL service ทำงานอยู่
# และ DATABASE_URL ใน backend/.env ถูกต้อง
# ตัวอย่าง:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/reg01
```

### ปัญหา: TTS ไม่มีเสียง
**วิธีแก้:**
- ตรวจสอบการเชื่อมต่ออินเทอร์เน็ต (edge-tts ต้องการออนไลน์)
- ตรวจสอบ Browser Audio Permissions
- ลองเปลี่ยน Voice Model ใน `backend/app/tts.py`

## การพัฒนาต่อยอด

### การเพิ่ม Prompt Template ใหม่
สร้างไฟล์ใน `backend/app/prompt/multi_language/`:
```python
request_prompt_xx.py  # xx = รหัสภาษา
```

### การเพิ่ม LLM Provider ใหม่
แก้ไขไฟล์:
- `backend/app/utils/llm/llm_model.py`
- `backend/app/utils/llm/llm.py`

### การเพิ่มฟีเจอร์ใน Admin Dashboard
แก้ไขไฟล์:
- `frontend-next/src/components/admin/*-tab.tsx`
- `frontend-next/src/app/admin/layout.tsx`
- `backend/router/admin_router.py`

## การปรับใช้งานจริง (Production)

### ความปลอดภัย
1. เปลี่ยน `ADMIN_TOKEN` เป็นค่าที่ปลอดภัย
2. ตั้งค่า `ALLOWED_ORIGINS` เฉพาะโดเมนที่ไว้วางใจ
3. ใช้ HTTPS สำหรับการเข้าถึงจากภายนอก
4. ตั้งค่า Rate Limiting
5. ใช้ Environment Variables แทนการเก็บ API Keys ในไฟล์

### Performance Optimization
1. เปิดใช้งาน CUDA สำหรับ Embedding
2. เพิ่ม Workers ใน `uvicorn.run()`
3. ใช้ Redis สำหรับ Session Storage
4. ตั้งค่า Load Balancer
5. ใช้ CDN สำหรับ Static Files

### Monitoring
1. ติดตั้ง Logging System (ELK Stack)
2. ตั้งค่า Health Check Endpoint
3. ใช้ Application Performance Monitoring
4. ตั้งค่า Alert System
5. Backup Database เป็นประจำ

## ข้อมูลเพิ่มเติม

### เอกสารอ้างอิง
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Sentence Transformers](https://www.sbert.net/)

### สิทธิการใช้งาน
โครงการนี้พัฒนาขึ้นสำหรับสำนักทะเบียนมหาวิทยาลัยเชียงใหม่

### ผู้พัฒนา
- Kungwansup Saelee

---

**อัปเดตล่าสุด:** 9 มกราคม 2569  
**สถานะ:** Prototype
