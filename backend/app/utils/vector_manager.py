import os
import sqlite3
import hashlib
import logging
import datetime
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import torch

logger = logging.getLogger("VectorManager")

class VectorManager:
    def __init__(self):
        # ตั้งค่า Path สำหรับฐานข้อมูล
        self.db_dir = os.path.join("data", "db")
        os.makedirs(self.db_dir, exist_ok=True)
        
        self.sqlite_path = os.path.join(self.db_dir, "metadata.db")
        self.chroma_path = os.path.join(self.db_dir, "chroma_data")
        
        # เตรียม Device สำหรับ Embedding
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model_name = "BAAI/bge-m3" if self.device == 'cuda' else "intfloat/multilingual-e5-small"
        self._model = None # Lazy load
        
        # เชื่อมต่อ Database
        self._init_sqlite()
        self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
        self.collection = self.chroma_client.get_or_create_collection(name="reg_context")

    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name} on {self.device}")
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def _init_sqlite(self):
        """สร้างตารางสำหรับเก็บ File Hash เพื่อเช็คความเปลี่ยนแปลง"""
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_registry (
                    file_path TEXT PRIMARY KEY,
                    file_hash TEXT,
                    last_updated DATETIME
                )
            """)
            conn.commit()

    def get_file_hash(self, filepath):
        """คำนวณ SHA-256 ของไฟล์"""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def needs_update(self, filepath):
        """เช็คว่าไฟล์ต้องอัปเดตลง DB หรือไม่"""
        current_hash = self.get_file_hash(filepath)
        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.execute("SELECT file_hash FROM file_registry WHERE file_path = ?", (filepath,))
            row = cursor.fetchone()
            if row is None or row[0] != current_hash:
                return True, current_hash
        return False, current_hash

    def update_registry(self, filepath, file_hash):
        """บันทึกประวัติการอัปเดตไฟล์"""
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO file_registry (file_path, file_hash, last_updated) VALUES (?, ?, ?)",
                (filepath, file_hash, datetime.datetime.now())
            )
            conn.commit()

    def add_document(self, filepath, chunks):
        """นำ Chunks ของไฟล์เข้าสู่ Vector DB"""
        # ลบข้อมูลเก่าของไฟล์นี้ออกก่อน (ถ้ามี)
        self.collection.delete(where={"source": filepath})
        
        if not chunks:
            return

        ids = [f"{filepath}_{i}" for i in range(len(chunks))]
        metadatas = [{"source": filepath, "index": i} for i in range(len(chunks))]
        
        # สร้าง Embeddings
        embeddings = self.model.encode(
            [f"passage: {c}" for c in chunks],
            normalize_embeddings=True
        ).tolist()

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )
        logger.info(f"✅ Indexed {len(chunks)} chunks from {os.path.basename(filepath)}")

    def search(self, query, k=5):
        """ค้นหาข้อมูลที่ใกล้เคียงที่สุด"""
        query_embedding = self.model.encode(
            f"query: {query}",
            normalize_embeddings=True
        ).tolist()

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )

        formatted_results = []
        if results['documents']:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    "chunk": results['documents'][0][i],
                    "source": results['metadatas'][0][i]['source'],
                    "score": results['distances'][0][i]
                })
        return formatted_results

# Create a singleton instance
vector_manager = VectorManager()