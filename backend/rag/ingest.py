import os
import hashlib
import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader

from config import RAGConfig
from core_components import RAGCore


def _file_hash(path: str) -> str:
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def ingest():
    print("🚀 Starting RAG ingestion...")

    vector_store = RAGCore.get_vector_store()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=RAGConfig.CHUNK_SIZE,
        chunk_overlap=RAGConfig.CHUNK_OVERLAP,
        add_start_index=True,
    )

    documents = []
    ids = []

    for root, _, files in os.walk(RAGConfig.DATA_DIR):
        for fname in files:
            if not fname.endswith(".txt"):
                continue

            filepath = os.path.join(root, fname)
            file_hash = _file_hash(filepath)
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, file_hash))

            loader = TextLoader(filepath)
            raw_docs = loader.load()

            for d in raw_docs:
                d.metadata.update({
                    "doc_id": doc_id,
                    "file_hash": file_hash,
                    "original_filename": fname,
                })

            chunks = splitter.split_documents(raw_docs)

            for idx, chunk in enumerate(chunks):
                chunk_id = hashlib.md5(f"{doc_id}_{idx}".encode()).hexdigest()
                chunk.metadata["chunk_index"] = idx

                documents.append(chunk)
                ids.append(chunk_id)

    if not documents:
        print("⚠️ No documents found.")
        return

    vector_store.add_documents(documents=documents, ids=ids)
    print(f"✅ Upserted {len(documents)} chunks (idempotent).")
