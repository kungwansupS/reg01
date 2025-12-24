import os
import torch
from sentence_transformers import SentenceTransformer, util
from dotenv import load_dotenv
from app.config import PDF_QUICK_USE_FOLDER, debug_list_files

load_dotenv()
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print ("======use "+ device +" for embedding======")

# intfloat/multilingual-e5-small เร็ว/พอใช้
# BAAI/bge-m3 ช้า/แม่น

if device == 'cuda':
    model_name = "BAAI/bge-m3"
else:
    model_name = "intfloat/multilingual-e5-small"
print ("use model " + model_name)
embedding_model = SentenceTransformer(model_name, device=device)

def get_file_chunks(folder=PDF_QUICK_USE_FOLDER, separator="==================="):
    debug_list_files(PDF_QUICK_USE_FOLDER, "📄 Quick-use TXT files")
    chunks = []
    for root, _, files in os.walk(folder):
        for filename in sorted(files):
            if filename.endswith(".txt"):
                filepath = os.path.join(root, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                parts = content.split(separator)
                for i, chunk in enumerate(parts):
                    chunk = chunk.strip()
                    if chunk:
                        chunks.append({
                            "chunk": chunk,
                            "source": filepath,
                            "index": i
                        })
    return chunks

def retrieve_top_k_chunks(query, k=5, folder=PDF_QUICK_USE_FOLDER):
    all_chunks = get_file_chunks(folder)
    passages = [f"passage: {entry['chunk']}" for entry in all_chunks]

    query_embedding = embedding_model.encode(f"query: {query}", convert_to_tensor=True, normalize_embeddings=True)
    chunk_embeddings = embedding_model.encode(passages, convert_to_tensor=True, normalize_embeddings=True)

    scores = util.dot_score(query_embedding, chunk_embeddings)[0].tolist()
    scored_chunks = [(entry, score) for entry, score in zip(all_chunks, scores)]
    scored_chunks.sort(key=lambda x: x[1], reverse=True)

    return scored_chunks[:k]
