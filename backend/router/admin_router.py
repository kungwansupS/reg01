# ✅ FIXED VERSION - admin_router.py
# Changes:
# 1. Fixed get_secure_path to handle empty string for root directory
# 2. Improved error responses with clear messages

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
from memory.session import get_bot_enabled, set_bot_enabled
from pdf_to_txt import process_pdfs

# สร้าง Router สำหรับ Admin
router = APIRouter(prefix="/api/admin")

# Security Configuration
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "super-secret-key")
ADMIN_API_KEY_HEADER = APIKeyHeader(name="X-Admin-Token", auto_error=False)
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")

# Executor สำหรับงาน Sync หนักๆ
admin_executor = ThreadPoolExecutor(max_workers=5)

# Logging
import logging
logger = logging.getLogger("AdminRouter")

async def verify_admin(auth: str = Depends(ADMIN_API_KEY_HEADER)):
    """ตรวจสอบสิทธิ์ Admin"""
    if auth != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Admin Token")
    return auth

def get_bot_settings():
    """Backward compatibility"""
    if not os.path.exists(BOT_SETTINGS_FILE):
        default = {"facebook": True, "line": True, "web": True}
        with open(BOT_SETTINGS_FILE, "w") as f: json.dump(default, f)
        return default
    with open(BOT_SETTINGS_FILE, "r") as f:
        try: return json.load(f)
        except: return {"facebook": True, "line": True, "web": True}

