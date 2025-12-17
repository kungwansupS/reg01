import os
import hashlib
import uuid
import logging
from typing import List, Optional
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models

from backend.app.config import settings
from backend.app.utils.embeddings import get_embedding_function

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IngestionPipeline:
    def __init__(self):
        self.embeddings = get_embedding_function()
        
        # Ensure persistence directory exists
        if not os.path.exists(settings.QDRANT_PATH):
            os.makedirs(settings.QDRANT_PATH)
            
        self.client = QdrantClient(path=str(settings.QDRANT_PATH))
        self.vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=settings.COLLECTION_NAME,
            embedding=self.embeddings,
        )
        self._ensure_collection()

    def _ensure_collection(self):
        """Checks if collection exists, if not creates it with correct config."""
        collections = self.client.get_collections().collections
        exists = any(c.name == settings.COLLECTION_NAME for c in collections)
        
        if not exists:
            # We determine vector size dynamically from a test embedding
            test_embed = self.embeddings.embed_query("test")
            vector_size = len(test_embed)
            logger.info(f"Creating Qdrant collection '{settings.COLLECTION_NAME}' with vector size: {vector_size}")
            
            self.client.create_collection(
                collection_name=settings.COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                )
            )

    def compute_file_hash(self, file_path: Path) -> str:
        """Computes MD5 hash of the file content for change detection."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def generate_uuid5_id(self, content_str: str) -> str:
        """Generates a deterministic UUID based on content string."""
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, content_str))

    def load_document(self, file_path: Path) -> List[Document]:
        """Loads PDF or TXT files."""
        file_ext = file_path.suffix.lower()
        docs = []
        try:
            if file_ext == ".pdf":
                loader = PyPDFLoader(str(file_path))
                docs = loader.load()
            elif file_ext == ".txt":
                loader = TextLoader(str(file_path), encoding='utf-8')
                docs = loader.load()
            else:
                logger.warning(f"Unsupported file type: {file_path}")
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            
        return docs

    def run(self, source_dir: Optional[Path] = None):
        """
        Main execution method.
        Iterates through files, processes them, and idempotently upserts to Qdrant.
        """
        target_dir = source_dir if source_dir else settings.DOCS_DIR
        logger.info(f"Starting ingestion from: {target_dir}")

        all_files = []
        if target_dir.exists():
            all_files.extend(list(target_dir.rglob("*.pdf")))
            all_files.extend(list(target_dir.rglob("*.txt")))

        if not all_files:
            logger.warning("No documents found to ingest.")
            return

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            add_start_index=True
        )

        documents_to_upsert = []
        ids_to_upsert = []

        for file_path in all_files:
            file_hash = self.compute_file_hash(file_path)
            raw_docs = self.load_document(file_path)
            
            if not raw_docs:
                continue

            # Split documents
            chunks = text_splitter.split_documents(raw_docs)
            
            for i, chunk in enumerate(chunks):
                # ENRICH METADATA
                chunk.metadata["file_hash"] = file_hash
                chunk.metadata["original_filename"] = file_path.name
                chunk.metadata["chunk_index"] = i
                
                # CREATE DETERMINISTIC ID
                # ID = hash(file_hash + chunk_content + index)
                # This ensures if content is same, ID is same -> Qdrant overwrites (Idempotent)
                unique_content_str = f"{file_hash}_{chunk.page_content}_{i}"
                chunk_id = self.generate_uuid5_id(unique_content_str)
                
                documents_to_upsert.append(chunk)
                ids_to_upsert.append(chunk_id)

        if documents_to_upsert:
            logger.info(f"Upserting {len(documents_to_upsert)} chunks to Qdrant...")
            try:
                # Upsert using add_documents with specific IDs
                self.vector_store.add_documents(
                    documents=documents_to_upsert,
                    ids=ids_to_upsert
                )
                logger.info("Ingestion completed successfully.")
            except Exception as e:
                logger.error(f"Failed to upsert documents: {e}")
                raise e
        else:
            logger.info("No valid chunks generated.")

# Helper to run directly
if __name__ == "__main__":
    pipeline = IngestionPipeline()
    pipeline.run()