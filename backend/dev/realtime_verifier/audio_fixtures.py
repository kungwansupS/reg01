import base64
import math
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class AudioFixture:
    fixture_id: str
    label: str
    chunks_b64: list[str]


def _gen_pcm_tone(duration_s: float, sample_rate: int = 16000, freq: float = 220.0, amp: float = 0.16) -> bytes:
    n = int(duration_s * sample_rate)
    out = bytearray()
    for i in range(n):
        val = math.sin(2.0 * math.pi * freq * (i / sample_rate))
        s16 = int(max(-32767, min(32767, val * amp * 32767)))
        out.extend(struct.pack("<h", s16))
    return bytes(out)


def _gen_pcm_silence(duration_s: float, sample_rate: int = 16000) -> bytes:
    n = int(duration_s * sample_rate)
    return b"\x00\x00" * n


def _pcm_to_b64_chunks(pcm: bytes, chunk_bytes: int = 4096) -> list[str]:
    out: list[str] = []
    for i in range(0, len(pcm), chunk_bytes):
        out.append(base64.b64encode(pcm[i : i + chunk_bytes]).decode("ascii"))
    return out


def default_fixtures() -> list[AudioFixture]:
    short = _pcm_to_b64_chunks(_gen_pcm_tone(1.0, freq=220.0))
    medium = _pcm_to_b64_chunks(_gen_pcm_tone(2.5, freq=260.0))
    silence = _pcm_to_b64_chunks(_gen_pcm_silence(1.5))
    return [
        AudioFixture("fx-short", "short-tone", short),
        AudioFixture("fx-medium", "medium-tone", medium),
        AudioFixture("fx-silence", "silence", silence),
    ]
