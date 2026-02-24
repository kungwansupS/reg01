"""Debug: find CMU-eGrad chunks and test why search misses them."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chromadb

db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "db", "chroma_data")
c = chromadb.PersistentClient(path=db_path)
col = c.get_or_create_collection("reg_context")
r = col.get(include=["documents", "metadatas"])

print("=== Chunks containing CMU-eGrad ===")
egrad_indices = []
for i, (doc, meta) in enumerate(zip(r["documents"], r["metadatas"])):
    if "CMU-eGrad" in doc or "eGrad" in doc:
        egrad_indices.append(i)
        print(f"\nCHUNK [{i}] (chunk_index={meta.get('chunk_index')}):")
        print(f"  doc_type: {meta.get('doc_type')}")
        print(f"  Full text ({len(doc)} chars):")
        print(doc[:800])
        print("..." if len(doc) > 800 else "")

if not egrad_indices:
    print("  NO CHUNKS FOUND!")

# Now test semantic search for this query
print("\n=== Semantic search test ===")
from sentence_transformers import SentenceTransformer
import torch

device = 'cuda' if torch.cuda.is_available() else 'cpu'
model_name = "BAAI/bge-m3" if device == 'cuda' else "intfloat/multilingual-e5-small"
model = SentenceTransformer(model_name, device=device)

query = "สอบ CMU-eGrad ปี 2568 วันไหน"
query_emb = model.encode(f"query: {query}", normalize_embeddings=True).tolist()

# Search without filters
results = col.query(query_embeddings=[query_emb], n_results=5)
print(f"\nTop 5 results for '{query}':")
for i in range(len(results["documents"][0])):
    doc = results["documents"][0][i][:150]
    dist = results["distances"][0][i]
    meta = results["metadatas"][0][i]
    has_egrad = "CMU-eGrad" in results["documents"][0][i]
    print(f"  [{i}] dist={dist:.4f} sim={1-dist:.4f} eGrad={has_egrad} idx={meta.get('chunk_index')}")
    print(f"       {doc}...")

# Search with doc_type filter
print(f"\nTop 5 with doc_type=calendar:")
results2 = col.query(query_embeddings=[query_emb], n_results=5, where={"doc_type": "calendar"})
for i in range(len(results2["documents"][0])):
    doc = results2["documents"][0][i][:150]
    dist = results2["distances"][0][i]
    has_egrad = "CMU-eGrad" in results2["documents"][0][i]
    print(f"  [{i}] dist={dist:.4f} sim={1-dist:.4f} eGrad={has_egrad}")
    print(f"       {doc}...")