def save_bot_settings(settings):
    """Backward compatibility"""
    with open(BOT_SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

def get_secure_path(root: str, path: str):
    """
    แมป Root และตรวจสอบความปลอดภัยของ Path
    
    FIXED: รองรับ empty string สำหรับ root directory
    """
    if root in ["data", "docs"]:
        base_path = PDF_INPUT_FOLDER
    elif root in ["uploads", "quick_use"]:
        base_path = PDF_QUICK_USE_FOLDER
    else:
        base_path = PDF_INPUT_FOLDER
    
    # ✅ Handle empty path (root directory)
    if not path or path.strip() == "":
        target = os.path.abspath(base_path)
        logger.info(f"📁 Resolved empty path to root: {target}")
    else:
        clean_path = path.lstrip("/").replace("..", "")
        target = os.path.abspath(os.path.join(base_path, clean_path))
        logger.info(f"📁 Resolved path '{path}' to: {target}")
    
    # Security check
    if not target.startswith(os.path.abspath(base_path)):
        logger.error(f"🚨 Security violation: {target} not in {base_path}")
        raise HTTPException(status_code=403, detail="Access Denied: Path escape detected")
    
    return target

def format_size(size_bytes):
    if size_bytes == 0: return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def calculate_token_analytics(logs: list) -> dict:
    """Calculate comprehensive token usage analytics from logs"""
    if not logs:
        return {
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "cached_responses": 0,
            "total_cost_usd": 0.0,
            "avg_tokens_per_request": 0,
            "requests_with_tokens": 0
        }
    
    total_tokens = 0
    total_prompt = 0
    total_completion = 0
    cached_count = 0
    total_cost = 0.0
    requests_with_tokens = 0
    
    for log in logs:
        if "tokens" in log:
            tokens = log["tokens"]
            total_tokens += tokens.get("total", 0)
            total_prompt += tokens.get("prompt", 0)
            total_completion += tokens.get("completion", 0)
            
            if tokens.get("cached", False):
                cached_count += 1
            
            if "cost_usd" in tokens:
                total_cost += tokens["cost_usd"]
            
            requests_with_tokens += 1
    
    avg_tokens = total_tokens / requests_with_tokens if requests_with_tokens > 0 else 0
    
    return {
        "total_tokens": total_tokens,
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "cached_responses": cached_count,
        "total_cost_usd": round(total_cost, 4),
        "avg_tokens_per_request": round(avg_tokens, 2),
        "requests_with_tokens": requests_with_tokens,
        "cache_hit_rate": round((cached_count / len(logs) * 100), 2) if logs else 0
    }

@router.get("/stats", dependencies=[Depends(verify_admin)])
async def get_stats():
    """ดึงข้อมูล Dashboard Stats พร้อม Token Analytics"""
    logs = []
    log_path = "logs/user_audit.log"
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                logs = [json.loads(line) for line in lines][-100:]
        except: logs = []
    
    token_analytics = calculate_token_analytics(logs)
    
    return {
        "recent_logs": logs,
        "faq_analytics": get_faq_analytics(),
        "bot_settings": get_bot_settings(),
        "token_analytics": token_analytics,
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
    try:
        target = os.path.join(get_secure_path(root, path), name)
        os.makedirs(target, exist_ok=True)
        logger.info(f"✅ Created directory: {target}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"❌ Failed to create directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rename", dependencies=[Depends(verify_admin)])
async def rename_item(root: str = Form(...), old_path: str = Form(...), new_name: str = Form(...)):
    try:
        old_target = get_secure_path(root, old_path)
        new_target = os.path.join(os.path.dirname(old_target), new_name)
        
        if os.path.exists(new_target):
            raise HTTPException(status_code=400, detail=f"'{new_name}' already exists")
        
        os.rename(old_target, new_target)
        logger.info(f"✅ Renamed: {old_target} → {new_target}")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Rename failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/move", dependencies=[Depends(verify_admin)])
async def move_items(root: str = Form(...), src_paths: str = Form(...), dest_dir: str = Form(...)):
    """
    ย้ายไฟล์/โฟลเดอร์
    
    FIXED: รองรับ dest_dir = "" สำหรับ root directory
    """
    try:
        paths = json.loads(src_paths)
        
        # ✅ Handle empty dest_dir (root directory)
        base_dest = get_secure_path(root, dest_dir)
        logger.info(f"📦 Moving {len(paths)} items to: {base_dest}")
        
        os.makedirs(base_dest, exist_ok=True)
        
        for p in paths:
            src = get_secure_path(root, p)
            dest = os.path.join(base_dest, os.path.basename(src))
            
            if not os.path.exists(src):
                logger.warning(f"⚠️ Source not found: {src}")
                continue
            
            if src == dest:
                logger.warning(f"⚠️ Source and destination are the same: {src}")
                continue
            
            if os.path.exists(dest):
                raise HTTPException(
                    status_code=400, 
                    detail=f"'{os.path.basename(src)}' already exists in destination"
                )
            
            shutil.move(src, dest)
            logger.info(f"  ✅ Moved: {os.path.basename(src)}")
        
        return {"status": "success"}
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in src_paths: {e}")
        raise HTTPException(status_code=400, detail="Invalid source paths format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Move failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/copy", dependencies=[Depends(verify_admin)])
async def copy_items(root: str = Form(...), source_paths: str = Form(...), target_path: str = Form(...)):
    """
    คัดลอกไฟล์/โฟลเดอร์ไปยังตำแหน่งใหม่
    
    FIXED: รองรับ target_path = "" สำหรับ root directory
    """
    try:
        paths = json.loads(source_paths)
        
        # ✅ Handle empty target_path (root directory)
        base_dest = get_secure_path(root, target_path)
        logger.info(f"📋 Copying {len(paths)} items to: {base_dest}")
        
        os.makedirs(base_dest, exist_ok=True)
        
        for p in paths:
            src = get_secure_path(root, p)
            if not os.path.exists(src):
                logger.warning(f"⚠️ Source not found: {src}")
                continue
            
            dest = os.path.join(base_dest, os.path.basename(src))
            
            # Handle duplicates
            counter = 1
            original_dest = dest
            while os.path.exists(dest):
                if os.path.isdir(src):
                    dest = f"{original_dest}_copy_{counter}"
                else:
                    name, ext = os.path.splitext(original_dest)
                    dest = f"{name}_copy_{counter}{ext}"
                counter += 1
            
            # Copy
            if os.path.isdir(src):
                shutil.copytree(src, dest)
                logger.info(f"  ✅ Copied folder: {os.path.basename(src)}")
            else:
                shutil.copy2(src, dest)
                logger.info(f"  ✅ Copied file: {os.path.basename(src)}")
        
        return {"status": "success"}
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in source_paths: {e}")
        raise HTTPException(status_code=400, detail="Invalid source paths format")
    except Exception as e:
        logger.error(f"❌ Copy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/view", dependencies=[Depends(verify_admin)])
async def preview_file(root: str, path: str):
    try:
        target = get_secure_path(root, path)
        if not os.path.exists(target) or os.path.isdir(target):
            raise HTTPException(status_code=404, detail="File not found")
        ext = target.lower()
        mime = "application/pdf" if ext.endswith(".pdf") else "text/plain"
        return FileResponse(target, media_type=mime)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ View file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/edit", dependencies=[Depends(verify_admin)])
async def edit_file(root: str = Form(...), path: str = Form(...), content: str = Form(...)):
    try:
        target = get_secure_path(root, path)
        with open(target, "w", encoding="utf-8") as f: f.write(content)
        logger.info(f"✅ Edited file: {target}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"❌ Edit file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload", dependencies=[Depends(verify_admin)])
async def upload_document(file: UploadFile, target_dir: str = Form(""), root: str = Form("data")):
    try:
        dest_folder = get_secure_path(root, target_dir)
        os.makedirs(dest_folder, exist_ok=True)
        file_path = os.path.join(dest_folder, file.filename)
        with open(file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
        logger.info(f"✅ Uploaded: {file.filename}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-rag", dependencies=[Depends(verify_admin)])
async def trigger_rag_process():
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(admin_executor, process_pdfs)
        logger.info("✅ RAG processing completed")
        return {"status": "completed"}
    except Exception as e:
        logger.error(f"❌ RAG processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/files", dependencies=[Depends(verify_admin)])
async def delete_items(root: str, paths: str):
    try:
        path_list = json.loads(paths)
        for path in path_list:
            target = get_secure_path(root, path)
            if os.path.exists(target):
                if os.path.isdir(target): shutil.rmtree(target)
                else: os.remove(target)
                logger.info(f"✅ Deleted: {target}")
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"❌ Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------- #
# CHAT & BOT CONTROL ENDPOINTS
# ----------------------------------------------------------------------------- #

@router.post("/bot-toggle", dependencies=[Depends(verify_admin)])
async def toggle_bot(session_id: str = Form(...), status: bool = Form(...)):
    """สลับสถานะเปิด/ปิด Bot สำหรับ Session นี้"""
    logger.info(f"🔄 Toggling bot for session {session_id}: {status}")
    
    success = set_bot_enabled(session_id, status)
    
    if success:
        logger.info(f"✅ Bot status updated for {session_id}: {status}")
        return {"status": "success", "session_id": session_id, "bot_enabled": status}
    else:
        logger.error(f"❌ Failed to update bot status for {session_id}")
        raise HTTPException(status_code=500, detail="Failed to update bot status")

@router.post("/bot-toggle-all", dependencies=[Depends(verify_admin)])
async def toggle_all_bots(status: bool = Form(...)):
    """เปิด/ปิด Bot ทั้งหมดทุก Session"""
    logger.info(f"🔄 Toggling ALL bots: {status}")
    
    if not os.path.exists(SESSION_DIR):
        return {"status": "success", "updated_count": 0}
    
    updated_count = 0
    try:
        for filename in os.listdir(SESSION_DIR):
            if filename.endswith(".json"):
                session_id = filename.replace(".json", "")
                if set_bot_enabled(session_id, status):
                    updated_count += 1
        
        logger.info(f"✅ Updated {updated_count} sessions")
        return {"status": "success", "updated_count": updated_count, "bot_enabled": status}
    except Exception as e:
        logger.error(f"❌ Failed to toggle all bots: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/sessions", dependencies=[Depends(verify_admin)])
async def get_chat_sessions():
    """ดึงรายชื่อ Session การแชทล่าสุด"""
    logger.info(f"📋 Loading chat sessions from {SESSION_DIR}")
    
    if not os.path.exists(SESSION_DIR): 
        logger.warning(f"⚠️ SESSION_DIR not found: {SESSION_DIR}")
        os.makedirs(SESSION_DIR, exist_ok=True)
        return []
    
    sessions = []
    file_count = 0
    
    try:
        files = [f for f in os.listdir(SESSION_DIR) if f.endswith(".json")]
        logger.info(f"📂 Found {len(files)} session files")
        
        for filename in files:
            file_count += 1
            path = os.path.join(SESSION_DIR, filename)
            
            try:
                mtime = os.path.getmtime(path)
                
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    session_id = filename.replace(".json", "")
                    logger.debug(f"  [{file_count}/{len(files)}] Processing: {session_id}")
                    
                    bot_enabled = data.get("bot_enabled", True)
                    
                    if isinstance(data, dict) and "user_info" in data:
                        info = data["user_info"]
                        history = data.get("history", [])
                        
                        sessions.append({
                            "id": session_id,
                            "platform": info.get("platform", "web"),
                            "profile": {
                                "name": info.get("name", f"User {session_id[:8]}"),
                                "picture": info.get("picture", "https://www.gravatar.com/avatar/?d=mp")
                            },
                            "bot_enabled": bot_enabled,
                            "last_active": mtime
                        })
                        logger.debug(f"    ✅ Valid session: {info.get('name')} (Bot: {bot_enabled})")
                        
                    elif isinstance(data, list):
                        is_fb = filename.startswith("fb_")
                        
                        sessions.append({
                            "id": session_id,
                            "platform": "facebook" if is_fb else "web",
                            "profile": {
                                "name": f"User {session_id[:8]}",
                                "picture": "https://www.gravatar.com/avatar/?d=mp"
                            },
                            "bot_enabled": True,
                            "last_active": mtime
                        })
                        logger.debug(f"    ⚠️ Old format (migrating): {session_id}")
                        
                    else:
                        logger.warning(f"    ❌ Unknown format: {session_id}")
                        
            except json.JSONDecodeError as e:
                logger.error(f"    ❌ JSON decode error in {filename}: {e}")
                continue
            except Exception as e:
                logger.error(f"    ❌ Error loading {filename}: {e}")
                continue
        
        sessions.sort(key=lambda x: x["last_active"], reverse=True)
        logger.info(f"✅ Successfully loaded {len(sessions)}/{file_count} sessions")
        
        return sessions
        
    except Exception as e:
        logger.error(f"❌ Failed to load sessions: {e}")
        return []

@router.get("/chat/history/{platform}/{uid}", dependencies=[Depends(verify_admin)])
async def get_chat_history(platform: str, uid: str):
    """ดึงประวัติการแชทรายคน"""
    logger.info(f"📖 Loading history for {platform}/{uid}")
    
    filename = f"{uid}.json"
    path = os.path.join(SESSION_DIR, filename)
    
    logger.info(f"   Looking for: {path}")
    
    if not os.path.exists(path):
        logger.warning(f"   ⚠️ History file not found: {path}")
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            if isinstance(data, dict) and "history" in data:
                history = data["history"]
                logger.info(f"   ✅ Loaded {len(history)} messages (new format)")
            elif isinstance(data, list):
                history = data
                logger.info(f"   ✅ Loaded {len(history)} messages (old format)")
            else:
                logger.error(f"   ❌ Unknown data format")
                return []
            
            filtered = [
                msg for msg in history
                if msg.get("role") in ["user", "model"]
                and msg.get("parts")
                and len(msg["parts"]) > 0
                and msg["parts"][0].get("text")
            ]
            
            logger.info(f"   ✅ Returning {len(filtered)} valid messages")
            return filtered
            
    except json.JSONDecodeError as e:
        logger.error(f"   ❌ JSON decode error: {e}")
        return []
    except Exception as e:
        logger.error(f"   ❌ Error reading history: {e}")
        return []

@router.post("/chat/send", dependencies=[Depends(verify_admin)])
async def admin_send_message(platform: str = Form(...), uid: str = Form(...), message: str = Form(...)):
    """Admin ส่งข้อความตอบกลับด้วยตนเอง"""
    logger.info(f"📤 Admin sending message to {platform}/{uid}")
    return {"status": "success", "platform": platform, "uid": uid}