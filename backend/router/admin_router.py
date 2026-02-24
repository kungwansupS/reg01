from fastapi import APIRouter, UploadFile, Form, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
import os
import json
import shutil
import asyncio
import datetime
import math
import httpx
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

# Import Config เธเธฒเธเธฃเธฐเธเธ
from app.auth import require_admin
from app.config import PDF_INPUT_FOLDER, PDF_QUICK_USE_FOLDER, BOT_SETTINGS_FILE
from memory.faq_cache import (
    get_faq_analytics,
    list_faq_entries,
    get_faq_entry,
    save_faq_entry,
    delete_faq_entry,
    purge_expired_faq_entries,
)
from memory.session import get_bot_enabled, set_bot_enabled
from memory.session_db import session_db
from pdf_to_txt import process_pdfs

# เธชเธฃเนเธฒเธ Router เธชเธณเธซเธฃเธฑเธ Admin
router = APIRouter(prefix="/api/admin")

# Security Configuration

# Executor เธชเธณเธซเธฃเธฑเธเธเธฒเธ Sync เธซเธเธฑเธเน
admin_executor = ThreadPoolExecutor(max_workers=5)

# Queue reference โ€” injected by main.py at startup
_llm_queue = None

def set_llm_queue(q):
    """Called by main.py to inject the queue instance for monitor endpoint."""
    global _llm_queue
    _llm_queue = q

# Logging
import logging
logger = logging.getLogger("AdminRouter")

