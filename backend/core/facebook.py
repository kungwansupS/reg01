import logging

import httpx

from .settings import Settings


logger = logging.getLogger(__name__)
GRAPH_BASE = "https://graph.facebook.com/v19.0"


async def send_facebook_text(settings: Settings, psid: str, text: str) -> None:
    if not settings.fb_page_access_token:
        return
    url = f"{GRAPH_BASE}/me/messages?access_token={settings.fb_page_access_token}"
    payload = {
        "recipient": {"id": psid},
        "message": {"text": (text or "")[:1999]},
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(url, json=payload)
    except Exception as exc:
        logger.error("Facebook send failed: %s", exc)

