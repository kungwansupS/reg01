import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend root
BASE_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_BACKEND_DIR / ".env")


class RAGConfig:
    """
    RAG-ONLY CONFIG
    Scope:
    - Embedding
    - Vector DB
    - Retrieval
    - RAG Answer
    """

    # --- Paths ---
    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR / "data"
    VECTOR_DB_PATH = BASE_DIR / "qdrant_data"

    # --- Embedding (ONE MODEL ONLY) ---
    # Preferred (2025, free, multilingual)
    EMBEDDING_MODEL_NAME = "google/embeddinggemma-300M"
    # Fallback (uncomment only if Gemma not accessible)
    # EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-base"

    NORMALIZE_EMBEDDINGS = True

    # --- Vector DB ---
    COLLECTION_NAME = "rag_documents"

    # --- Ingestion ---
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 150

    # --- Retrieval ---
    SEARCH_TYPE = "mmr"
    FETCH_K = 20
    K = 5
    LAMBDA_MULT = 0.5

    # --- LLM (used only in rag_query.py) ---
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    LLM_TEMPERATURE = 0.3

    # Ensure dirs
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)


if not RAGConfig.GOOGLE_API_KEY:
    print("Warning: GOOGLE_API_KEY not found (required only for RAG answer generation)")
