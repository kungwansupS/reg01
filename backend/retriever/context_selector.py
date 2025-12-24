import os
import torch
import threading
from sentence_transformers import SentenceTransformer, util
from dotenv import load_dotenv
from app.config import PDF_QUICK_USE_FOLDER, debug_list_files

load_dotenv()
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"====== use {device} for embedding ======")

# เลือกระดับความแม่นยำตาม Hardware
if device == 'cuda':
    model_name = "BAAI/bge-m3"
else:
    model_name = "intfloat/multilingual-e5-small"

print(f"use model {model_name}")
embedding_model = SentenceTransformer(model_name, device=device)

# ------------------------------------------------------------------
# Global Cache & Lock
# ------------------------------------------------------------------
_chunks_cache = []
_cache_lock = threading.Lock()
_embedding_lock = threading.Lock()

def get_file_chunks(folder=PDF_QUICK_USE_FOLDER, separator="===================", force_reload=False):
    """
    ดึงข้อมูล Chunks จากไฟล์ พร้อมระบบ Caching เพื่อลดการอ่าน Disk
    """
    global _chunks_cache
    
    with _cache_lock:
        if _chunks_cache and not force_reload:
            return _chunks_cache

        debug_list_files(folder, "📄 Quick-use TXT files")
        new_chunks = []
        
        if not os.path.exists(folder):
            return []

        for root, _, files in os.walk(folder):
            for filename in sorted(files):
                if filename.endswith(".txt"):
                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        parts = content.split(separator)
                        for i, chunk in enumerate(parts):
                            chunk = chunk.strip()
                            if chunk:
                                new_chunks.append({
                                    "chunk": chunk,
                                    "source": filepath,
                                    "index": i
                                })
                    except Exception as e:
                        print(f"❌ Error reading {filename}: {e}")
        
        _chunks_cache = new_chunks
        return _chunks_cache

def retrieve_top_k_chunks(query, k=5, folder=PDF_QUICK_USE_FOLDER):
    """
    ค้นหาข้อมูลที่ใกล้เคียงที่สุดโดยใช้ Vector Search
    """
    all_chunks = get_file_chunks(folder)
    if not all_chunks:
        return []

    passages = [f"passage: {entry['chunk']}" for entry in all_chunks]

    # ใช้ Lock เพื่อความปลอดภัยในการทำ Inference พร้อมกันหลาย Thread
    with _embedding_lock:
        query_embedding = embedding_model.encode(
            f"query: {query}", 
            convert_to_tensor=True, 
            normalize_embeddings=True
        )
        chunk_embeddings = embedding_model.encode(
            passages, 
            convert_to_tensor=True, 
            normalize_embeddings=True
        )

        scores = util.dot_score(query_embedding, chunk_embeddings)[0].tolist()
    
    scored_chunks = [(entry, score) for entry, score in zip(all_chunks, scores)]
    scored_chunks.sort(key=lambda x: x[1], reverse=True)

    return scored_chunks[:k]