"""
Facebook Webhook Router
จัดการ webhook verification และรับข้อความจาก Facebook Messenger
"""
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
import os
import json
import logging
import hmac
import hashlib
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="", tags=["webhooks"])
logger = logging.getLogger("WebhookRouter")

FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "")
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")

fb_task_queue = None


def _verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    if not FB_APP_SECRET:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    incoming_signature = signature_header.split("=", 1)[1].strip()
    expected_signature = hmac.new(
        FB_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(incoming_signature, expected_signature)

def init_webhook_router(task_queue):
    """Initialize router with task queue"""
    global fb_task_queue
    fb_task_queue = task_queue

@router.get("/webhook")
async def fb_verify(request: Request):
    """Facebook Webhook Verification"""
    params = request.query_params
    
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == FB_VERIFY_TOKEN:
        logger.info("✅ Facebook webhook verified")
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    
    logger.warning("⚠️ Invalid webhook verification attempt")
    return Response(content="Invalid Token", status_code=403)

@router.post("/webhook")
async def fb_webhook(request: Request):
    """Facebook Webhook Endpoint - รับข้อความจาก Messenger"""
    raw = await request.body()
    signature = (request.headers.get("X-Hub-Signature-256") or "").strip()

    if not _verify_webhook_signature(raw, signature):
        logger.warning("Invalid webhook signature")
        return JSONResponse({"status": "error", "message": "Invalid signature"}, status_code=401)
    
    try:
        if fb_task_queue is None:
            logger.error("Webhook task queue is not initialized")
            return JSONResponse({"status": "error", "message": "Server not ready"}, status_code=503)

        payload = json.loads(raw.decode("utf-8"))
        
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                if "message" in event and "text" in event["message"] and not event["message"].get("is_echo"):
                    sender_id = event["sender"]["id"]
                    message_text = event["message"]["text"].strip()
                    
                    await fb_task_queue.put({
                        "psid": sender_id,
                        "text": message_text
                    })
                    
                    logger.info(f"📨 Received message from {sender_id}: {message_text[:50]}")
        
        return JSONResponse({"status": "accepted"})
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON payload: {e}")
        return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)
    
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return JSONResponse({"status": "error"}, status_code=500)
