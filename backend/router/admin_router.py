from fastapi import APIRouter, UploadFile, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.security.api_key import APIKeyHeader
import os
import json
import shutil
import asyncio
import datetime
import math
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

# Import Config จากระบบ
from app.config import PDF_INPUT_FOLDER, PDF_QUICK_USE_FOLDER
from memory.faq_cache import get_faq_analytics
from pdf_to_txt import process_pdfs

# สร้าง Router สำหรับ Admin
router = APIRouter(prefix="/api/admin")

# Security Configuration
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "super-secret-key")
ADMIN_API_KEY_HEADER = APIKeyHeader(name="X-Admin-Token", auto_error=False)

# Executor สำหรับงาน Sync หนักๆ
admin_executor = ThreadPoolExecutor(max_workers=5)

async def verify_admin(auth: str = Depends(ADMIN_API_KEY_HEADER)):
    """ตรวจสอบสิทธิ์ Admin"""
    if auth != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Admin Token")
    return auth

def get_secure_path(root: str, path: str):
    """แมป Root และตรวจสอบความปลอดภัยของ Path"""
    # Mapping Root จากหน้าบ้านให้ตรงกับ Config
    if root in ["data", "docs"]:
        base_path = PDF_INPUT_FOLDER
    elif root in ["uploads", "quick_use"]:
        base_path = PDF_QUICK_USE_FOLDER
    else:
        base_path = PDF_INPUT_FOLDER
        
    clean_path = path.lstrip("/").replace("..", "")
    target = os.path.abspath(os.path.join(base_path, clean_path))
    
    # ป้องกัน Directory Traversal
    if not target.startswith(os.path.abspath(base_path)):
        raise HTTPException(status_code=403, detail="Access Denied: Path escape detected")
    return target

def format_size(size_bytes):
    """แปลงขนาดไฟล์เป็นหน่วยที่อ่านง่าย"""
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
    # ตรวจสอบ Path ของ Log File
    log_path = os.path.abspath(os.path.join(os.getcwd(), "..", "logs", "user_audit.log"))
    if not os.path.exists(log_path):
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
async def list_admin_files(root: str = "data", subdir: str = ""):
    """รายการไฟล์และโฟลเดอร์แบบละเอียด"""
    if root in ["data", "docs"]:
        base_path = PDF_INPUT_FOLDER
    else:
        base_path = PDF_QUICK_USE_FOLDER
        
    clean_subdir = subdir.lstrip("/").replace("..", "")
    target_dir = os.path.join(base_path, clean_subdir)
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        
    entries = []
    try:
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            is_dir = os.path.isdir(item_path)
            
            size_val = "N/A"
            try:
                if is_dir:
                    size_val = f"{len(os.listdir(item_path))} items"
                else:
                    size_val = format_size(os.path.getsize(item_path))
            except: pass

            entries.append({
                "name": item,
                "type": "dir" if is_dir else "file",
                "path": os.path.join(clean_subdir, item).replace("\\", "/"),
                "size": size_val,
                "ext": "".join(Path(item).suffixes).lower() if not is_dir else ""
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return {
        "root": root,
        "current_path": clean_subdir,
        "entries": sorted(entries, key=lambda x: (x["type"] != "dir", x["name"].lower()))
    }

@router.post("/mkdir", dependencies=[Depends(verify_admin)])
async def create_directory(root: str = Form(...), path: str = Form(...), name: str = Form(...)):
    """สร้างโฟลเดอร์ใหม่"""
    target = os.path.join(get_secure_path(root, path), name)
    os.makedirs(target, exist_ok=True)
    return {"status": "success"}

@router.post("/rename", dependencies=[Depends(verify_admin)])
async def rename_item(root: str = Form(...), old_path: str = Form(...), new_name: str = Form(...)):
    """เปลี่ยนชื่อไฟล์/โฟลเดอร์"""
    old_target = get_secure_path(root, old_path)
    new_target = os.path.join(os.path.dirname(old_target), new_name)
    if os.path.exists(new_target):
        raise HTTPException(status_code=400, detail="Name already exists")
    os.rename(old_target, new_target)
    return {"status": "success"}

@router.post("/move", dependencies=[Depends(verify_admin)])
async def move_items(root: str = Form(...), src_paths: str = Form(...), dest_dir: str = Form(...)):
    """ย้ายไฟล์/โฟลเดอร์"""
    paths = json.loads(src_paths)
    base_dest = get_secure_path(root, dest_dir)
    os.makedirs(base_dest, exist_ok=True)
    
    for p in paths:
        src = get_secure_path(root, p)
        shutil.move(src, os.path.join(base_dest, os.path.basename(src)))
    return {"status": "success"}

@router.get("/view", dependencies=[Depends(verify_admin)])
async def preview_file(root: str, path: str):
    """ส่งคืนไฟล์เพื่อ Preview"""
    target = get_secure_path(root, path)
    if not os.path.exists(target) or os.path.isdir(target):
        raise HTTPException(status_code=404, detail="File not found")
    
    ext = target.lower()
    mime = "application/pdf" if ext.endswith(".pdf") else "text/plain"
    return FileResponse(target, media_type=mime)

@router.post("/edit", dependencies=[Depends(verify_admin)])
async def edit_file(root: str = Form(...), path: str = Form(...), content: str = Form(...)):
    """แก้ไขไฟล์ TXT"""
    target = get_secure_path(root, path)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "success"}

@router.post("/upload", dependencies=[Depends(verify_admin)])
async def upload_document(file: UploadFile, target_dir: str = Form(""), root: str = Form("data")):
    """อัปโหลดไฟล์"""
    dest_folder = get_secure_path(root, target_dir)
    os.makedirs(dest_folder, exist_ok=True)
    file_path = os.path.join(dest_folder, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "success"}

@router.post("/process-rag", dependencies=[Depends(verify_admin)])
async def trigger_rag_process():
    """สั่ง Sync RAG (PDF -> TXT)"""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(admin_executor, process_pdfs)
        return {"status": "completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/files", dependencies=[Depends(verify_admin)])
async def delete_items(root: str, paths: str):
    """ลบไฟล์/โฟลเดอร์แบบกลุ่ม"""
    path_list = json.loads(paths)
    for path in path_list:
        target = get_secure_path(root, path)
        if os.path.exists(target):
            if os.path.isdir(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
    return {"status": "deleted"}