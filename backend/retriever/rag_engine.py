import os
import hashlib
import uuid
from typing import List, Dict, Any

# LangChain & Qdrant Integration
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

# App Config
from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME, PDF_QUICK_USE_FOLDER, QDRANT_PATH

# ==========================================
# 1. Setup Embedding & Vector DB
# ==========================================

print("⚡ Initializing RAG Engine...")

# ใช้ EmbeddingGemma ตาม Requirement
embeddings = HuggingFaceEmbeddings(
    model_name="google/embeddinggemma-300M",
    model_kwargs={'device': 'cpu'}, 
    encode_kwargs={'normalize_embeddings': True}
)

# Dynamic Dimension Detection (ป้องกัน Hardcode)
try:
    dummy_vector = embeddings.embed_query("test")
    EMBEDDING_SIZE = len(dummy_vector)
    print(f"   - Embedding Model Loaded (Dim: {EMBEDDING_SIZE})")
except Exception as e:
    print(f"❌ Error loading embeddings: {e}")
    EMBEDDING_SIZE = 768 # Fallback

# Setup Qdrant Client (Persistent)
# ตรวจสอบว่า folder ปลายทางมีอยู่จริงหรือไม่ ถ้าไม่มีให้สร้าง
if not os.path.exists(QDRANT_PATH):
    os.makedirs(QDRANT_PATH, exist_ok=True)

qdrant_client = QdrantClient(path=QDRANT_PATH)
COLLECTION_NAME = "reg_knowledge_base"

# Create Collection if not exists
if not qdrant_client.collection_exists(COLLECTION_NAME):
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_SIZE, distance=Distance.COSINE),
    )
    print(f"   - Created new Qdrant collection: {COLLECTION_NAME}")
else:
    print(f"   - Connected to existing Qdrant collection: {COLLECTION_NAME}")

# Connect LangChain to Qdrant
vector_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=COLLECTION_NAME,
    embedding=embeddings,
)

# ==========================================
# 2. Utility Functions
# ==========================================

