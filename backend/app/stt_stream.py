import asyncio
import os
import tempfile
import wave
from dataclasses import dataclass, field

from app.stt import transcribe


@dataclass
class StreamingSTTSession:
    sample_rate: int = 16000
    audio_buffer: bytearray = field(default_factory=bytearray)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def feed_pcm16(self, pcm_chunk: bytes) -> None:
        if not pcm_chunk:
            return
        async with self.lock:
            self.audio_buffer.extend(pcm_chunk)

    async def flush_and_transcribe(self) -> str:
        async with self.lock:
            raw_pcm = bytes(self.audio_buffer)
            self.audio_buffer.clear()

        if not raw_pcm:
            return ""

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name
        try:
            _write_pcm16_wav(wav_path, raw_pcm, self.sample_rate)
            return await asyncio.to_thread(transcribe, wav_path)
        finally:
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass


def _write_pcm16_wav(path: str, pcm: bytes, sample_rate: int) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
