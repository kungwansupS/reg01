import os
import threading
import logging
import asyncio
from typing import List, Dict, Tuple, Optional
from app.config import PDF_QUICK_USE_FOLDER, debug_list_files
from app.utils.vector_manager import vector_manager
from retriever.hybrid_retriever import hybrid_retriever

# ตั้งค่า Logging สำหรับการตรวจสอบการทำงาน
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ContextSelector")

# ------------------------------------------------------------------
# Global Cache & Lock
# ------------------------------------------------------------------
_chunks_cache = []
_cache_lock = threading.Lock()

def get_file_chunks(folder=PDF_QUICK_USE_FOLDER, separator="===================", force_reload=False):
    """
    ดึงข้อมูล Chunks จากไฟล์ต้นทาง (.txt) พร้อมระบบ Caching 
    ใช้สำหรับการทำ Indexing ลงฐานข้อมูล หรือตรวจสอบเนื้อหาดิบ
    """
    global _chunks_cache
    
    with _cache_lock:
        if _chunks_cache and not force_reload:
            return _chunks_cache

        debug_list_files(folder, "📄 Quick-use TXT files for Indexing")
        new_chunks = []
        
        if not os.path.exists(folder):
            logger.warning(f"⚠️ Folder not found: {folder}")
            return []

        for root, _, files in os.walk(folder):
            for filename in sorted(files):
                if filename.endswith(".txt"):
                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        parts = content.split(separator)
                        for i, chunk in enumerate(parts):
                            chunk = chunk.strip()
                            if chunk:
                                new_chunks.append({
                                    "chunk": chunk,
                                    "source": filepath,
                                    "index": i
                                })
                    except Exception as e:
                        logger.error(f"❌ Error reading {filename}: {e}")
        
        _chunks_cache = new_chunks
        return _chunks_cache

async def extract_query_filters(query: str) -> Dict:
    """
    Extract metadata filters from query using LLM
    
    Args:
        query: User query
    
    Returns:
        Dict of filters (academic_year, semester, doc_type)
    """
    try:
        from app.utils.llm.llm_model import get_llm_model
        from app.config import LLM_PROVIDER, GEMINI_MODEL_NAME, OPENAI_MODEL_NAME, LOCAL_MODEL_NAME
        
        prompt = f"""วิเคราะห์คำถามและระบุ metadata ที่ต้องการ:
คำถาม: "{query}"

ตอบเป็น JSON เท่านั้น (ไม่ต้องมี markdown):
{{
    "academic_year": "256X" หรือ null,
    "semester": 1 หรือ 2 หรือ 3 หรือ null,
    "doc_type": "calendar" หรือ "regulation" หรือ null
}}

กฎ:
- academic_year: หากพบคำว่า "ปี 2568", "2568" → "2568"
- semester: หากพบ "ภาค 1", "เทอม 1" → 1
- doc_type: หากพบ "ปฏิทิน", "calendar" → "calendar"
"""
        
        model = get_llm_model()
        
        if LLM_PROVIDER == "gemini":
            response = await model.aio.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt
            )
            result = response.text.strip()
        else:
            m_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
            response = await model.chat.completions.create(
                model=m_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            result = response.choices[0].message.content.strip()
        
        # Parse JSON
        import json
        import re
        
        # Remove markdown code blocks if present
        result = re.sub(r'```json\s*|\s*```', '', result).strip()
        
        filters = json.loads(result)
        
        # Clean None values
        cleaned = {k: v for k, v in filters.items() if v is not None}
        
        if cleaned:
            logger.info(f"🔍 Extracted filters: {cleaned}")
        
        return cleaned
        
    except Exception as e:
        logger.warning(f"⚠️ Filter extraction failed: {e}")
        return {}

def retrieve_top_k_chunks(
    query: str, 
    k: int = 5, 
    folder: str = PDF_QUICK_USE_FOLDER,
    use_hybrid: bool = True,
    use_filters: bool = True
) -> List[Tuple[Dict, float]]:
    """
    ค้นหาข้อมูลที่ใกล้เคียงที่สุด พร้อม Hybrid Search และ Smart Filtering
    
    Args:
        query: Search query
        k: Number of results
        folder: Source folder (kept for compatibility)
        use_hybrid: Enable hybrid search (dense + sparse)
        use_filters: Enable smart filtering from query
    
    Returns:
        List of (entry, score) tuples where entry has 'chunk' and 'source'
    """
    try:
        # Step 1: Extract filters from query (if enabled)
        filters = {}
        if use_filters:
            try:
                filters = asyncio.run(extract_query_filters(query))
            except RuntimeError:
                # Already in async context
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    logger.warning("⚠️ Already in async loop, skipping filter extraction")
                else:
                    filters = loop.run_until_complete(extract_query_filters(query))
            except Exception as e:
                logger.warning(f"⚠️ Filter extraction error: {e}")
        
        # Step 2: Hybrid Search
        if use_hybrid and hybrid_retriever.bm25_index is not None:
            # Dense search with filters
            dense_results = vector_manager.search(query, k=k*2, filter_dict=filters)
            
            # Sparse search (BM25 doesn't support filters, so we filter after)
            sparse_results = hybrid_retriever.bm25_search(query, k=k*2)
            
            # Apply filters to sparse results if needed
            if filters:
                filtered_sparse = []
                for doc, score in sparse_results:
                    # Simple filtering based on source filepath
                    include = True
                    
                    if 'doc_type' in filters:
                        if filters['doc_type'] not in doc.get('source', '').lower():
                            include = False
                    
                    if 'academic_year' in filters:
                        # Read chunk content to check
                        if filters['academic_year'] not in doc.get('chunk', ''):
                            include = False
                    
                    if include:
                        filtered_sparse.append((doc, score))
                
                sparse_results = filtered_sparse
            
            # RRF Fusion
            fused_results = hybrid_retriever.rrf_fusion(dense_results, sparse_results, k=k)
            
            logger.info(f"🔀 Hybrid retrieval: {len(dense_results)} dense + {len(sparse_results)} sparse → {len(fused_results)} fused")
            
        else:
            # Fallback to pure semantic search
            logger.info("📡 Using pure semantic search")
            fused_results = vector_manager.search(query, k=k, filter_dict=filters)
        
        # Step 3: Convert to old format (entry, score) tuples
        scored_chunks = []
        for result in fused_results:
            entry = {
                'chunk': result.get('chunk', ''),
                'source': result.get('source', ''),
                'index': result.get('metadata', {}).get('chunk_index', 0)
            }
            score = result.get('rrf_score', result.get('score', 0))
            scored_chunks.append((entry, score))
        
        if not scored_chunks:
            logger.warning(f"⚠️ No results found for query: '{query}'")
        else:
            logger.info(f"✅ Retrieved {len(scored_chunks)} chunks")
        
        return scored_chunks

    except Exception as e:
        logger.error(f"❌ Retrieval Error: {e}")
        import traceback
        traceback.print_exc()
        # Return empty list on error (no-error policy)
        return []