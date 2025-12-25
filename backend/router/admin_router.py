from fastapi import APIRouter, UploadFile, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.security.api_key import APIKeyHeader
import os
import json
import shutil
import asyncio
import datetime
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from app.config import PDF_INPUT_FOLDER, PDF_QUICK_USE_FOLDER
from memory.faq_cache import get_faq_analytics
from pdf_to_txt import process_pdfs

# สร้าง Router สำหรับ Admin
router = APIRouter(prefix="/api/admin")

# Configuration & Security
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "super-secret-key")
ADMIN_API_KEY_HEADER = APIKeyHeader(name="X-Admin-Token", auto_error=False)

# ThreadPoolExecutor สำหรับงานหนัก (RAG Processing)
admin_executor = ThreadPoolExecutor(max_workers=5)

async def verify_admin(auth: str = Depends(ADMIN_API_KEY_HEADER)):
    """ตรวจสอบความถูกต้องของ Admin Token"""
    if auth != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Admin Token")
    return auth

@router.get("/stats", dependencies=[Depends(verify_admin)])
async def get_stats():
    """ดึงข้อมูลสถิติและประวัติล่าสุด"""
    logs = []
    log_path = "logs/user_audit.log"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            logs = [json.loads(line) for line in f.readlines()][-100:]
    return {
        "recent_logs": logs,
        "faq_analytics": get_faq_analytics(),
        "system_time": datetime.datetime.now().isoformat()
    }

@router.get("/files", dependencies=[Depends(verify_admin)])
async def list_admin_files(root: str = "docs", subdir: str = ""):
    """รายการไฟล์และโฟลเดอร์แบบโครงสร้าง"""
    base_path = PDF_INPUT_FOLDER if root == "docs" else PDF_QUICK_USE_FOLDER
    clean_subdir = subdir.lstrip("/").replace("..", "")
    target_dir = os.path.join(base_path, clean_subdir)
    
    if not os.path.exists(target_dir):
        return {"root": root, "entries": [], "current_path": clean_subdir}
        
    entries = []
    for item in os.listdir(target_dir):
        item_path = os.path.join(target_dir, item)
        is_dir = os.path.isdir(item_path)
        rel_path = os.path.join(clean_subdir, item).replace("\\", "/")
        entries.append({
            "name": item,
            "is_dir": is_dir,
            "path": rel_path,
            "ext": "".join(Path(item).suffixes).lower() if not is_dir else ""
        })
    return {
        "root": root,
        "current_path": clean_subdir,
        "entries": sorted(entries, key=lambda x: (not x["is_dir"], x["name"].lower()))
    }

@router.get("/view", dependencies=[Depends(verify_admin)])
async def preview_file(root: str, path: str):
    """ส่งคืนไฟล์สำหรับการพรีวิว (PDF/TXT)"""
    base_path = PDF_INPUT_FOLDER if root == "docs" else PDF_QUICK_USE_FOLDER
    target = os.path.join(base_path, path.lstrip("/").replace("..", ""))
    
    if not os.path.exists(target) or os.path.isdir(target):
        raise HTTPException(status_code=404, detail="File not found")
        
    mime_type = "application/pdf" if target.lower().endswith(".pdf") else "text/plain"
    return FileResponse(target, media_type=mime_type)

@router.post("/edit", dependencies=[Depends(verify_admin)])
async def edit_file(root: str = Form(...), path: str = Form(...), content: str = Form(...)):
    """แก้ไขเนื้อหาไฟล์ TXT"""
    base_path = PDF_INPUT_FOLDER if root == "docs" else PDF_QUICK_USE_FOLDER
    target = os.path.join(base_path, path.lstrip("/").replace("..", ""))
    
    if not os.path.exists(target) or os.path.isdir(target) or not target.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Invalid file type or path")
        
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "success"}

@router.post("/upload", dependencies=[Depends(verify_admin)])
async def upload_document(file: UploadFile, target_dir: str = Form("")):
    """อัปโหลดไฟล์ใหม่ รองรับ Folder Structure"""
    if not (file.filename.lower().endswith(".pdf") or file.filename.lower().endswith(".txt")):
        raise HTTPException(status_code=400, detail="Only PDF or TXT allowed")
    
    clean_dir = target_dir.lstrip("/").replace("..", "")
    dest_folder = os.path.join(PDF_INPUT_FOLDER, clean_dir)
    os.makedirs(dest_folder, exist_ok=True)
    
    safe_name = "".join([c for c in file.filename if c.isalnum() or c in ('.', '_', '-', '/')]).strip()
    file_path = os.path.join(dest_folder, os.path.basename(safe_name))
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "success"}

@router.post("/process-rag", dependencies=[Depends(verify_admin)])
async def trigger_rag_process():
    """สั่งประมวลผล PDF to TXT"""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(admin_executor, process_pdfs)
        return {"status": "completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/files", dependencies=[Depends(verify_admin)])
async def delete_item(root: str, path: str):
    """ลบไฟล์หรือโฟลเดอร์"""
    base_path = PDF_INPUT_FOLDER if root == "docs" else PDF_QUICK_USE_FOLDER
    target = os.path.join(base_path, path.lstrip("/").replace("..", ""))
    
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="Not found")
        
    if os.path.isdir(target):
        shutil.rmtree(target)
    else:
        os.remove(target)
    return {"status": "deleted"}