import os
import threading
import logging
from typing import List, Dict, Tuple, Optional
from app.config import PDF_QUICK_USE_FOLDER, debug_list_files
from app.utils.vector_manager import vector_manager
from retriever.hybrid_retriever import hybrid_retriever
from retriever.intent_analyzer import analyze_intent
from retriever.reranker import rerank_chunks

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


def retrieve_top_k_chunks(
    query: str, 
    k: int = 5, 
    folder: str = PDF_QUICK_USE_FOLDER,
    use_hybrid: bool = True,
    use_rerank: bool = True,
    use_intent_analysis: bool = True,
    # Legacy parameters (kept for backward compatibility)
    use_llm_rerank: bool = True,
) -> List[Tuple[Dict, float]]:
    """
    ค้นหาข้อมูลที่ใกล้เคียงที่สุด — ไม่มี LLM call ใดๆ

    Pipeline (ทั้งหมดทำงาน local):
    1. Rule-based Intent Analysis → filters
    2. Hybrid Search (Dense + BM25 + RRF)
    3. Cross-Encoder Reranking (local model)
    
    Args:
        query: Search query
        k: Number of results
        folder: Source folder (kept for compatibility)
        use_hybrid: Enable hybrid search (dense + sparse)
        use_rerank: Enable cross-encoder reranking
        use_intent_analysis: Enable rule-based intent detection
    
    Returns:
        List of (entry, score) tuples where entry has 'chunk' and 'source'
    """
    try:
        # Step 1: Rule-based Intent Analysis (instant, no API call)
        intent_data = {}
        if use_intent_analysis:
            try:
                intent_data = analyze_intent(query)
            except Exception as e:
                logger.warning(f"⚠️ Intent analysis error: {e}")
        
        # Extract filters from intent
        # Only use doc_type as a hard filter (pre-filter in ChromaDB)
        # academic_year/semester are NOT used as filters because:
        # 1. Chunk metadata may not have these fields set correctly
        # 2. Semantic search + BM25 naturally rank by relevance
        # 3. Aggressive filtering causes 0-result searches
        filters = {}
        if intent_data.get("doc_type") and intent_data["doc_type"] != "payment":
            filters["doc_type"] = intent_data["doc_type"]
        
        if filters:
            logger.info(f"🔍 Filters: {filters}")
        
        # Step 2: Hybrid Search
        if use_hybrid and hybrid_retriever.bm25_index is not None:
            # Dense search with filters
            dense_results = vector_manager.search(query, k=k*3, filter_dict=filters)
            
            # Sparse search (BM25)
            sparse_results = hybrid_retriever.bm25_search(query, k=k*2)
            
            # Apply doc_type filter to sparse results (soft filter)
            if filters.get('doc_type'):
                filtered_sparse = []
                for doc, score in sparse_results:
                    if filters['doc_type'] not in doc.get('source', '').lower():
                        continue
                    filtered_sparse.append((doc, score))
                # Only use filtered if it has results; else keep all
                if filtered_sparse:
                    sparse_results = filtered_sparse
            
            # RRF Fusion
            fused_results = hybrid_retriever.rrf_fusion(
                dense_results, 
                sparse_results, 
                k=k*2,
                dense_weight=0.7,
                sparse_weight=0.3,
            )
            
            # Fallback: if filtered search returns 0, retry WITHOUT filters
            if not fused_results and filters:
                logger.info("🔄 Filtered search returned 0, retrying without filters...")
                dense_results = vector_manager.search(query, k=k*3, filter_dict=None)
                sparse_results = hybrid_retriever.bm25_search(query, k=k*2)
                fused_results = hybrid_retriever.rrf_fusion(
                    dense_results, sparse_results, k=k*2,
                    dense_weight=0.7, sparse_weight=0.3,
                )
            
            logger.info(f"🔀 Hybrid: {len(dense_results)} dense + {len(sparse_results)} sparse → {len(fused_results)} fused")
            
        else:
            # Fallback to pure semantic search
            logger.info("📡 Using pure semantic search")
            fused_results = vector_manager.search(query, k=k*2, filter_dict=filters)
            
            # Fallback: if filtered search returns 0, retry WITHOUT filters
            if not fused_results and filters:
                logger.info("🔄 Filtered search returned 0, retrying without filters...")
                fused_results = vector_manager.search(query, k=k*2, filter_dict=None)
        
        # Step 3: Convert to (entry, score) tuples
        scored_chunks = []
        for result in fused_results:
            entry = {
                'chunk': result.get('chunk', ''),
                'source': result.get('source', ''),
                'index': result.get('metadata', {}).get('chunk_index', 0)
            }
            score = result.get('rrf_score', result.get('score', 0))
            scored_chunks.append((entry, score))
        
        # Step 4: Cross-Encoder Reranking (local model, no API call)
        if use_rerank and scored_chunks:
            try:
                scored_chunks = rerank_chunks(query, scored_chunks, top_k=k)
            except Exception as e:
                logger.warning(f"⚠️ Cross-encoder reranking error: {e}")
                scored_chunks = scored_chunks[:k]
        else:
            scored_chunks = scored_chunks[:k]
        
        # Step 5: Keyword guarantee — ensure chunks with exact entity
        # matches from intent analysis are always included in results.
        # This prevents cross-encoder from dropping keyword-relevant chunks.
        entities = intent_data.get("key_entities", [])
        if entities and scored_chunks:
            # Check if entities are already in scored_chunks
            scored_text = " ".join(c[0].get('chunk', '') for c in scored_chunks)
            entities_missing = [e for e in entities if e not in scored_text]
            if entities_missing:
                logger.info(f"🔑 Entities missing from top-{k}: {entities_missing}, checking fused ({len(fused_results)} results)...")
                for result in fused_results:
                    chunk_text = result.get('chunk', '')
                    for entity in entities_missing:
                        if entity in chunk_text:
                            entry = {
                                'chunk': chunk_text,
                                'source': result.get('source', ''),
                                'index': result.get('metadata', {}).get('chunk_index', 0),
                            }
                            boost_score = scored_chunks[0][1] * 0.9 if scored_chunks else 1.0
                            scored_chunks.insert(1, (entry, boost_score))
                            scored_chunks = scored_chunks[:k + 1]
                            entities_missing.remove(entity)
                            logger.info(f"🔑 Keyword boost: inserted chunk containing '{entity}' (len={len(chunk_text)})")
                            break
                    if not entities_missing:
                        break
                if entities_missing:
                    logger.warning(f"⚠️ Entities still missing after boost: {entities_missing}")
        
        if not scored_chunks:
            logger.warning(f"⚠️ No results found for query: '{query}'")
        else:
            logger.info(f"✅ Final results: {len(scored_chunks)} chunks (top score: {scored_chunks[0][1]:.2f})")
        
        return scored_chunks

    except Exception as e:
        logger.error(f"❌ Retrieval Error: {e}")
        import traceback
        traceback.print_exc()
        return []