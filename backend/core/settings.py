import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv


def _split_csv(value: str) -> List[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _normalize_provider_chain(items: List[str]) -> List[str]:
    dedup: List[str] = []
    for item in items:
        provider = (item or "").strip().lower()
        if provider and provider not in dedup:
            dedup.append(provider)
    return dedup


@dataclass
class Settings:
    environment: str
    host: str
    port: int
    log_level: str
    allowed_origins: List[str]
    trusted_hosts: List[str]
    llm_provider_chain: List[str]
    rate_limit_window_seconds: int
    speech_rate_limit: int
    webhook_rate_limit: int
    max_text_chars: int
    max_audio_bytes: int

    openai_api_key: str
    openai_base_url: str
    openai_model_name: str

    gemini_api_key: str
    gemini_model_name: str
    gemini_fallback_models: List[str]
    gemini_max_retries: int
    gemini_retry_base_seconds: float

    local_api_key: str
    local_base_url: str
    local_model_name: str

    fb_verify_token: str
    fb_page_access_token: str
    fb_app_secret: str
    admin_token: str

    docs_folder: Path
    sessions_db_path: Path
    frontend_dir: Path
    assets_dir: Path
    logs_dir: Path

    @property
    def is_production(self) -> bool:
        return self.environment in {"prod", "production"}

    @property
    def cors_allow_credentials(self) -> bool:
        return "*" not in self.allowed_origins

    @property
    def socket_cors(self) -> List[str] | str:
        if "*" in self.allowed_origins:
            return "*"
        return self.allowed_origins

    def provider_has_required_config(self, provider: str) -> bool:
        normalized = (provider or "").strip().lower()
        if normalized == "openai":
            return bool(self.openai_api_key and self.openai_model_name)
        if normalized == "gemini":
            return bool(self.gemini_api_key and self.gemini_model_name)
        if normalized == "local":
            return bool(self.local_base_url and self.local_model_name)
        return False

    def validate(self) -> tuple[List[str], List[str]]:
        errors: List[str] = []
        warnings: List[str] = []
        allowed_providers = {"openai", "gemini", "local"}

        unknown = [p for p in self.llm_provider_chain if p not in allowed_providers]
        if unknown:
            errors.append(f"Unknown providers in LLM_PROVIDER_CHAIN: {', '.join(unknown)}")

        configured = [p for p in self.llm_provider_chain if self.provider_has_required_config(p)]
        if not configured:
            errors.append("No usable LLM provider configuration found")

        if self.is_production and "*" in self.allowed_origins:
            warnings.append("ALLOWED_ORIGINS is '*' in production")
        if self.is_production and ("*" in self.trusted_hosts or not self.trusted_hosts):
            warnings.append("TRUSTED_HOSTS is not restricted in production")
        if not self.docs_folder.exists():
            warnings.append(f"Knowledge folder not found: {self.docs_folder}")
        if not self.fb_verify_token:
            warnings.append("FB_VERIFY_TOKEN is empty (Facebook verify endpoint will fail)")
        if self.fb_page_access_token and not self.fb_app_secret:
            warnings.append("FB_APP_SECRET is empty (webhook signature cannot be verified)")
        if not self.admin_token:
            warnings.append("ADMIN_TOKEN is empty (admin API will be disabled)")

        return errors, warnings


def load_settings() -> Settings:
    backend_dir = Path(__file__).resolve().parents[1]
    repo_dir = backend_dir.parent
    load_dotenv(backend_dir / ".env")

    primary_provider = os.getenv("LLM_PROVIDER", "openai")
    provider_chain = _normalize_provider_chain(
        [primary_provider] + _split_csv(os.getenv("LLM_PROVIDER_CHAIN", "openai,gemini,local"))
    )

    return Settings(
        environment=os.getenv("ENVIRONMENT", "development").strip().lower(),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        allowed_origins=_split_csv(os.getenv("ALLOWED_ORIGINS", "*")) or ["*"],
        trusted_hosts=_split_csv(os.getenv("TRUSTED_HOSTS", "*")) or ["*"],
        llm_provider_chain=provider_chain or ["local"],
        rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
        speech_rate_limit=int(os.getenv("SPEECH_RATE_LIMIT", "40")),
        webhook_rate_limit=int(os.getenv("WEBHOOK_RATE_LIMIT", "120")),
        max_text_chars=int(os.getenv("MAX_TEXT_CHARS", "2500")),
        max_audio_bytes=int(os.getenv("MAX_AUDIO_BYTES", str(8 * 1024 * 1024))),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
        openai_model_name=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini").strip(),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model_name=os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash").strip(),
        gemini_fallback_models=_split_csv(
            os.getenv(
                "GEMINI_FALLBACK_MODELS",
                "gemini-2.5-flash-lite,gemini-2.0-flash,gemini-2.0-flash-lite",
            )
        ),
        gemini_max_retries=int(os.getenv("GEMINI_MAX_RETRIES", "2")),
        gemini_retry_base_seconds=float(os.getenv("GEMINI_RETRY_BASE_SECONDS", "1.5")),
        local_api_key=os.getenv("LOCAL_API_KEY", "ollama").strip(),
        local_base_url=os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1").strip(),
        local_model_name=os.getenv("LOCAL_MODEL_NAME", "qwen3:4b").strip(),
        fb_verify_token=os.getenv("FB_VERIFY_TOKEN", "").strip(),
        fb_page_access_token=os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip(),
        fb_app_secret=os.getenv("FB_APP_SECRET", "").strip(),
        admin_token=os.getenv("ADMIN_TOKEN", "").strip(),
        docs_folder=Path(
            os.getenv("PDF_QUICK_USE_FOLDER", str(backend_dir / "app" / "static" / "quick_use"))
        ),
        sessions_db_path=backend_dir / "memory" / "assistant_sessions.db",
        frontend_dir=repo_dir / "frontend",
        assets_dir=repo_dir / "frontend" / "assets",
        logs_dir=repo_dir / "logs",
    )
