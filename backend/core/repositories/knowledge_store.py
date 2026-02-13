import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

from rank_bm25 import BM25Okapi

from ..schemas import RetrievedChunk


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[0-9A-Za-z\u0E00-\u0E7F]+", text.lower())


@dataclass
class _DocChunk:
    source: str
    chunk: str


class KnowledgeStore:
    def __init__(self, docs_folder: Path, separator: str = "===================") -> None:
        self.docs_folder = docs_folder
        self.separator = separator
        self._chunks: List[_DocChunk] = []
        self._bm25: BM25Okapi | None = None

    def reload(self) -> None:
        chunks: List[_DocChunk] = []
        if not self.docs_folder.exists():
            self._chunks = []
            self._bm25 = None
            return

        for root, _, files in os.walk(self.docs_folder):
            for name in files:
                if not name.lower().endswith(".txt"):
                    continue
                path = Path(root) / name
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for part in content.split(self.separator):
                    chunk = part.strip()
                    if len(chunk) < 40:
                        continue
                    chunks.append(_DocChunk(source=str(path), chunk=chunk))

        tokenized = [_tokenize(c.chunk) for c in chunks]
        self._chunks = chunks
        self._bm25 = BM25Okapi(tokenized) if tokenized else None

    def search(self, query: str, k: int = 5) -> List[RetrievedChunk]:
        if not self._bm25 or not self._chunks:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results: List[RetrievedChunk] = []
        for idx in ranked[:k]:
            if scores[idx] <= 0:
                continue
            raw = self._chunks[idx]
            results.append(
                RetrievedChunk(source=raw.source, chunk=raw.chunk, score=float(scores[idx]))
            )
        return results