async def verify_admin(claims: dict = Depends(require_admin)):
    """Require admin access (JWT RBAC or legacy token mode)."""
    return claims

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
    เนเธกเธ Root เนเธฅเธฐเธ•เธฃเธงเธเธชเธญเธเธเธงเธฒเธกเธเธฅเธญเธ”เธ เธฑเธขเธเธญเธ Path
    """
    if root in ["data", "docs"]:
        base_path = PDF_INPUT_FOLDER
    elif root in ["uploads", "quick_use"]:
        base_path = PDF_QUICK_USE_FOLDER
    else:
        base_path = PDF_INPUT_FOLDER
    
    if not path or path.strip() == "":
        target = os.path.abspath(base_path)
        logger.info(f"๐“ Resolved empty path to root: {target}")
    else:
        clean_path = path.lstrip("/").replace("..", "")
        target = os.path.abspath(os.path.join(base_path, clean_path))
        logger.info(f"๐“ Resolved path '{path}' to: {target}")
    
    if not target.startswith(os.path.abspath(base_path)):
        logger.error(f"๐จ Security violation: {target} not in {base_path}")
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
    """เธ”เธถเธเธเนเธญเธกเธนเธฅ Dashboard Stats เธเธฃเนเธญเธก Token Analytics"""
    logs = []
    log_path = "logs/user_audit.log"
    if os.path.exists(log_path):
        try:
            parsed_logs = []
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parsed_logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            logs = parsed_logs[-100:]
        except Exception:
            logs = []
    
    token_analytics = calculate_token_analytics(logs)
    
    return {
        "recent_logs": logs,
        "faq_analytics": await get_faq_analytics(),
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
async def create_directory(root: str = Form(...), path: str = Form(""), name: str = Form(...)):
    try:
        target = os.path.join(get_secure_path(root, path), name)
        os.makedirs(target, exist_ok=True)
        logger.info(f"โ… Created directory: {target}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"โ Failed to create directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rename", dependencies=[Depends(verify_admin)])
async def rename_item(root: str = Form(...), old_path: str = Form(...), new_name: str = Form(...)):
    try:
        old_target = get_secure_path(root, old_path)
        new_target = os.path.join(os.path.dirname(old_target), new_name)
        
        if os.path.exists(new_target):
            raise HTTPException(status_code=400, detail=f"'{new_name}' already exists")
        
        os.rename(old_target, new_target)
        logger.info(f"โ… Renamed: {old_target} โ’ {new_target}")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"โ Rename failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/move", dependencies=[Depends(verify_admin)])
async def move_items(
    root: str = Form(...), 
    source_paths: str = Form(...),
    target_path: str = Form("")
):
    """เธขเนเธฒเธขเนเธเธฅเน/เนเธเธฅเน€เธ”เธญเธฃเน"""
    try:
        paths = json.loads(source_paths)
        logger.info(f"๐“ฅ API Move Request: root={root}, target={target_path}")
        
        base_dest = get_secure_path(root, target_path)
        
        os.makedirs(base_dest, exist_ok=True)
        
        for p in paths:
            src = get_secure_path(root, p)
            dest = os.path.join(base_dest, os.path.basename(src))
            
            if not os.path.exists(src):
                logger.warning(f"โ ๏ธ Source not found: {src}")
                continue
            
            if src == dest:
                logger.warning(f"โ ๏ธ Source and destination are the same: {src}")
                continue
            
            if os.path.exists(dest):
                raise HTTPException(
                    status_code=400, 
                    detail=f"'{os.path.basename(src)}' already exists in destination"
                )
            
            shutil.move(src, dest)
            logger.info(f"  โ… Moved: {os.path.basename(src)}")
        
        return {"status": "success"}
        
    except json.JSONDecodeError as e:
        logger.error(f"โ Invalid JSON in src_paths: {e}")
        raise HTTPException(status_code=400, detail="Invalid source paths format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"โ Move failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/copy", dependencies=[Depends(verify_admin)])
async def copy_items(root: str = Form(...), source_paths: str = Form(...), target_path: str = Form(...)):
    """เธเธฑเธ”เธฅเธญเธเนเธเธฅเน/เนเธเธฅเน€เธ”เธญเธฃเน"""
    try:
        paths = json.loads(source_paths)
        
        base_dest = get_secure_path(root, target_path)
        logger.info(f"๐“ Copying {len(paths)} items to: {base_dest}")
        
        os.makedirs(base_dest, exist_ok=True)
        
        for p in paths:
            src = get_secure_path(root, p)
            if not os.path.exists(src):
                logger.warning(f"โ ๏ธ Source not found: {src}")
                continue
            
            dest = os.path.join(base_dest, os.path.basename(src))
            
            counter = 1
            original_dest = dest
            while os.path.exists(dest):
                if os.path.isdir(src):
                    dest = f"{original_dest}_copy_{counter}"
                else:
                    name, ext = os.path.splitext(original_dest)
                    dest = f"{name}_copy_{counter}{ext}"
                counter += 1
            
            if os.path.isdir(src):
                shutil.copytree(src, dest)
                logger.info(f"  โ… Copied folder: {os.path.basename(src)}")
            else:
                shutil.copy2(src, dest)
                logger.info(f"  โ… Copied file: {os.path.basename(src)}")
        
        return {"status": "success"}
        
    except json.JSONDecodeError as e:
        logger.error(f"โ Invalid JSON in source_paths: {e}")
        raise HTTPException(status_code=400, detail="Invalid source paths format")
    except Exception as e:
        logger.error(f"โ Copy error: {e}")
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
        logger.error(f"โ View file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/edit", dependencies=[Depends(verify_admin)])
async def edit_file(root: str = Form(...), path: str = Form(...), content: str = Form(...)):
    try:
        target = get_secure_path(root, path)
        with open(target, "w", encoding="utf-8") as f: f.write(content)
        logger.info(f"โ… Edited file: {target}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"โ Edit file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload", dependencies=[Depends(verify_admin)])
async def upload_document(file: UploadFile, target_dir: str = Form(""), root: str = Form("data")):
    try:
        dest_folder = get_secure_path(root, target_dir)
        os.makedirs(dest_folder, exist_ok=True)
        file_path = os.path.join(dest_folder, file.filename)
        with open(file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
        logger.info(f"โ… Uploaded: {file.filename}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"โ Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-rag", dependencies=[Depends(verify_admin)])
async def trigger_rag_process():
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(admin_executor, process_pdfs)
        logger.info("โ… RAG processing completed")
        return {"status": "completed"}
    except Exception as e:
        logger.error(f"โ RAG processing error: {e}")
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
                logger.info(f"โ… Deleted: {target}")
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"โ Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------- #
# CHAT & BOT CONTROL ENDPOINTS (เนเธเน Database)
# ----------------------------------------------------------------------------- #

@router.post("/bot-toggle", dependencies=[Depends(verify_admin)])
async def toggle_bot(session_id: str = Form(...), status: bool = Form(...)):
    """เธชเธฅเธฑเธเธชเธ–เธฒเธเธฐเน€เธเธดเธ”/เธเธดเธ” Bot เธชเธณเธซเธฃเธฑเธ Session เธเธตเน"""
    logger.info(f"๐” Toggling bot for session {session_id}: {status}")
    
    success = await set_bot_enabled(session_id, status)
    
    if success:
        logger.info(f"โ… Bot status updated for {session_id}: {status}")
        return {"status": "success", "session_id": session_id, "bot_enabled": status}
    else:
        logger.error(f"โ Failed to update bot status for {session_id}")
        raise HTTPException(status_code=500, detail="Failed to update bot status")

@router.post("/bot-toggle-all", dependencies=[Depends(verify_admin)])
async def toggle_all_bots(status: bool = Form(...)):
    """เน€เธเธดเธ”/เธเธดเธ” Bot เธ—เธฑเนเธเธซเธกเธ”เธ—เธธเธ Session"""
    logger.info(f"๐” Toggling ALL bots: {status}")
    
    try:
        sessions = await session_db.get_all_sessions()
        
        updated_count = 0
        for session in sessions:
            if await set_bot_enabled(session['session_id'], status):
                updated_count += 1
        
        logger.info(f"โ… Updated {updated_count} sessions")
        return {"status": "success", "updated_count": updated_count, "bot_enabled": status}
    except Exception as e:
        logger.error(f"โ Failed to toggle all bots: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/sessions", dependencies=[Depends(verify_admin)])
async def get_chat_sessions():
    """เธ”เธถเธเธฃเธฒเธขเธเธทเนเธญ Session เธเธฒเธฃเนเธเธ—เธฅเนเธฒเธชเธธเธ” (เธเธฒเธ Database)"""
    logger.info("๐“ Loading chat sessions from database")
    
    try:
        sessions = await session_db.get_all_sessions()
        
        formatted_sessions = []
        for session in sessions:
            formatted_sessions.append({
                "id": session['session_id'],
                "platform": session['platform'],
                "profile": {
                    "name": session['user_name'],
                    "picture": session['user_picture'] or "https://www.gravatar.com/avatar/?d=mp"
                },
                "bot_enabled": bool(session['bot_enabled']),
                "last_active": session['last_active']
            })
        
        logger.info(f"โ… Successfully loaded {len(formatted_sessions)} sessions")
        return formatted_sessions
        
    except Exception as e:
        logger.error(f"โ Failed to load sessions: {e}")
        return []

@router.get("/chat/history/{platform}/{uid}", dependencies=[Depends(verify_admin)])
async def get_chat_history(platform: str, uid: str):
    """เธ”เธถเธเธเธฃเธฐเธงเธฑเธ•เธดเธเธฒเธฃเนเธเธ—เธฃเธฒเธขเธเธ (เธเธฒเธ Database)"""
    logger.info(f"๐“– Loading history for {platform}/{uid}")
    
    try:
        history = await session_db.get_history(uid)
        
        logger.info(f"   โ… Returning {len(history)} valid messages")
        return history
        
    except Exception as e:
        logger.error(f"   โ Error reading history: {e}")
        return []

@router.post("/chat/send", dependencies=[Depends(verify_admin)])
async def admin_send_message(platform: str = Form(...), uid: str = Form(...), message: str = Form(...)):
    """Admin เธชเนเธเธเนเธญเธเธงเธฒเธกเธ•เธญเธเธเธฅเธฑเธเธ”เนเธงเธขเธ•เธเน€เธญเธ"""
    logger.info(f"๐“ค Admin sending message to {platform}/{uid}")
    return {"status": "success", "platform": platform, "uid": uid}

# ----------------------------------------------------------------------------- #
# FAQ MANAGEMENT ENDPOINTS
# ----------------------------------------------------------------------------- #

@router.get("/faq", dependencies=[Depends(verify_admin)])
async def api_list_faq(limit: int = 300, query: str = "", include_expired: bool = False):
    """เธ”เธถเธเธฃเธฒเธขเธเธฒเธฃ FAQ เธ—เธฑเนเธเธซเธกเธ”"""
    return await list_faq_entries(limit=limit, query=query, include_expired=include_expired)

@router.get("/faq/entry", dependencies=[Depends(verify_admin)])
async def api_get_faq(question: str):
    """เธ”เธถเธ FAQ entry เน€เธ”เธตเนเธขเธง"""
    entry = await get_faq_entry(question)
    if not entry:
        raise HTTPException(status_code=404, detail="FAQ entry not found")
    return entry

@router.put("/faq", dependencies=[Depends(verify_admin)])
async def api_save_faq(
    question: str = Form(...),
    answer: str = Form(...),
    original_question: Optional[str] = Form(None),
    ttl_seconds: Optional[int] = Form(None),
    source: str = Form("admin"),
):
    """เธชเธฃเนเธฒเธเธซเธฃเธทเธญเนเธเนเนเธ FAQ entry"""
    try:
        result = await save_faq_entry(
            question=question,
            answer=answer,
            original_question=original_question,
            ttl_seconds=ttl_seconds,
            source=source,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/faq", dependencies=[Depends(verify_admin)])
async def api_delete_faq(question: str):
    """เธฅเธ FAQ entry"""
    try:
        return await delete_faq_entry(question)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/faq/purge-expired", dependencies=[Depends(verify_admin)])
async def api_purge_expired():
    """เธฅเธ FAQ entries เธ—เธตเนเธซเธกเธ”เธญเธฒเธขเธธเธ—เธฑเนเธเธซเธกเธ”"""
    return await purge_expired_faq_entries()

# ----------------------------------------------------------------------------- #
# REAL-TIME MONITOR ENDPOINT
# ----------------------------------------------------------------------------- #

@router.get("/monitor/stats", dependencies=[Depends(verify_admin)])
async def api_monitor_stats():
    """เธ”เธถเธเธเนเธญเธกเธนเธฅ real-time เธชเธณเธซเธฃเธฑเธ monitor dashboard"""
    # Queue stats
    queue_stats = {}
    try:
        if _llm_queue:
            queue_stats = _llm_queue.get_stats()
    except Exception:
        pass

    # Recent logs (last 50)
    logs = []
    log_path = "logs/user_audit.log"
    if os.path.exists(log_path):
        try:
            parsed = []
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parsed.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            logs = parsed[-50:]
        except Exception:
            pass

    # Active sessions count
    session_count = 0
    try:
        session_count = await session_db.get_session_count()
    except Exception:
        pass

    return {
        "queue": queue_stats,
        "recent_activity": logs,
        "active_sessions": session_count,
        "faq_analytics": await get_faq_analytics(),
        "system_time": datetime.datetime.now().isoformat(),
    }

