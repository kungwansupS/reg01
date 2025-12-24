import sys
import os
import subprocess
import logging
import uvicorn
import time
import re
from dotenv import load_dotenv

# Path Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

from backend.main import asgi_app
from backend.app.config import HOST, PORT
from backend.pdf_to_txt import process_pdfs

load_dotenv(os.path.join(BACKEND_DIR, ".env"))
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def start_tunnel():
    """ฟังก์ชันรัน Cloudflare Tunnel ตามโหมดที่เลือก"""
    use_quick = os.getenv("USE_QUICK_TUNNEL", "false").lower() == "true"
    
    try:
        subprocess.run(["cloudflared", "--version"], check=True, capture_output=True)
        
        if use_quick:
            logging.info("⚡ กำลังสร้าง Quick Tunnel (TryCloudflare)...")
            # รันและดึง Output เพื่อหา URL
            process = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{PORT}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # วนลูปหา URL ใน Logs ของ Cloudflare
            for line in process.stdout:
                if ".trycloudflare.com" in line:
                    match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                    if match:
                        url = match.group(0)
                        print("\n" + "="*60)
                        print(f"🔗 ลิงค์ Webhook ของคุณคือ: {url}/webhook")
                        print(f"🔑 อย่าลืมตั้ง Verify Token เป็น: {os.getenv('FB_VERIFY_TOKEN')}")
                        print("="*60 + "\n")
                        break
        else:
            tunnel_name = os.getenv("CLOUDFLARE_TUNNEL_NAME")
            if tunnel_name:
                logging.info(f"🌐 กำลังเปิด Named Tunnel: {tunnel_name}...")
                subprocess.Popen(["cloudflared", "tunnel", "run", tunnel_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                logging.warning("⚠️ ไม่พบการตั้งค่า Tunnel ระบบจะรันแบบ Local")

    except Exception as e:
        logging.error(f"❌ ไม่สามารถเริ่ม Tunnel ได้: {e}")

if __name__ == "__main__":
    logging.info("🚀 เริ่มต้นการรันระบบ REG-01...")
    process_pdfs()
    start_tunnel()
    logging.info(f"📡 ASGI Server รันที่พอร์ต {PORT}")
    uvicorn.run(asgi_app, host=HOST, port=PORT, workers=1, reload=False)