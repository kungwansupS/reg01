import asyncio
import logging

import edge_tts


logger = logging.getLogger(__name__)


async def stream_tts(text: str):
    payload = (text or "").strip()
    if not payload:
        return
    try:
        communicate = edge_tts.Communicate(payload, voice="th-TH-PremwadeeNeural")
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                yield chunk["data"]
    except Exception as exc:
        logger.error("TTS error: %s", exc)
        # keep stream contract alive
        for _ in range(2):
            await asyncio.sleep(0)
            yield b"\x00" * 512

