"""Quick diagnostic: check retrieval quality for failing queries."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from retriever.context_selector import retrieve_top_k_chunks

QUERIES = [
    ("สอบ CMU-eGrad ปี 2568 วันไหน", ["CMU-eGrad", "กันยายน"]),
    ("ปิดเทอม 1/2568 วันไหน", ["4 พฤศจิกายน", "ปิด"]),
    ("เปิดเทอม 2/2568 วันไหน", ["17 พฤศจิกายน", "เปิด"]),
]

FOLDER = os.path.join(os.path.dirname(__file__), "..", "app", "static", "quick_use")

for query, keywords in QUERIES:
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"Expected keywords: {keywords}")
    print("-" * 60)
    
    chunks = retrieve_top_k_chunks(
        query, k=5, folder=FOLDER,
        use_hybrid=True, use_rerank=True, use_intent_analysis=True,
    )
    
    if not chunks:
        print("  NO CHUNKS RETRIEVED!")
        continue
    
    for i, (chunk_data, score) in enumerate(chunks):
        text = chunk_data.get("chunk", "")[:200]
        source = chunk_data.get("source", "?")
        print(f"  [{i+1}] score={score:.3f} src={source}")
        print(f"      {text}")
        
        # Check if any keyword is in this chunk
        for kw in keywords:
            if kw in chunk_data.get("chunk", ""):
                print(f"      ✅ Contains '{kw}'")

print("\n" + "=" * 60)
print("Done.")
