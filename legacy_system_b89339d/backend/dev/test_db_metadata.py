"""Check what metadata values exist in ChromaDB."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils.vector_manager import vector_manager

# Get all chunks from the collection
results = vector_manager.collection.get(include=["metadatas", "documents"])

print(f"Total chunks in DB: {len(results['ids'])}")
print()

# Collect unique metadata values
doc_types = set()
academic_years = set()
semesters = set()

for i, meta in enumerate(results['metadatas']):
    doc_types.add(meta.get('doc_type', 'NONE'))
    academic_years.add(meta.get('academic_years', 'NONE'))
    semesters.add(meta.get('semesters', 'NONE'))

print(f"doc_type values: {doc_types}")
print(f"academic_years values: {academic_years}")
print(f"semesters values: {semesters}")

# Check which chunks contain CMU-eGrad
print()
print("Chunks containing 'CMU-eGrad':")
for i, doc in enumerate(results['documents']):
    if 'CMU-eGrad' in doc:
        meta = results['metadatas'][i]
        print(f"  Chunk #{i}: doc_type={meta.get('doc_type')}, academic_years={meta.get('academic_years')}")
        print(f"  Preview: {doc[:200]}")
        print()

# Check which chunks contain 'ปิดภาคการศึกษา'
print("Chunks containing 'ปิดภาคการศึกษา':")
for i, doc in enumerate(results['documents']):
    if 'ปิดภาคการศึกษา' in doc:
        meta = results['metadatas'][i]
        print(f"  Chunk #{i}: doc_type={meta.get('doc_type')}, source={meta.get('source','')[-40:]}")
        print()
