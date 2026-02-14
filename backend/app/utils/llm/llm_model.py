import asyncio
import os
import subprocess
import time
import logging
import httpx
import openai
import shutil
from google import genai
from app.config import (
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    LLM_PROVIDER,
    OPENAI_BASE_URL,
    LOCAL_API_KEY,
    LOCAL_BASE_URL,
    LOCAL_MODEL_NAME
)

logger = logging.getLogger(__name__)

# Global async clients (singleton pattern)
_async_openai_client = None
_async_local_client = None


def _split_csv_env(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _load_openai_api_keys() -> list[str]:
    explicit_list = _split_csv_env(os.getenv("OPENAI_API_KEYS", ""))
    candidates = [
        str(OPENAI_API_KEY or "").strip(),
        str(os.getenv("OPENAI_API_KEY2", "")).strip(),
        str(os.getenv("OPENAI_API_KEY_BACKUP", "")).strip(),
        *explicit_list,
    ]
    keys = _dedupe_keep_order([key for key in candidates if key])
    return keys


def _mask_api_key(api_key: str) -> str:
    value = str(api_key or "").strip()
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def _extract_status_code(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status
    return None


def _is_retryable_openai_error(exc: Exception) -> bool:
    status_code = _extract_status_code(exc)
    if status_code in {408, 409, 425, 429}:
        return True
    if isinstance(status_code, int) and 500 <= status_code <= 599:
        return True

    transient_types = (
        getattr(openai, "APIConnectionError", Exception),
        getattr(openai, "APITimeoutError", Exception),
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.RemoteProtocolError,
        httpx.NetworkError,
    )
    if isinstance(exc, transient_types):
        return True

    message = str(exc or "").lower()
    markers = [
        "429",
        "rate limit",
        "too many requests",
        "resource_exhausted",
        "quota exceeded",
        "connection error",
        "connect error",
        "timeout",
        "temporarily unavailable",
        "server error",
    ]
    return any(token in message for token in markers)


class _OpenAICompletionsFailover:
    def __init__(self, pool):
        self._pool = pool

    async def create(self, *args, **kwargs):
        return await self._pool.create_chat_completion(*args, **kwargs)


class _OpenAIChatFailover:
    def __init__(self, pool):
        self.completions = _OpenAICompletionsFailover(pool)


class OpenAIFailoverClient:
    def __init__(self, clients: list, labels: list[str]):
        if not clients:
            raise ValueError("OpenAIFailoverClient requires at least one client.")
        self._clients = clients
        self._labels = labels
        self._active_index = 0
        self._switch_lock = asyncio.Lock()
        self.chat = _OpenAIChatFailover(self)

    async def create_chat_completion(self, *args, **kwargs):
        retry_rounds = 2
        last_retryable_error = None

        for round_idx in range(retry_rounds):
            async with self._switch_lock:
                preferred_index = self._active_index

            call_order = [preferred_index] + [idx for idx in range(len(self._clients)) if idx != preferred_index]

            for idx in call_order:
                client = self._clients[idx]
                try:
                    result = await client.chat.completions.create(*args, **kwargs)
                    if idx != preferred_index:
                        async with self._switch_lock:
                            self._active_index = idx
                        logger.warning(
                            "OpenAI failover switched active key to #%d (%s).",
                            idx + 1,
                            self._labels[idx],
                        )
                    return result
                except Exception as exc:
                    if _is_retryable_openai_error(exc):
                        last_retryable_error = exc
                        status_code = _extract_status_code(exc)
                        status_part = f"status={status_code}" if status_code is not None else "status=none"
                        logger.warning(
                            "OpenAI key #%d (%s) transient error (%s, %s); trying next key.",
                            idx + 1,
                            self._labels[idx],
                            type(exc).__name__,
                            status_part,
                        )
                        continue
                    raise

            if round_idx < retry_rounds - 1:
                await asyncio.sleep(0.35 * (round_idx + 1))

        if last_retryable_error is not None:
            logger.warning(
                "OpenAI transient errors persisted across failover rounds (%d rounds).",
                retry_rounds,
            )
            raise last_retryable_error
        raise RuntimeError("OpenAI failover could not create completion.")

    async def close(self):
        for idx, client in enumerate(self._clients):
            try:
                await client.close()
            except Exception as exc:
                logger.warning("Error closing OpenAI key #%d (%s): %s", idx + 1, self._labels[idx], exc)

def ensure_local_llm_ready():
    """
    ตรวจสอบและเตรียมความพร้อมสำหรับ Local LLM (Ollama)
    """
    if LLM_PROVIDER != "local":
        return

    ollama_path = shutil.which("ollama")
    if not ollama_path:
        logger.error("❌ ไม่พบโปรแกรม 'ollama' ใน System PATH")
        return

    base_url_only = LOCAL_BASE_URL.replace("/v1", "")
    
    try:
        with httpx.Client() as client:
            client.get(base_url_only, timeout=2.0)
    except Exception:
        logger.info("🚀 กำลังเริ่มต้น Ollama Service...")
        try:
            if os.name == 'nt': 
                subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            else: 
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            for _ in range(10):
                time.sleep(1)
                try:
                    with httpx.Client() as client:
                        if client.get(base_url_only).status_code == 200:
                            break
                except:
                    continue
        except Exception as e:
            logger.error(f"❌ ไม่สามารถเปิด Ollama อัตโนมัติได้: {e}")
            return

    try:
        with httpx.Client(timeout=10.0) as client:
            tags_response = client.get(f"{base_url_only}/api/tags")
            models = [m['name'] for m in tags_response.json().get('models', [])]
            
            target_model = LOCAL_MODEL_NAME
            if target_model not in models and f"{target_model}:latest" not in models:
                logger.info(f"📥 กำลังติดตั้งโมเดล {target_model} (โปรดรอสักครู่)...")
                subprocess.run(["ollama", "pull", target_model], shell=(os.name == 'nt'), check=True)
                logger.info(f"✅ ติดตั้งโมเดล {target_model} สำเร็จ")
    except Exception as e:
        logger.warning(f"⚠️ การ Pull โมเดลขัดข้อง: {e}")

def get_llm_model():
    """
    สร้างและคืนค่า Client ของ LLM (Async สำหรับ OpenAI/Local, GenAI Client สำหรับ Gemini)
    """
    global _async_openai_client, _async_local_client
    
    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("❌ ไม่พบ GEMINI_API_KEY")
        # GenAI SDK รองรับ .aio สำหรับการเรียกใช้แบบ asynchronous
        return genai.Client(api_key=GEMINI_API_KEY)

    elif LLM_PROVIDER == "openai":
        openai_keys = _load_openai_api_keys()
        if not openai_keys:
            raise ValueError("❌ ไม่พบ OPENAI_API_KEY")
        
        # ใช้ singleton pattern
        if _async_openai_client is None:
            clients = []
            labels = []
            for idx, api_key in enumerate(openai_keys):
                clients.append(
                    openai.AsyncOpenAI(
                        api_key=api_key,
                        base_url=OPENAI_BASE_URL,
                        timeout=httpx.Timeout(60.0, connect=10.0),
                        max_retries=0,
                    )
                )
                labels.append(_mask_api_key(api_key))
                logger.info("OpenAI key #%d ready (%s)", idx + 1, labels[-1])
            _async_openai_client = OpenAIFailoverClient(clients, labels)
            if len(openai_keys) > 1:
                logger.info("OpenAI failover enabled with %d keys.", len(openai_keys))
        return _async_openai_client

    elif LLM_PROVIDER == "local":
        ensure_local_llm_ready()
        
        # ใช้ singleton pattern
        if _async_local_client is None:
            _async_local_client = openai.AsyncOpenAI(
                api_key=LOCAL_API_KEY,
                base_url=LOCAL_BASE_URL,
                timeout=httpx.Timeout(120.0, connect=10.0)
            )
        return _async_local_client
    else:
        raise ValueError(f"❌ ไม่รู้จัก LLM_PROVIDER: {LLM_PROVIDER}")

async def close_llm_clients():
    """
    ✅ ปิด async clients อย่างถูกวิธี
    """
    global _async_openai_client, _async_local_client
    
    if _async_openai_client is not None:
        try:
            await _async_openai_client.close()
            logger.info("✅ Closed OpenAI client")
        except Exception as e:
            logger.warning(f"⚠️ Error closing OpenAI client: {e}")
        _async_openai_client = None
    
    if _async_local_client is not None:
        try:
            await _async_local_client.close()
            logger.info("✅ Closed Local client")
        except Exception as e:
            logger.warning(f"⚠️ Error closing Local client: {e}")
        _async_local_client = None

def log_llm_usage(response, context="", model_name=None):
    """
    บันทึกการใช้งาน Token ของระบบ
    """
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    try:
        if LLM_PROVIDER == "gemini":
            usage = getattr(response, "usage_metadata", None)
            if usage:
                prompt_tokens = usage.prompt_token_count
                completion_tokens = usage.candidates_token_count
                total_tokens = usage.total_token_count
        else:
            usage = getattr(response, "usage", None)
            if usage:
                prompt_tokens = usage.prompt_tokens
                completion_tokens = usage.completion_tokens
                total_tokens = usage.total_tokens
    except Exception as e:
        logger.warning(f"⚠️ ไม่สามารถบันทึก Usage Log ได้: {e}")

    logger.info(f"🔢 {LLM_PROVIDER.upper()} Usage ({context}) - Total: {total_tokens} tokens")
