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

def get_secure_path(root: str, path: str):
    """สร้าง Path ที่ปลอดภัยและตรวจสอบการพยายามออกนอก Directory"""
    base_path = PDF_INPUT_FOLDER if root == "docs" else PDF_QUICK_USE_FOLDER
    clean_path = path.lstrip("/").replace("..", "")
    target = os.path.normpath(os.path.join(base_path, clean_path))
    if not target.startswith(os.path.abspath(base_path)):
        raise HTTPException(status_code=403, detail="Access Denied: Path escape detected")
    return target

@router.get("/stats", dependencies=[Depends(verify_admin)])
async def get_stats():
    """ดึงข้อมูลสถิติและประวัติล่าสุด"""
    logs = []
    log_path = "logs/user_audit.log"
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                logs = [json.loads(line) for line in lines][-100:]
        except:
            logs = []
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

@router.post("/mkdir", dependencies=[Depends(verify_admin)])
async def create_directory(root: str = Form(...), path: str = Form(...), name: str = Form(...)):
    """สร้างโฟลเดอร์ใหม่"""
    target = os.path.join(get_secure_path(root, path), name)
    try:
        os.makedirs(target, exist_ok=True)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rename", dependencies=[Depends(verify_admin)])
async def rename_item(root: str = Form(...), old_path: str = Form(...), new_name: str = Form(...)):
    """เปลี่ยนชื่อไฟล์หรือโฟลเดอร์"""
    old_target = get_secure_path(root, old_path)
    parent_dir = os.path.dirname(old_target)
    new_target = os.path.join(parent_dir, new_name)
    
    if os.path.exists(new_target):
        raise HTTPException(status_code=400, detail="Name already exists")
    
    try:
        os.rename(old_target, new_target)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/move", dependencies=[Depends(verify_admin)])
async def move_items(root: str = Form(...), src_paths: str = Form(...), dest_dir: str = Form(...)):
    """ย้ายไฟล์หรือโฟลเดอร์ (รองรับแบบกลุ่มผ่าน JSON string ของ list)"""
    paths = json.loads(src_paths)
    base_dest = get_secure_path(root, dest_dir)
    
    moved = []
    errors = []
    for p in paths:
        src = get_secure_path(root, p)
        dest = os.path.join(base_dest, os.path.basename(src))
        try:
            shutil.move(src, dest)
            moved.append(p)
        except Exception as e:
            errors.append({"path": p, "error": str(e)})
            
    return {"status": "completed", "moved": moved, "errors": errors}

@router.get("/view", dependencies=[Depends(verify_admin)])
async def preview_file(root: str, path: str):
    """ส่งคืนไฟล์สำหรับการพรีวิว (PDF/TXT)"""
    target = get_secure_path(root, path)
    if not os.path.exists(target) or os.path.isdir(target):
        raise HTTPException(status_code=404, detail="File not found")
    mime_type = "application/pdf" if target.lower().endswith(".pdf") else "text/plain"
    return FileResponse(target, media_type=mime_type)

@router.post("/edit", dependencies=[Depends(verify_admin)])
async def edit_file(root: str = Form(...), path: str = Form(...), content: str = Form(...)):
    """แก้ไขเนื้อหาไฟล์ TXT"""
    target = get_secure_path(root, path)
    if not os.path.exists(target) or os.path.isdir(target) or not target.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Invalid file type or path")
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "success"}

@router.post("/upload", dependencies=[Depends(verify_admin)])
async def upload_document(file: UploadFile, target_dir: str = Form("")):
    """อัปโหลดไฟล์ใหม่"""
    if not (file.filename.lower().endswith(".pdf") or file.filename.lower().endswith(".txt")):
        raise HTTPException(status_code=400, detail="Only PDF or TXT allowed")
    
    dest_folder = get_secure_path("docs", target_dir) # อัปโหลดเข้า docs เสมอเพื่อรอ Process
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
async def delete_items(root: str, paths: str):
    """ลบไฟล์หรือโฟลเดอร์ (รองรับแบบกลุ่มผ่าน JSON string ของ list)"""
    path_list = json.loads(paths)
    deleted = []
    for path in path_list:
        target = get_secure_path(root, path)
        if os.path.exists(target):
            if os.path.isdir(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
            deleted.append(path)
    return {"status": "deleted", "count": len(deleted)}