"""Fix duplicate chunks in ChromaDB caused by different path casing."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chromadb

db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "db", "chroma_data")
c = chromadb.PersistentClient(path=db_path)
col = c.get_or_create_collection("reg_context")

r = col.get(include=["documents", "metadatas"])
ids = r["ids"]
docs = r["documents"]
metas = r["metadatas"]

print(f"Total chunks before: {len(ids)}")

# Find duplicates by normalizing chunk_index + source filename
seen = {}
duplicates = []
for doc_id, doc, meta in zip(ids, docs, metas):
    # Normalize the key: lowercase source path + chunk_index
    source = meta.get("source", "").lower().replace("\\", "/")
    chunk_idx = meta.get("chunk_index", -1)
    key = f"{source}:{chunk_idx}"
    
    if key in seen:
        duplicates.append(doc_id)
        print(f"  Duplicate: {doc_id}")
    else:
        seen[key] = doc_id

if duplicates:
    print(f"\nRemoving {len(duplicates)} duplicates...")
    col.delete(ids=duplicates)
    print(f"Total chunks after: {col.count()}")
else:
    print("No duplicates found.")
