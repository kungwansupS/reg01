import sys
import os

# Add backend to path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from backend.retriever.rag_engine import run_ingestion

if __name__ == "__main__":
    print("📢 Starting Manual Ingestion...")
    run_ingestion()
    print("🎉 Ingestion Finished!")