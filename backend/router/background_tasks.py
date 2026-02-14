"""
Background Tasks & Workers
จัดการงานพื้นหลัง: FB worker, maintenance, vector sync
"""
import os
import time
import asyncio
import httpx
import logging
from dotenv import load_dotenv

from app.utils.vector_manager import vector_manager
from app.config import (
    PDF_QUICK_USE_FOLDER,
    LLM_PROVIDER,
    GEMINI_MODEL_NAME,
    OPENAI_MODEL_NAME,
    LOCAL_MODEL_NAME,
    RAG_STARTUP_EMBEDDING,
    RAG_STARTUP_PROCESS_PDF,
    RAG_STARTUP_BUILD_HYBRID,
)
from memory.session import get_or_create_history, save_history, cleanup_old_sessions, get_bot_enabled

load_dotenv()

logger = logging.getLogger("BackgroundTasks")

FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
GRAPH_BASE = "https://graph.facebook.com/v19.0"

sio = None
fb_task_queue = None
session_locks = {}
audit_logger = None
ask_llm_fn = None
send_fb_text_fn = None

def init_background_tasks(
    socketio_instance,
    task_queue,
    locks_dict,
    audit_log_fn,
    llm_fn,
    fb_sender_fn
):
    """Initialize background tasks"""
    global sio, fb_task_queue, session_locks, audit_logger, ask_llm_fn, send_fb_text_fn
    sio = socketio_instance
    fb_task_queue = task_queue
    session_locks = locks_dict
    audit_logger = audit_log_fn
    ask_llm_fn = llm_fn
    send_fb_text_fn = fb_sender_fn

async def get_session_lock(session_id: str):
    """Get or create session lock"""
    if session_id not in session_locks:
        session_locks[session_id] = asyncio.Lock()
    return session_locks[session_id]

async def sync_vector_db():
    """
    [PHASE 3] ตรวจสอบความเปลี่ยนแปลงของไฟล์ .txt และอัปเดตลง Vector DB อัตโนมัติ
    """
    def run_sync():
        from app.utils.metadata_extractor import metadata_extractor
        
        logger.info("🔍 [Vector DB] Starting startup synchronization...")
        if not os.path.exists(PDF_QUICK_USE_FOLDER):
            logger.warning(f"⚠️ [Vector DB] Quick-use folder not found: {PDF_QUICK_USE_FOLDER}")
            return

        sync_count = 0
        for root, _, files in os.walk(PDF_QUICK_USE_FOLDER):
            for filename in sorted(files):
                if filename.endswith(".txt"):
                    filepath = os.path.join(root, filename)
                    needs_upd, file_hash = vector_manager.needs_update(filepath)
                    
                    if needs_upd:
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                content = f.read()
                            
                            separator = "==================="
                            chunks = [c.strip() for c in content.split(separator) if c.strip()]
                            
                            metadata = metadata_extractor.extract(content, filepath)
                            vector_manager.add_document(filepath, chunks, metadata)
                            vector_manager.update_registry(filepath, file_hash)
                            sync_count += 1
                        except Exception as e:
                            logger.error(f"❌ [Vector DB] Sync failed for {filename}: {e}")
        
        if sync_count > 0:
            logger.info(f"✅ [Vector DB] Synchronization complete. Updated {sync_count} files.")
        else:
            logger.info("✅ [Vector DB] Database is already up-to-date.")

    await asyncio.to_thread(run_sync)

async def build_hybrid_index():
    """
    [PHASE 3] Build BM25 index for hybrid search
    """
    def run_build():
        from retriever.hybrid_retriever import hybrid_retriever
        
        logger.info("🔨 [Hybrid] Building BM25 index...")
        
        chunks = vector_manager.get_all_chunks()
        
        if not chunks:
            logger.warning("⚠️ [Hybrid] No chunks found in vector DB")
            return
        
        hybrid_retriever.build_index(chunks)
        logger.info(f"✅ [Hybrid] BM25 index ready with {len(chunks)} chunks")
    
    await asyncio.to_thread(run_build)


async def process_pdfs_for_rag():
    """
    Run PDF -> TXT pipeline before embedding sync (startup use-case).
    """
    def run_process():
        from pdf_to_txt import process_pdfs
        process_pdfs()

    logger.info("📄 [Startup RAG] Running PDF to TXT pipeline...")
    started = time.perf_counter()
    await asyncio.to_thread(run_process)
    logger.info(f"✅ [Startup RAG] PDF to TXT completed in {round(time.perf_counter() - started, 2)}s")


