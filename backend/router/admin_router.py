from fastapi import APIRouter, UploadFile, Form, HTTPException, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security.api_key import APIKeyHeader
import os
import json
import shutil
import asyncio
import datetime
import math
import httpx
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

# Import Config จากระบบ
from app.config import PDF_INPUT_FOLDER, PDF_QUICK_USE_FOLDER, BOT_SETTINGS_FILE, SESSION_DIR
from memory.faq_cache import get_faq_analytics
from pdf_to_txt import process_pdfs

# สร้าง Router สำหรับ Admin
router = APIRouter(prefix="/api/admin")

# Security Configuration
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "super-secret-key")
ADMIN_API_KEY_HEADER = APIKeyHeader(name="X-Admin-Token", auto_error=False)
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")

# Executor สำหรับงาน Sync หนักๆ
admin_executor = ThreadPoolExecutor(max_workers=5)

async def verify_admin(auth: str = Depends(ADMIN_API_KEY_HEADER)):
    """ตรวจสอบสิทธิ์ Admin"""
    if auth != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Admin Token")
    return auth

def get_bot_settings():
    if not os.path.exists(BOT_SETTINGS_FILE):
        default = {"facebook": True, "line": True, "web": True}
        with open(BOT_SETTINGS_FILE, "w") as f: json.dump(default, f)
        return default
    with open(BOT_SETTINGS_FILE, "r") as f:
        try: return json.load(f)
        except: return {"facebook": True, "line": True, "web": True}

