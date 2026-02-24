import asyncio
import datetime
import hashlib
import logging
import os
import re
import threading
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import chromadb
import torch
from sentence_transformers import SentenceTransformer
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import DATABASE_URL
from memory.models import FileRegistry

logger = logging.getLogger("VectorManager")


class VectorManager:
    def __init__(self):
        self.db_dir = os.path.join("data", "db")
        os.makedirs(self.db_dir, exist_ok=True)

        self.chroma_path = os.path.join(self.db_dir, "chroma_data")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = (
            "BAAI/bge-m3"
            if self.device == "cuda"
            else "intfloat/multilingual-e5-small"
        )
        self._model = None

        self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
        self.collection = self.chroma_client.get_or_create_collection(name="reg_context")

    @property
    def model(self):
        if self._model is None:
            logger.info("Loading embedding model: %s on %s", self.model_name, self.device)
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    @staticmethod
    def _run_async(coro):
        """
        Run async DB helpers from sync call-sites.
        These methods are normally called inside `asyncio.to_thread`.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        # Fallback: if called from an active loop, run coroutine in a dedicated thread.
        result = {"value": None, "error": None}

        def _runner():
            try:
                result["value"] = asyncio.run(coro)
            except Exception as exc:  # pragma: no cover - defensive bridge
                result["error"] = exc

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join()
        if result["error"] is not None:
            raise result["error"]
        return result["value"]

    @staticmethod
    def _to_async_dsn(dsn: str) -> str:
        if dsn.startswith("postgresql://"):
            return dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
        return dsn

    @asynccontextmanager
    async def _session_scope(self):
        """
        Create a loop-local SQLAlchemy session.
        This avoids reusing asyncpg resources across different event loops/threads.
        """
        engine = create_async_engine(
            self._to_async_dsn(DATABASE_URL),
            poolclass=NullPool,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as db:
                yield db
        finally:
            await engine.dispose()

    async def _get_registry_hash(self, filepath: str) -> Optional[str]:
        async with self._session_scope() as db:
            return await db.scalar(
                select(FileRegistry.file_hash).where(FileRegistry.file_path == filepath)
            )

    async def _upsert_registry(self, filepath: str, file_hash: str) -> None:
        async with self._session_scope() as db:
            row = await db.get(FileRegistry, filepath)
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if row:
                row.file_hash = file_hash
                row.last_updated = now_utc
            else:
                db.add(
                    FileRegistry(
                        file_path=filepath,
                        file_hash=file_hash,
                        last_updated=now_utc,
                    )
                )
            await db.commit()

    async def _delete_registry(self, filepath: str) -> None:
        async with self._session_scope() as db:
            await db.execute(
                delete(FileRegistry).where(FileRegistry.file_path == filepath)
            )
            await db.commit()

    def get_file_hash(self, filepath: str) -> str:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            hasher.update(f.read())
        return hasher.hexdigest()

    def needs_update(self, filepath: str):
        current_hash = self.get_file_hash(filepath)
        existing_hash = self._run_async(self._get_registry_hash(filepath))
        if existing_hash != current_hash:
            return True, current_hash
        return False, current_hash

    def update_registry(self, filepath: str, file_hash: str):
        self._run_async(self._upsert_registry(filepath, file_hash))

    def remove_from_registry(self, filepath: str):
        self._run_async(self._delete_registry(filepath))

    def purge_out_of_scope(self, valid_paths: set[str], allowed_root: str) -> Dict[str, int]:
        normalized_valid = {os.path.normcase(os.path.abspath(path)) for path in valid_paths}
        normalized_root = os.path.normcase(os.path.abspath(allowed_root))
        root_with_sep = normalized_root + os.sep

        try:
            rows = self.collection.get(include=["metadatas", "documents"])
        except Exception as exc:
            logger.error("Failed to enumerate existing vectors: %s", exc)
            return {"removed_ids": 0, "removed_sources": 0}

        ids = rows.get("ids", []) or []
        metadatas = rows.get("metadatas", []) or []
        documents = rows.get("documents", []) or []
        if not ids:
            return {"removed_ids": 0, "removed_sources": 0}

        remove_ids: list[str] = []
        remove_sources = set()
        for row_id, metadata, document in zip(ids, metadatas, documents):
            source = str((metadata or {}).get("source") or "").strip()
            if not source:
                continue
            normalized_source = os.path.normcase(os.path.abspath(source))
            in_root = normalized_source == normalized_root or normalized_source.startswith(
                root_with_sep
            )
            doc_text = str(document or "").strip()
            doc_alnum = len(re.findall(r"[A-Za-z0-9\u0E00-\u0E7F]", doc_text))
            is_noisy_doc = doc_alnum < 10
            if (not in_root) or (normalized_source not in normalized_valid) or is_noisy_doc:
                remove_ids.append(row_id)
                remove_sources.add(source)

        if remove_ids:
            self.collection.delete(ids=remove_ids)
            for source in remove_sources:
                self.remove_from_registry(source)
            logger.info(
                "Purged %s stale chunks from %s sources",
                len(remove_ids),
                len(remove_sources),
            )

        return {"removed_ids": len(remove_ids), "removed_sources": len(remove_sources)}

    def add_document(self, filepath: str, chunks: List[str], metadata: Optional[Dict] = None):
        """
        Add file chunks to ChromaDB and attach per-chunk metadata.
        """
        self.collection.delete(where={"source": filepath})

        if not chunks:
            logger.warning("No chunks to index for %s", filepath)
            return

        base_metadata = metadata or {}
        ids = [f"{filepath}_{i}" for i in range(len(chunks))]
        metadatas = []

        for i in range(len(chunks)):
            chunk_metadata = {
                "source": filepath,
                "filename": base_metadata.get("filename", os.path.basename(filepath)),
                "chunk_index": i,
                "doc_type": base_metadata.get("doc_type", "general"),
                "language": base_metadata.get("language", "th"),
                "has_dates": base_metadata.get("has_dates", False),
                "last_updated": base_metadata.get(
                    "last_updated", datetime.datetime.now().isoformat()
                ),
            }

            if "academic_years" in base_metadata and base_metadata["academic_years"]:
                chunk_metadata["academic_years"] = ",".join(base_metadata["academic_years"])

            if "semesters" in base_metadata and base_metadata["semesters"]:
                chunk_metadata["semesters"] = ",".join(map(str, base_metadata["semesters"]))

            metadatas.append(chunk_metadata)

        embeddings = self.model.encode(
            [f"passage: {chunk}" for chunk in chunks],
            normalize_embeddings=True,
        ).tolist()

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        logger.info("Indexed %d chunks from %s", len(chunks), os.path.basename(filepath))

    def search(self, query: str, k: int = 5, filter_dict: Optional[Dict] = None) -> List[Dict]:
        query_embedding = self.model.encode(
            f"query: {query}",
            normalize_embeddings=True,
        ).tolist()

        where_clause = None
        post_filters = {}

        if filter_dict:
            if "doc_type" in filter_dict:
                where_clause = {"doc_type": filter_dict["doc_type"]}
                logger.debug("Pre-filter: doc_type=%s", filter_dict["doc_type"])
            elif "language" in filter_dict:
                where_clause = {"language": filter_dict["language"]}
                logger.debug("Pre-filter: language=%s", filter_dict["language"])

            if "academic_year" in filter_dict:
                post_filters["academic_year"] = filter_dict["academic_year"]
            if "semester" in filter_dict:
                post_filters["semester"] = str(filter_dict["semester"])

        query_k = k * 3 if post_filters else k

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=query_k,
                where=where_clause,
            )
        except Exception as exc:
            logger.error("ChromaDB query error: %s", exc)
            try:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=query_k,
                )
            except Exception as fallback_exc:
                logger.error("Fallback query failed: %s", fallback_exc)
                return []

        formatted_results = []
        if results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                metadata = results["metadatas"][0][i]

                if post_filters:
                    if "academic_year" in post_filters:
                        academic_years = metadata.get("academic_years", "")
                        if post_filters["academic_year"] not in academic_years:
                            continue

                    if "semester" in post_filters:
                        semesters = metadata.get("semesters", "")
                        if post_filters["semester"] not in semesters:
                            continue

                formatted_results.append(
                    {
                        "chunk": results["documents"][0][i],
                        "source": metadata.get("source", ""),
                        "score": 1.0 - results["distances"][0][i],
                        "metadata": metadata,
                    }
                )

        filtered_count = len(formatted_results)
        formatted_results = formatted_results[:k]

        if post_filters:
            logger.info(
                "Post-filtered: %d -> %d results",
                filtered_count,
                len(formatted_results),
            )

        return formatted_results

    def get_all_chunks(self) -> List[Dict]:
        try:
            results = self.collection.get()

            chunks = []
            if results["documents"]:
                for i, doc in enumerate(results["documents"]):
                    chunks.append(
                        {
                            "chunk": doc,
                            "source": results["metadatas"][i].get("source", ""),
                            "index": results["metadatas"][i].get("chunk_index", i),
                        }
                    )

            logger.info("Retrieved %d chunks for indexing", len(chunks))
            return chunks

        except Exception as exc:
            logger.error("Error getting all chunks: %s", exc)
            return []


vector_manager = VectorManager()
