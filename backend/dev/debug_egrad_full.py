"""Debug the full retrieval pipeline for CMU-eGrad query."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chromadb
from sentence_transformers import SentenceTransformer
import torch

# Connect to the SAME DB as the server
db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "db", "chroma_data")
c = chromadb.PersistentClient(path=db_path)
col = c.get_or_create_collection("reg_context")

# Check which chunks have CMU-eGrad
r = col.get(include=["documents", "metadatas"])
print("=== CMU-eGrad chunks in DB ===")
egrad_ids = []
for i, (doc_id, doc, meta) in enumerate(zip(r["ids"], r["documents"], r["metadatas"])):
    if "CMU-eGrad" in doc:
        egrad_ids.append(doc_id)
        print(f"  ID: {doc_id}")
        print(f"  doc_type: {meta.get('doc_type')}")
        print(f"  chunk_index: {meta.get('chunk_index')}")
        print(f"  Text length: {len(doc)}")
        # Find where CMU-eGrad appears
        idx = doc.index("CMU-eGrad")
        print(f"  CMU-eGrad at char position: {idx}")
        print(f"  Context: ...{doc[max(0,idx-30):idx+80]}...")
        print()

# Test search with doc_type=calendar filter
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model_name = "BAAI/bge-m3" if device == 'cuda' else "intfloat/multilingual-e5-small"
model = SentenceTransformer(model_name, device=device)

query = "สอบ CMU-eGrad ปี 2568 วันไหน"
query_emb = model.encode(f"query: {query}", normalize_embeddings=True).tolist()

print("=== Search with doc_type=calendar filter (k=15) ===")
results = col.query(query_embeddings=[query_emb], n_results=15, where={"doc_type": "calendar"})
found_egrad = False
for i in range(len(results["ids"][0])):
    doc_id = results["ids"][0][i]
    doc = results["documents"][0][i]
    dist = results["distances"][0][i]
    has = "CMU-eGrad" in doc
    if has:
        found_egrad = True
    print(f"  [{i}] id={doc_id[-20:]} dist={dist:.4f} eGrad={has}")

if not found_egrad:
    print("  >>> CMU-eGrad NOT FOUND in filtered results!")
    print()
    print("=== Search WITHOUT filter (k=15) ===")
    results2 = col.query(query_embeddings=[query_emb], n_results=15)
    for i in range(len(results2["ids"][0])):
        doc_id = results2["ids"][0][i]
        doc = results2["documents"][0][i]
        dist = results2["distances"][0][i]
        has = "CMU-eGrad" in doc
        print(f"  [{i}] id={doc_id[-20:]} dist={dist:.4f} eGrad={has}")

# Check total collection count
print(f"\nTotal documents in collection: {col.count()}")
print(f"CMU-eGrad chunk IDs: {egrad_ids}")
