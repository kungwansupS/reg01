"""Inspect ChromaDB chunks to find missing content."""
import chromadb
import os

# Use the same path as the server (run from project root)
db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "db", "chroma_data")
print(f"DB path: {os.path.abspath(db_path)}")

c = chromadb.PersistentClient(path=db_path)
col = c.get_or_create_collection("reg_context")
results = col.get(include=["documents", "metadatas"])

ids = results["ids"]
docs = results["documents"]
metas = results["metadatas"]

print(f"Total chunks: {len(ids)}")
print()

# Search for specific keywords
search_terms = ["CMU-eGrad", "ปิดภาคการศึกษา", "เปิดภาคการศึกษา", "4 พฤศจิกายน", "17 พฤศจิกายน", "กันยายน"]

for term in search_terms:
    print(f"--- Searching for '{term}' ---")
    found = False
    for i, (doc, meta) in enumerate(zip(docs, metas)):
        if term in doc:
            found = True
            # Show context around the match
            idx = doc.index(term)
            start = max(0, idx - 50)
            end = min(len(doc), idx + len(term) + 80)
            snippet = doc[start:end].replace("\n", " ")
            print(f"  [{i}] meta={meta}")
            print(f"       ...{snippet}...")
    if not found:
        print(f"  NOT FOUND in any chunk!")
    print()

# Also show all chunk summaries
print("=== ALL CHUNKS ===")
for i, (doc, meta) in enumerate(zip(docs, metas)):
    first_line = doc[:150].replace("\n", " ")
    print(f"  [{i}] meta={meta}")
    print(f"       {first_line}...")
