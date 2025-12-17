from ingest import ingest
from rag_query import ask

print("=== RUN RAG INGEST ===")
ingest()

print("\n=== RUN RAG QUERY TEST ===")
result = ask("ลงทะเบียนเรียนได้เมื่อไหร่")

print("\nANSWER:")
print(result["answer"])

print("\nSOURCES:")
for src in result["sources"]:
    print("-", src)
