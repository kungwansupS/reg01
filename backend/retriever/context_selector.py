import os
import threading
import logging
import asyncio
from typing import List, Dict, Tuple, Optional
from app.config import PDF_QUICK_USE_FOLDER, debug_list_files
from app.utils.vector_manager import vector_manager
from retriever.hybrid_retriever import hybrid_retriever
from retriever.intent_analyzer import intent_analyzer
from retriever.evidence_scorer import evidence_scorer
from retriever.context_distiller import context_distiller


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ContextSelector")

_chunks_cache = []
_cache_lock = threading.Lock()

def get_file_chunks(folder=PDF_QUICK_USE_FOLDER, separator="===================", force_reload=False):
    """ดึงข้อมูล Chunks จากไฟล์ต้นทาง (.txt) พร้อมระบบ Caching"""
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
    use_advanced: bool = True,
    max_tokens: int = 2000
) -> List[Tuple[Dict, float]]:
    """
    Advanced retrieval pipeline with 3 layers:
    1. Intent Analysis
    2. Evidence Scoring
    3. Context Distillation
    
    Args:
        query: คำค้นหา
        k: จำนวนผลลัพธ์
        folder: โฟลเดอร์ต้นทาง
        use_hybrid: เปิด hybrid search
        use_advanced: เปิด advanced pipeline (intent + evidence + distill)
        max_tokens: จำนวน tokens สูงสุด
    
    Returns:
        List of (entry, score) tuples
    """
    try:
        # LAYER 0: Intent Analysis
        intent_analysis = {}
        search_params = {
            'k_multiplier': 3,
            'dense_weight': 0.5,
            'sparse_weight': 0.5,
            'keyword_boost': 0.3,
            'need_diversity': False
        }
        
        if use_advanced:
            try:
                intent_analysis = asyncio.run(intent_analyzer.analyze_intent(query))
                search_params = intent_analyzer.get_search_params(intent_analysis)
                logger.info(f"🎯 Adaptive params: k_mult={search_params['k_multiplier']}, "
                          f"dense={search_params['dense_weight']:.2f}, "
                          f"sparse={search_params['sparse_weight']:.2f}")
            except Exception as e:
                logger.warning(f"⚠️ Intent analysis failed, using defaults: {e}")
        
        # LAYER 1: Hybrid Search with adaptive params
        fetch_k = k * search_params['k_multiplier']
        
        if use_hybrid and hybrid_retriever.bm25_index is not None:
            dense_results = vector_manager.search(query, k=fetch_k)
            sparse_results = hybrid_retriever.bm25_search(query, k=fetch_k)
            
            fused_results = hybrid_retriever.rrf_fusion(
                dense_results, 
                sparse_results, 
                k=fetch_k,
                dense_weight=search_params['dense_weight'],
                sparse_weight=search_params['sparse_weight']
            )
            
            logger.info(f"🔀 Hybrid: {len(dense_results)} dense + {len(sparse_results)} sparse → {len(fused_results)}")
        else:
            logger.info("📡 Pure semantic search")
            fused_results = vector_manager.search(query, k=fetch_k)
        
        # Convert to (entry, score) format
        scored_chunks = []
        for result in fused_results:
            entry = {
                'chunk': result.get('chunk', ''),
                'source': result.get('source', ''),
                'index': result.get('metadata', {}).get('chunk_index', 0)
            }
            score = result.get('hybrid_score', result.get('score', 0))
            scored_chunks.append((entry, score))
        
        if not scored_chunks:
            logger.warning(f"⚠️ No results for: '{query}'")
            return []
        
        # LAYER 2: Evidence Scoring (if advanced mode)
        if use_advanced and intent_analysis:
            try:
                evidence_results = asyncio.run(
                    evidence_scorer.score_evidence(query, scored_chunks, intent_analysis)
                )
                
                # Log score breakdown for top result
                if evidence_results:
                    _, top_score, breakdown = evidence_results[0]
                    logger.info(f"📊 Top evidence: {breakdown}")
            except Exception as e:
                logger.warning(f"⚠️ Evidence scoring failed: {e}")
                evidence_results = [(chunk, score, {}) for chunk, score in scored_chunks]
        else:
            evidence_results = [(chunk, score, {}) for chunk, score in scored_chunks]
        
        # LAYER 3: Context Distillation (if advanced mode)
        if use_advanced and intent_analysis:
            try:
                distilled = asyncio.run(
                    context_distiller.distill(
                        evidence_results,
                        query,
                        intent_analysis,
                        max_chunks=k,
                        max_tokens=max_tokens
                    )
                )
                
                final_chunks = distilled['chunks']
                logger.info(f"🔬 Distilled: {distilled['metadata']}")
                logger.info(f"📝 Summary: {distilled['summary']}")
                
                result_chunks = [(chunk, 1.0) for chunk in final_chunks]
                
            except Exception as e:
                logger.warning(f"⚠️ Distillation failed: {e}")
                result_chunks = [(chunk, score) for chunk, score, _ in evidence_results[:k]]
        else:
            result_chunks = [(chunk, score) for chunk, score, _ in evidence_results[:k]]
        
        if result_chunks:
            logger.info(f"✅ Final: {len(result_chunks)} chunks selected")
        
        return result_chunks

    except Exception as e:
        logger.error(f"❌ Retrieval Error: {e}")
        import traceback
        traceback.print_exc()
        return []