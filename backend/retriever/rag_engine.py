import os
import hashlib
import uuid
from typing import List, Dict, Any

# --- Modern LangChain Imports (v0.2/v0.3 Compatible) ---
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

# Explicit Import Paths (Fix for ModuleNotFoundError)
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain

# App Config
from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME, PDF_QUICK_USE_FOLDER, QDRANT_PATH

# ==========================================
# 1. Setup Embedding & Vector DB
# ==========================================

print("⚡ Initializing RAG Engine...")

# Embedding Setup
embeddings = HuggingFaceEmbeddings(
    model_name="google/embeddinggemma-300M",
    model_kwargs={'device': 'cpu'}, 
    encode_kwargs={'normalize_embeddings': True}
)

# Dynamic Dimension Check
try:
    dummy_vector = embeddings.embed_query("test")
    EMBEDDING_SIZE = len(dummy_vector)
    print(f"   - Embedding Model: EmbeddingGemma (Dim: {EMBEDDING_SIZE})")
except Exception as e:
    print(f"❌ Error loading embeddings: {e}")
    EMBEDDING_SIZE = 768

# Qdrant Client Setup (Persistent)
qdrant_client = QdrantClient(path=QDRANT_PATH)
COLLECTION_NAME = "reg_knowledge_base"

if not qdrant_client.collection_exists(COLLECTION_NAME):
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_SIZE, distance=Distance.COSINE),
    )
    print(f"   - Created Qdrant Collection: {COLLECTION_NAME}")
else:
    print(f"   - Connected to Qdrant Collection: {COLLECTION_NAME}")

vector_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=COLLECTION_NAME,
    embedding=embeddings,
)

# ==========================================
# 2. Ingestion Logic
# ==========================================

def generate_file_hash(filepath: str) -> str:
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def run_ingestion():
    print(f"\n🚀 Starting Ingestion from: {PDF_QUICK_USE_FOLDER}")
    
    files = []
    for root, _, filenames in os.walk(PDF_QUICK_USE_FOLDER):
        for filename in filenames:
            if filename.lower().endswith(".txt"):
                files.append(os.path.join(root, filename))
    
    if not files:
        print("⚠️ No text files found to ingest.")
        return

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
            file_hash = generate_file_hash(filepath)
            doc_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, file_hash))
            filename = os.path.basename(filepath)

            loader = TextLoader(filepath, encoding='utf-8')
            raw_docs = loader.load()

            chunks = text_splitter.split_documents(raw_docs)
            
            for i, chunk in enumerate(chunks):
                chunk_id = hashlib.md5(f"{doc_uuid}_{i}".encode()).hexdigest()
                
                chunk.metadata["doc_id"] = doc_uuid
                chunk.metadata["file_hash"] = file_hash
                chunk.metadata["original_filename"] = filename
                chunk.metadata["chunk_index"] = i
                
                documents_to_upsert.append(chunk)
                ids_to_upsert.append(chunk_id)
                
        except Exception as e:
            print(f"❌ Failed to process {filepath}: {e}")

    if documents_to_upsert:
        vector_store.add_documents(documents=documents_to_upsert, ids=ids_to_upsert)
        print(f"✅ Ingestion Complete: {len(documents_to_upsert)} chunks upserted.")
    else:
        print("⚠️ No valid chunks generated.")

# ==========================================
# 3. Retrieval Logic (RAG)
# ==========================================

def ask_rag(query: str) -> Dict[str, Any]:
    if not GEMINI_API_KEY:
        return {"answer": "Error: GEMINI_API_KEY is missing.", "citations": []}

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL_NAME,
        google_api_key=GEMINI_API_KEY,
        temperature=0.3
    )

    # Use MMR for diversity
    retriever = vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 5, "fetch_k": 20, "lambda_mult": 0.5}
    )

    system_prompt = (
        "คุณเป็นผู้ช่วยอัจฉริยะของงานทะเบียน REG "
        "จงตอบคำถามโดยอ้างอิงข้อมูลจาก Context ด้านล่างนี้เท่านั้น "
        "หากข้อมูลไม่เพียงพอ ให้ตอบว่า 'ไม่ทราบข้อมูลในเอกสารที่มี' อย่าแต่งเอง\n\n"
        "--- Context ---\n"
        "{context}\n"
        "---------------"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

    try:
        response = rag_chain.invoke({"input": query})
        
        citations = []
        seen = set()
        for doc in response.get("context", []):
            fname = doc.metadata.get("original_filename", "unknown")
            if fname not in seen:
                citations.append(fname)
                seen.add(fname)
        
        return {
            "answer": response["answer"],
            "citations": citations
        }

    except Exception as e:
        print(f"❌ RAG Error: {e}")
        return {"answer": "เกิดข้อผิดพลาดในระบบ RAG", "citations": []}