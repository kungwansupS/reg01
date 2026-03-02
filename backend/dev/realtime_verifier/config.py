from dataclasses import dataclass


@dataclass(frozen=True)
class VerifierConfig:
    backend_url: str = "http://localhost:5000"
    socket_path: str = "socket.io"
    turn_timeout_s: float = 30.0
    inter_chunk_sleep_s: float = 0.01
    eos_to_first_audio_p95_ms: float = 1200.0
    interruption_reaction_p90_ms: float = 350.0
    turn_error_rate_max: float = 0.10
    min_turns: int = 5
    report_dir: str = "team-space/eval/realtime/reports"


DEFAULT_CONFIG = VerifierConfig()
