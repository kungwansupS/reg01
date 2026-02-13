# Backend Core Architecture

## Goals
- Keep the assistant available for web (Live2D) and Facebook channels.
- Replace legacy backend with a modular, testable architecture.
- Support provider fallback (`openai -> gemini -> local`) and lower outage risk.
- Keep response style natural while grounding answers in university documents.

## Service Layout
- `settings.py`: environment loading and runtime config.
- `repositories/session_store.py`: conversation persistence (SQLite).
- `repositories/knowledge_store.py`: document chunk loading + BM25 retrieval.
- `services/llm_gateway.py`: provider clients, retries, fallback chain.
- `services/assistant_service.py`: orchestration, prompting, response shaping.
- `services/stt_service.py`: speech-to-text adapter for uploaded audio.
- `services/tts_service.py`: text-to-speech streaming adapter.
- `facebook.py`: Messenger send helper.
- `app_factory.py`: FastAPI + Socket.IO routes and lifecycle wiring.

## Production Safeguards
- Request middleware with:
  - `X-Request-ID` correlation id
  - latency logging per request
  - uniform error envelope for unhandled failures
- Security controls:
  - `TrustedHostMiddleware` (`TRUSTED_HOSTS`)
  - CORS from `ALLOWED_ORIGINS`
  - security headers (`nosniff`, `X-Frame-Options`, `HSTS` in production)
- Abuse protection:
  - sliding-window rate limit for `/api/speech` and `/webhook`
  - text/audio payload size guards
- Facebook hardening:
  - webhook verify route supports official `hub.*` parameters
  - optional `X-Hub-Signature-256` verification with `FB_APP_SECRET`
- Runtime readiness:
  - `GET /health` for liveness
  - `GET /ready` for dependency checks (session DB, knowledge index, LLM config)

## Request Flow
1. Client sends text/audio to `/api/speech`.
2. Audio is transcribed (if present).
3. Assistant loads recent session history.
4. Knowledge store retrieves top chunks.
5. LLM gateway generates answer with provider fallback.
6. Response is emitted via Socket.IO (`ai_response`) and returned as JSON.
7. Audit line is appended to `logs/user_audit.log`.

## Channel Support
- Web:
  - `POST /api/speech`
  - `POST /api/speak`
  - Socket.IO events (`subtitle`, `ai_status`, `ai_response`)
- Facebook:
  - `GET /webhook` verify
  - `POST /webhook` receive + reply

## Environment Keys
- Required for cloud providers:
  - `OPENAI_API_KEY` (Groq/OpenAI-compatible)
  - `GEMINI_API_KEY`
- Optional controls:
  - `LLM_PROVIDER` and `LLM_PROVIDER_CHAIN`
  - `GEMINI_FALLBACK_MODELS`
  - `GEMINI_MAX_RETRIES`
  - `GEMINI_RETRY_BASE_SECONDS`
  - `RATE_LIMIT_WINDOW_SECONDS`
  - `SPEECH_RATE_LIMIT`
  - `WEBHOOK_RATE_LIMIT`
  - `MAX_TEXT_CHARS`
  - `MAX_AUDIO_BYTES`
  - `TRUSTED_HOSTS`
  - `ADMIN_TOKEN`

## Validation Command
- Run production smoke checks:
  - `python tools/production_check.py`
  - output: `tools/production_check_result.json`