async def run_startup_embedding_pipeline():
    """
    Startup pipeline:
    1) Optional PDF -> TXT
    2) Embedding sync to vector DB
    3) Optional hybrid index build
    """
    if not RAG_STARTUP_EMBEDDING:
        logger.info("⏭️ [Startup RAG] Skipped (RAG_STARTUP_EMBEDDING=false)")
        return

    logger.info(
        "🚀 [Startup RAG] Begin pipeline | process_pdf=%s build_hybrid=%s",
        RAG_STARTUP_PROCESS_PDF,
        RAG_STARTUP_BUILD_HYBRID,
    )
    started = time.perf_counter()

    if RAG_STARTUP_PROCESS_PDF:
        try:
            await process_pdfs_for_rag()
        except Exception as exc:
            logger.error(f"❌ [Startup RAG] PDF to TXT failed: {exc}")
    else:
        logger.info("⏭️ [Startup RAG] Skip PDF to TXT (RAG_STARTUP_PROCESS_PDF=false)")

    await sync_vector_db()

    if RAG_STARTUP_BUILD_HYBRID:
        await build_hybrid_index()
    else:
        logger.info("⏭️ [Startup RAG] Skip hybrid index (RAG_STARTUP_BUILD_HYBRID=false)")

    logger.info(f"✅ [Startup RAG] Pipeline completed in {round(time.perf_counter() - started, 2)}s")

async def maintenance_loop():
    """งานบำรุงรักษาระบบรายวัน"""
    while True:
        try:
            cleanup_old_sessions(days=7)
            logger.info("🧹 Maintenance: Old sessions cleaned up")
        except Exception as e:
            logger.error(f"❌ Maintenance error: {e}")
        
        await asyncio.sleep(86400)  # 24 hours

async def fb_worker():
    """
    Worker สำหรับจัดการข้อความจาก Facebook Messenger
    """
    while True:
        task = await fb_task_queue.get()
        psid = task["psid"]
        user_text = task["text"]
        start_time = time.time()
        
        session_id = f"fb_{psid}"
        logger.info(f"📩 Processing FB message: {session_id}")
        
        user_name = f"FB User {psid[:5]}"
        user_pic = "https://www.gravatar.com/avatar/?d=mp"
        
        if FB_PAGE_ACCESS_TOKEN:
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(
                        f"https://graph.facebook.com/{psid}?fields=name,picture&access_token={FB_PAGE_ACCESS_TOKEN}",
                        timeout=3
                    )
                    if r.status_code == 200:
                        data = r.json()
                        user_name = data.get("name", user_name)
                        user_pic = data.get("picture", {}).get("data", {}).get("url", user_pic)
            except Exception as e:
                logger.error(f"❌ Fetch FB Profile Error: {e}")

        await sio.emit("admin_new_message", {
            "platform": "facebook",
            "uid": session_id,
            "text": user_text,
            "user_name": user_name,
            "user_pic": user_pic
        })
        
        bot_enabled = get_bot_enabled(session_id)
        if not bot_enabled:
            history = get_or_create_history(
                session_id,
                user_name=user_name,
                user_picture=user_pic,
                platform="facebook"
            )
            history.append({"role": "user", "parts": [{"text": user_text}]})
            save_history(
                session_id,
                history,
                user_name=user_name,
                user_picture=user_pic,
                platform="facebook"
            )
            fb_task_queue.task_done()
            continue

        async with await get_session_lock(session_id):
            try:
                get_or_create_history(
                    session_id,
                    user_name=user_name,
                    user_picture=user_pic,
                    platform="facebook"
                )
                
                # FB worker does not need to broadcast ai_status to all sockets.
                result = await ask_llm_fn(user_text, session_id)
                reply = result["text"]
                tokens = result.get("tokens", {})
                trace_id = result.get("trace_id")
                
                fb_message = f"[Bot พี่เร็ก] {reply.replace('//', '')}"
                await send_fb_text_fn(psid, fb_message)
                
                await sio.emit("admin_bot_reply", {
                    "platform": "facebook",
                    "uid": session_id,
                    "text": fb_message
                })
                
                model_name = GEMINI_MODEL_NAME if LLM_PROVIDER == "gemini" else (
                    OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
                )
                
                audit_logger(
                    psid,
                    "facebook",
                    user_text,
                    reply,
                    time.time() - start_time,
                    tokens=tokens,
                    model_name=model_name,
                    session_id=session_id,
                    trace_id=trace_id,
                )
            except Exception as e:
                logger.error(f"❌ FB Worker Error: {e}")
            finally:
                fb_task_queue.task_done()