def save_bot_settings(settings):
    with open(BOT_SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

def get_secure_path(root: str, path: str):
    """แมป Root และตรวจสอบความปลอดภัยของ Path"""
    if root in ["data", "docs"]:
        base_path = PDF_INPUT_FOLDER
    elif root in ["uploads", "quick_use"]:
        base_path = PDF_QUICK_USE_FOLDER
    else:
        base_path = PDF_INPUT_FOLDER
        
    clean_path = path.lstrip("/").replace("..", "")
    target = os.path.abspath(os.path.join(base_path, clean_path))
    
    if not target.startswith(os.path.abspath(base_path)):
        raise HTTPException(status_code=403, detail="Access Denied: Path escape detected")
    return target

def format_size(size_bytes):
    if size_bytes == 0: return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

@router.get("/stats", dependencies=[Depends(verify_admin)])
async def get_stats():
    """ดึงข้อมูล Dashboard Stats"""
    logs = []
    log_path = "logs/user_audit.log"
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                logs = [json.loads(line) for line in lines][-100:]
        except: logs = []
            
    return {
        "recent_logs": logs,
        "faq_analytics": get_faq_analytics(),
        "bot_settings": get_bot_settings(),
        "system_time": datetime.datetime.now().isoformat()
    }

@router.get("/files", dependencies=[Depends(verify_admin)])
async def list_admin_files(root: str = "data", subdir: str = ""):
    if root in ["data", "docs"]: base_path = PDF_INPUT_FOLDER
    else: base_path = PDF_QUICK_USE_FOLDER
    clean_subdir = subdir.lstrip("/").replace("..", "")
    target_dir = os.path.join(base_path, clean_subdir)
    if not os.path.exists(target_dir): os.makedirs(target_dir, exist_ok=True)
    entries = []
    try:
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            is_dir = os.path.isdir(item_path)
            size_val = "N/A"
            try:
                if is_dir: size_val = f"{len(os.listdir(item_path))} items"
                else: size_val = format_size(os.path.getsize(item_path))
            except: pass
            entries.append({
                "name": item, "type": "dir" if is_dir else "file",
                "path": os.path.join(clean_subdir, item).replace("\\", "/"),
                "size": size_val, "ext": "".join(Path(item).suffixes).lower() if not is_dir else ""
            })
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
    return {"root": root, "current_path": clean_subdir, "entries": sorted(entries, key=lambda x: (x["type"] != "dir", x["name"].lower()))}

@router.post("/mkdir", dependencies=[Depends(verify_admin)])
async def create_directory(root: str = Form(...), path: str = Form(...), name: str = Form(...)):
    target = os.path.join(get_secure_path(root, path), name)
    os.makedirs(target, exist_ok=True)
    return {"status": "success"}

@router.post("/rename", dependencies=[Depends(verify_admin)])
async def rename_item(root: str = Form(...), old_path: str = Form(...), new_name: str = Form(...)):
    old_target = get_secure_path(root, old_path)
    new_target = os.path.join(os.path.dirname(old_target), new_name)
    if os.path.exists(new_target): raise HTTPException(status_code=400, detail="Name already exists")
    os.rename(old_target, new_target)
    return {"status": "success"}

@router.post("/move", dependencies=[Depends(verify_admin)])
async def move_items(root: str = Form(...), src_paths: str = Form(...), dest_dir: str = Form(...)):
    paths = json.loads(src_paths)
    base_dest = get_secure_path(root, dest_dir)
    os.makedirs(base_dest, exist_ok=True)
    for p in paths:
        src = get_secure_path(root, p)
        shutil.move(src, os.path.join(base_dest, os.path.basename(src)))
    return {"status": "success"}

@router.get("/view", dependencies=[Depends(verify_admin)])
async def preview_file(root: str, path: str):
    target = get_secure_path(root, path)
    if not os.path.exists(target) or os.path.isdir(target): raise HTTPException(status_code=404, detail="File not found")
    ext = target.lower()
    mime = "application/pdf" if ext.endswith(".pdf") else "text/plain"
    return FileResponse(target, media_type=mime)

@router.post("/edit", dependencies=[Depends(verify_admin)])
async def edit_file(root: str = Form(...), path: str = Form(...), content: str = Form(...)):
    target = get_secure_path(root, path)
    with open(target, "w", encoding="utf-8") as f: f.write(content)
    return {"status": "success"}

@router.post("/upload", dependencies=[Depends(verify_admin)])
async def upload_document(file: UploadFile, target_dir: str = Form(""), root: str = Form("data")):
    dest_folder = get_secure_path(root, target_dir)
    os.makedirs(dest_folder, exist_ok=True)
    file_path = os.path.join(dest_folder, file.filename)
    with open(file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    return {"status": "success"}

@router.post("/process-rag", dependencies=[Depends(verify_admin)])
async def trigger_rag_process():
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(admin_executor, process_pdfs)
        return {"status": "completed"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.delete("/files", dependencies=[Depends(verify_admin)])
async def delete_items(root: str, paths: str):
    path_list = json.loads(paths)
    for path in path_list:
        target = get_secure_path(root, path)
        if os.path.exists(target):
            if os.path.isdir(target): shutil.rmtree(target)
            else: os.remove(target)
    return {"status": "deleted"}

# ----------------------------------------------------------------------------- #
# CHAT & BOT CONTROL ENDPOINTS
# ----------------------------------------------------------------------------- #

@router.post("/bot-toggle", dependencies=[Depends(verify_admin)])
async def toggle_bot(platform: str = Form(...), status: bool = Form(...)):
    """สลับสถานะเปิด/ปิด Bot"""
    settings = get_bot_settings()
    settings[platform] = status
    save_bot_settings(settings)
    return {"status": "success", "settings": settings}

@router.get("/chat/sessions", dependencies=[Depends(verify_admin)])
async def get_chat_sessions():
    """ดึงรายชื่อ Session การแชทล่าสุด โดยอ่าน metadata จากไฟล์โดยตรง"""
    sessions = []
    if not os.path.exists(SESSION_DIR): return []
    
    for filename in os.listdir(SESSION_DIR):
        if filename.endswith(".json"):
            path = os.path.join(SESSION_DIR, filename)
            try:
                mtime = os.path.getmtime(path)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    uid = filename.replace(".json", "").replace("fb_", "")
                    
                    # ตรวจสอบโครงสร้างไฟล์ (New: Dict with user_info, Old: List)
                    if isinstance(data, dict) and "user_info" in data:
                        info = data["user_info"]
                        sessions.append({
                            "id": uid, 
                            "platform": info.get("platform", "web"), 
                            "profile": info, 
                            "last_active": mtime
                        })
                    else:
                        is_fb = filename.startswith("fb_")
                        sessions.append({
                            "id": uid, 
                            "platform": "facebook" if is_fb else "web", 
                            "profile": {"name": f"User {uid[:5]}", "picture": "https://www.gravatar.com/avatar/?d=mp"}, 
                            "last_active": mtime
                        })
            except: pass
    
    return sorted(sessions, key=lambda x: x["last_active"], reverse=True)

@router.get("/chat/history/{platform}/{uid}", dependencies=[Depends(verify_admin)])
async def get_chat_history(platform: str, uid: str):
    """ดึงประวัติการแชทรายคน"""
    filename = f"fb_{uid}.json" if platform == "facebook" else f"{uid}.json"
    path = os.path.join(SESSION_DIR, filename)
    if not os.path.exists(path): return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data.get("history", [])
            return data # Case เก่าที่เป็น list
    except: return []

@router.post("/chat/send", dependencies=[Depends(verify_admin)])
async def admin_send_message(platform: str = Form(...), uid: str = Form(...), message: str = Form(...)):
    """Admin ส่งข้อความตอบกลับด้วยตนเอง (API Proxy)"""
    return {"status": "success", "platform": platform, "uid": uid}