import os
import re
import sqlite3
import hashlib
import logging
import datetime
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import torch
from typing import List, Dict, Optional

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

    def remove_from_registry(self, filepath: str):
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute("DELETE FROM file_registry WHERE file_path = ?", (filepath,))
            conn.commit()

    def purge_out_of_scope(self, valid_paths: set[str], allowed_root: str) -> Dict[str, int]:
        normalized_valid = {os.path.normcase(os.path.abspath(path)) for path in valid_paths}
        normalized_root = os.path.normcase(os.path.abspath(allowed_root))
        root_with_sep = normalized_root + os.sep

        try:
            rows = self.collection.get(include=["metadatas", "documents"])
        except Exception as exc:
            logger.error(f"Failed to enumerate existing vectors: {exc}")
            return {"removed_ids": 0, "removed_sources": 0}

        ids = rows.get("ids", []) or []
        metadatas = rows.get("metadatas", []) or []
        documents = rows.get("documents", []) or []
        if not ids:
            return {"removed_ids": 0, "removed_sources": 0}

        remove_ids = []
        remove_sources = set()
        for row_id, metadata, document in zip(ids, metadatas, documents):
            source = str((metadata or {}).get("source") or "").strip()
            if not source:
                continue
            normalized_source = os.path.normcase(os.path.abspath(source))
            in_root = (
                normalized_source == normalized_root
                or normalized_source.startswith(root_with_sep)
            )
            doc_text = str(document or "").strip()
            doc_alnum = len(re.findall(r"[A-Za-z0-9\u0E00-\u0E7F]", doc_text))
            is_noisy_doc = doc_alnum < 10
            if (not in_root) or (normalized_source not in normalized_valid) or is_noisy_doc:
                remove_ids.append(row_id)
                remove_sources.add(source)

        if remove_ids:
            self.collection.delete(ids=remove_ids)
            for source in remove_sources:
                self.remove_from_registry(source)
            logger.info(
                "Purged %s stale chunks from %s sources",
                len(remove_ids),
                len(remove_sources),
            )

        return {"removed_ids": len(remove_ids), "removed_sources": len(remove_sources)}

    def add_document(self, filepath: str, chunks: List[str], metadata: Optional[Dict] = None):
        """
        นำ Chunks ของไฟล์เข้าสู่ Vector DB พร้อม metadata
        
        Args:
            filepath: Path to source file
            chunks: List of text chunks
            metadata: Document-level metadata (from metadata_extractor)
        """
        # ลบข้อมูลเก่าของไฟล์นี้ออกก่อน (ถ้ามี)
        self.collection.delete(where={"source": filepath})
        
        if not chunks:
            logger.warning(f"⚠️ No chunks to index for {filepath}")
            return

        # Prepare metadata for each chunk
        base_metadata = metadata or {}
        ids = [f"{filepath}_{i}" for i in range(len(chunks))]
        metadatas = []
        
        for i in range(len(chunks)):
            chunk_metadata = {
                "source": filepath,
                "filename": base_metadata.get('filename', os.path.basename(filepath)),
                "chunk_index": i,
                "doc_type": base_metadata.get('doc_type', 'general'),
                "language": base_metadata.get('language', 'th'),
                "has_dates": base_metadata.get('has_dates', False),
                "last_updated": base_metadata.get('last_updated', datetime.datetime.now().isoformat())
            }
            
            # Add academic_years and semesters as JSON strings (ChromaDB limitation)
            if 'academic_years' in base_metadata and base_metadata['academic_years']:
                chunk_metadata['academic_years'] = ','.join(base_metadata['academic_years'])
            
            if 'semesters' in base_metadata and base_metadata['semesters']:
                chunk_metadata['semesters'] = ','.join(map(str, base_metadata['semesters']))
            
            metadatas.append(chunk_metadata)
        
        # สร้าง Embeddings
        embeddings = self.model.encode(
            [f"passage: {c}" for c in chunks],
            normalize_embeddings=True
        ).tolist()

        # Add to ChromaDB
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )
        
        logger.info(f"✅ Indexed {len(chunks)} chunks from {os.path.basename(filepath)}")

    def search(self, query: str, k: int = 5, filter_dict: Optional[Dict] = None) -> List[Dict]:
        """
        ค้นหาข้อมูลที่ใกล้เคียงที่สุด พร้อมกรอง metadata
        
        Args:
            query: Search query
            k: Number of results (จะดึงมากขึ้นเพื่อ post-filter)
            filter_dict: Metadata filters (e.g., {'doc_type': 'calendar', 'academic_year': '2568'})
        
        Returns:
            List of dicts with chunk, source, score, metadata
        """
        # Create query embedding
        query_embedding = self.model.encode(
            f"query: {query}",
            normalize_embeddings=True
        ).tolist()

        # ChromaDB รองรับ filter เดียวต่อ query
        # Strategy: ใช้ filter ที่สำคัญที่สุดก่อน แล้ว post-filter ที่เหลือ
        where_clause = None
        post_filters = {}
        
        if filter_dict:
            # Priority 1: doc_type (ถ้ามี)
            if 'doc_type' in filter_dict:
                where_clause = {'doc_type': filter_dict['doc_type']}
                logger.debug(f"🔍 Pre-filter: doc_type={filter_dict['doc_type']}")
            
            # Priority 2: language (ถ้าไม่มี doc_type)
            elif 'language' in filter_dict:
                where_clause = {'language': filter_dict['language']}
                logger.debug(f"🔍 Pre-filter: language={filter_dict['language']}")
            
            # เก็บ filters อื่นไว้สำหรับ post-processing
            if 'academic_year' in filter_dict:
                post_filters['academic_year'] = filter_dict['academic_year']
            
            if 'semester' in filter_dict:
                post_filters['semester'] = str(filter_dict['semester'])

        # Query ChromaDB with increased k for post-filtering
        query_k = k * 3 if post_filters else k
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=query_k,
                where=where_clause
            )
        except Exception as e:
            logger.error(f"❌ ChromaDB query error: {e}")
            # Fallback: query without filters
            try:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=query_k
                )
            except Exception as e2:
                logger.error(f"❌ Fallback query failed: {e2}")
                return []

        # Format results
        formatted_results = []
        if results['documents'] and results['documents'][0]:
            for i in range(len(results['documents'][0])):
                metadata = results['metadatas'][0][i]
                
                # Post-filter: ตรวจสอบ academic_year และ semester
                if post_filters:
                    # Filter by academic_year
                    if 'academic_year' in post_filters:
                        academic_years = metadata.get('academic_years', '')
                        if post_filters['academic_year'] not in academic_years:
                            continue
                    
                    # Filter by semester
                    if 'semester' in post_filters:
                        semesters = metadata.get('semesters', '')
                        if post_filters['semester'] not in semesters:
                            continue
                
                formatted_results.append({
                    "chunk": results['documents'][0][i],
                    "source": metadata.get('source', ''),
                    "score": 1.0 - results['distances'][0][i],  # Convert distance to similarity
                    "metadata": metadata
                })
        
        # Return top k after post-filtering
        filtered_count = len(formatted_results)
        formatted_results = formatted_results[:k]
        
        if post_filters:
            logger.info(f"✅ Post-filtered: {filtered_count} → {len(formatted_results)} results")
        
        return formatted_results
    
    def get_all_chunks(self) -> List[Dict]:
        """
        Get all chunks from database (for BM25 indexing)
        
        Returns:
            List of dicts with chunk, source, index
        """
        try:
            # Get all documents (ChromaDB limit is 100,000)
            results = self.collection.get()
            
            chunks = []
            if results['documents']:
                for i, doc in enumerate(results['documents']):
                    chunks.append({
                        'chunk': doc,
                        'source': results['metadatas'][i].get('source', ''),
                        'index': results['metadatas'][i].get('chunk_index', i)
                    })
            
            logger.info(f"📚 Retrieved {len(chunks)} chunks for indexing")
            return chunks
            
        except Exception as e:
            logger.error(f"❌ Error getting all chunks: {e}")
            return []

# Create a singleton instance
vector_manager = VectorManager()