def generate_file_hash(filepath: str) -> str:
    """สร้าง Hash MD5 จากเนื้อหาไฟล์ เพื่อใช้เป็น Unique ID ของเอกสาร"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

# ==========================================
# 3. Ingestion Logic
# ==========================================

def run_ingestion():
    """
    ฟังก์ชันสำหรับ Index ข้อมูลเข้า Vector DB
    คุณสมบัติ:
    - Idempotency: รันซ้ำได้ ไม่เกิดข้อมูลขยะ (ใช้ Hash ID)
    - Metadata: เก็บชื่อไฟล์, ID, Index
    - Optimized Chunking: ตัดคำแบบมี Overlap
    """
    print(f"\n🚀 Starting Ingestion Process from: {PDF_QUICK_USE_FOLDER}")
    
    if not os.path.exists(PDF_QUICK_USE_FOLDER):
        print(f"❌ Folder not found: {PDF_QUICK_USE_FOLDER}")
        return

    # Scan files manually to control ID generation
    files = []
    for root, _, filenames in os.walk(PDF_QUICK_USE_FOLDER):
        for filename in filenames:
            if filename.lower().endswith(".txt"): # รองรับ .txt (อนาคตเพิ่ม .pdf ที่นี่)
                files.append(os.path.join(root, filename))
    
    if not files:
        print("⚠️ No text files found to ingest.")
        return

    # Text Splitter Configuration
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=150,
        separators=["\n\n", "\n", " ", ""],
        add_start_index=True
    )

    documents_to_upsert = []
    ids_to_upsert = []
    
    print(f"   - Found {len(files)} files. Processing...")

    for filepath in files:
        try:
            # 1. Generate Doc ID based on Content Hash
            file_hash = generate_file_hash(filepath)
            doc_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, file_hash))
            filename = os.path.basename(filepath)

            # 2. Load Text
            loader = TextLoader(filepath, encoding='utf-8')
            raw_docs = loader.load()

            # 3. Split & Inject Metadata
            chunks = text_splitter.split_documents(raw_docs)
            
            for i, chunk in enumerate(chunks):
                # Deterministic Chunk ID: Hash(DocID + Index) -> เหมือนเดิมเสมอถ้ารันซ้ำ
                chunk_id = hashlib.md5(f"{doc_uuid}_{i}".encode()).hexdigest()
                
                # Update Metadata
                chunk.metadata["doc_id"] = doc_uuid
                chunk.metadata["file_hash"] = file_hash
                chunk.metadata["original_filename"] = filename
                chunk.metadata["chunk_index"] = i
                
                documents_to_upsert.append(chunk)
                ids_to_upsert.append(chunk_id)
                
        except Exception as e:
            print(f"❌ Failed to process {filepath}: {e}")

    # 4. Batch Upsert to Qdrant
    if documents_to_upsert:
        vector_store.add_documents(documents=documents_to_upsert, ids=ids_to_upsert)
        print(f"✅ Successfully upserted {len(documents_to_upsert)} chunks to Qdrant.")
        print(f"   - Storage Path: {QDRANT_PATH}")
    else:
        print("⚠️ No valid chunks generated.")

# ==========================================
# 4. Retrieval Logic (RAG)
# ==========================================

def ask_rag(query: str) -> Dict[str, Any]:
    """
    ฟังก์ชัน RAG หลัก
    - ใช้ MMR เพื่อเพิ่ม Diversity ของข้อมูล
    - คืนค่า Answer + Citations
    """
    # 1. Setup LLM
    if not GEMINI_API_KEY:
        return {"answer": "❌ Error: GEMINI_API_KEY not found in environment.", "citations": []}

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL_NAME,
        google_api_key=GEMINI_API_KEY,
        temperature=0.3
    )

    # 2. Setup Retriever with MMR (Maximal Marginal Relevance)
    retriever = vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 5,             # จำนวน chunks ที่ต้องการสุดท้าย
            "fetch_k": 20,      # จำนวน chunks ที่ดึงมาพิจารณาตอนแรก
            "lambda_mult": 0.5  # Balance: 0.5 (กลางๆ), 1.0 (เหมือน similarity ปกติ)
        }
    )

    # 3. Prompt Template
    system_prompt = (
        "คุณเป็นผู้ช่วยอัจฉริยะของงานทะเบียน REG "
        "จงตอบคำถามโดยอ้างอิงข้อมูลจาก Context ด้านล่างนี้เท่านั้น "
        "หากข้อมูลใน Context ไม่เพียงพอ ให้ตอบว่า 'ไม่ทราบข้อมูลในเอกสารที่มี' อย่าแต่งเอง\n\n"
        "--- Context ---\n"
        "{context}\n"
        "---------------"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    # 4. Create Chain
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

    # 5. Invoke & Format Result
    try:
        response = rag_chain.invoke({"input": query})
        
        answer = response["answer"]
        context_docs = response["context"]
        
        # Extract Citations
        citations = []
        seen = set()
        for doc in context_docs:
            fname = doc.metadata.get("original_filename", "unknown")
            # ถ้าเป็น PDF อาจจะมี page number (เตรียมไว้สำหรับอนาคต)
            page = doc.metadata.get("page", None)
            
            ref = fname
            if page is not None:
                ref += f" (Page {page + 1})"
            
            if ref not in seen:
                citations.append(ref)
                seen.add(ref)
        
        return {
            "answer": answer,
            "citations": citations,
            "source_documents": context_docs # เก็บไว้ debug ถ้าต้องการ
        }

    except Exception as e:
        print(f"❌ RAG Error: {e}")
        return {"answer": "ขออภัย เกิดข้อผิดพลาดในการประมวลผลคำตอบ", "citations": []}

# Test block (ทำงานเมื่อรันไฟล์นี้ตรงๆ)
if __name__ == "__main__":
    # Test Ingestion
    run_ingestion()
    
    # Test Query
    test_query = "การลงทะเบียนเรียนต้องทำอย่างไร?"
    print(f"\n❓ Query: {test_query}")
    result = ask_rag(test_query)
    print(f"💡 Answer: {result['answer']}")
    print(f"📚 Citations: {result['citations']}")