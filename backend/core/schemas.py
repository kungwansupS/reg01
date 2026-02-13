from dataclasses import dataclass
from typing import List


@dataclass
class RetrievedChunk:
    source: str
    chunk: str
    score: float


@dataclass
class AssistantReply:
    text: str
    motion: str
    provider: str
    model: str
    sources: List[RetrievedChunk]

