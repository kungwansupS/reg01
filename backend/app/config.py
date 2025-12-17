import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    # --- Base Paths ---
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    BACKEND_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / "data"
    DOCS_DIR = BACKEND_DIR / "app" / "static" / "docs"
    QUICK_USE_DIR = BACKEND_DIR / "app" / "static" / "quick_use"
    
    # Ensure directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    
    # --- LLM Settings (Gemini) ---
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    LLM_MODEL_NAME = "gemini-1.5-flash"
    LLM_TEMPERATURE = 0.3  # Low temperature for factual RAG
    
    # --- Embedding Settings (Gemma) ---
    # Using the exact model requested
    EMBEDDING_MODEL_NAME = "google/embeddinggemma-300m" 
    EMBEDDING_DEVICE = "cpu" # Change to "cuda" if GPU is available
    NORMALIZE_EMBEDDINGS = True
    
    # --- Vector DB Settings (Qdrant) ---
    QDRANT_PATH = DATA_DIR / "qdrant_data"
    COLLECTION_NAME = "reg_knowledge_base"
    VECTOR_SIZE = 768  # Gemma-300M usually outputs 768 dimensions (need verify at runtime)
    DISTANCE_METRIC = "Cosine"
    
    # --- Ingestion Settings ---
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 150
    
    # --- Retrieval Settings ---
    SEARCH_TYPE = "mmr"
    FETCH_K = 20
    K = 5
    LAMBDA_MULT = 0.5

settings = Settings()