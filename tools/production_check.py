import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

REPO_DIR = Path(__file__).resolve().parents[1]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))
os.chdir(REPO_DIR)

from backend.core.app_factory import create_asgi_app
from backend.core.settings import load_settings


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    critical: bool = True


def _result(name: str, ok: bool, detail: str, critical: bool = True) -> CheckResult:
    return CheckResult(name=name, status="pass" if ok else "fail", detail=detail, critical=critical)


def _skip(name: str, detail: str, critical: bool = False) -> CheckResult:
    return CheckResult(name=name, status="skip", detail=detail, critical=critical)


def run_checks() -> dict[str, Any]:
    settings = load_settings()
    asgi_app, app, _, _ = create_asgi_app()
    checks: list[CheckResult] = []

    started = time.perf_counter()
    with TestClient(asgi_app) as client:
        health = client.get("/health")
        checks.append(
            _result(
                "health_endpoint",
                health.status_code == 200 and bool(health.json().get("ok")),
                f"status={health.status_code} body={health.json()}",
            )
        )

        ready = client.get("/ready")
        ready_ok = ready.status_code == 200 and bool(ready.json().get("ok"))
        ready_json = ready.json()
        checks.append(
            _result(
                "readiness_endpoint",
                ready_ok,
                f"status={ready.status_code} body={ready_json}",
            )
        )
        audio_check = ((ready_json.get("checks") or {}).get("audio_transcoder") or {}).get("ok")
        checks.append(
            _result(
                "audio_transcoder_available",
                bool(audio_check),
                f"audio_transcoder={((ready_json.get('checks') or {}).get('audio_transcoder') or {})}",
                critical=False,
            )
        )

        speech = client.post("/api/speech", files={"text": (None, "ping"), "session_id": (None, "prod_check")})
        speech_json = speech.json() if speech.headers.get("content-type", "").startswith("application/json") else {}
        checks.append(
            _result(
                "speech_ping",
                speech.status_code == 200 and bool(speech_json.get("text")),
                f"status={speech.status_code} body={speech_json}",
            )
        )
        tts = client.post("/api/speak", files={"text": (None, "test audio output")})
        tts_all_zero = bool(tts.content) and all(byte == 0 for byte in tts.content)
        checks.append(
            _result(
                "tts_stream",
                tts.status_code == 200
                and tts.headers.get("content-type", "").startswith("audio/mpeg")
                and len(tts.content) > 0,
                f"status={tts.status_code} content_type={tts.headers.get('content-type')} bytes={len(tts.content)}",
            )
        )
        checks.append(
            _result(
                "tts_non_silent_audio",
                not tts_all_zero,
                f"all_zero_audio={tts_all_zero} bytes={len(tts.content)}",
                critical=False,
            )
        )
        checks.append(
            _result(
                "request_id_header",
                bool(speech.headers.get("x-request-id")),
                "x-request-id present" if speech.headers.get("x-request-id") else "x-request-id missing",
            )
        )

        too_long_text = "x" * (settings.max_text_chars + 1)
        too_long = client.post("/api/speech", files={"text": (None, too_long_text), "session_id": (None, "prod_check")})
        checks.append(
            _result(
                "input_guard_text_length",
                too_long.status_code == 422,
                f"status={too_long.status_code} body={too_long.text[:160]}",
            )
        )

        burst = min(settings.speech_rate_limit + 1, 120)
        rate_statuses = []
        for idx in range(burst):
            r = client.post(
                "/api/speech",
                files={"text": (None, "ping"), "session_id": (None, f"rate_{idx}")},
            )
            rate_statuses.append(r.status_code)
        checks.append(
            _result(
                "speech_rate_limit_guard",
                429 in rate_statuses,
                f"burst={burst} statuses_tail={rate_statuses[-5:]}",
            )
        )

        if settings.fb_verify_token:
            webhook_verify = client.get(
                "/webhook",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": settings.fb_verify_token,
                    "hub.challenge": "12345",
                },
            )
            checks.append(
                _result(
                    "facebook_webhook_verify",
                    webhook_verify.status_code == 200 and webhook_verify.text == "12345",
                    f"status={webhook_verify.status_code} body={webhook_verify.text}",
                )
            )
        else:
            checks.append(_skip("facebook_webhook_verify", "FB_VERIFY_TOKEN not set"))

        if settings.fb_app_secret:
            invalid_signature = client.post(
                "/webhook",
                content=b'{"object":"page","entry":[]}',
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=invalid"},
            )
            checks.append(
                _result(
                    "facebook_signature_guard",
                    invalid_signature.status_code == 403,
                    f"status={invalid_signature.status_code}",
                )
            )
        else:
            checks.append(_skip("facebook_signature_guard", "FB_APP_SECRET not set"))

        if settings.admin_token:
            admin_stats = client.get("/api/admin/stats", headers={"X-Admin-Token": settings.admin_token})
            checks.append(
                _result(
                    "admin_stats_auth",
                    admin_stats.status_code == 200,
                    f"status={admin_stats.status_code}",
                    critical=False,
                )
            )
        else:
            admin_stats = client.get("/api/admin/stats")
            checks.append(
                _result(
                    "admin_disabled_without_token",
                    admin_stats.status_code == 503,
                    f"status={admin_stats.status_code}",
                    critical=False,
                )
            )

    elapsed = round(time.perf_counter() - started, 3)
    failed_critical = [c for c in checks if c.status == "fail" and c.critical]
    failed_non_critical = [c for c in checks if c.status == "fail" and not c.critical]
    summary = {
        "environment": settings.environment,
        "total": len(checks),
        "critical_failures": len(failed_critical),
        "non_critical_failures": len(failed_non_critical),
        "skipped": len([c for c in checks if c.status == "skip"]),
        "duration_sec": elapsed,
        "pass": len(failed_critical) == 0,
    }
    return {"summary": summary, "checks": [asdict(c) for c in checks]}


def main() -> None:
    result = run_checks()
    output = Path("tools/production_check_result.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"Saved detailed result: {output}")


if __name__ == "__main__":
    main()
