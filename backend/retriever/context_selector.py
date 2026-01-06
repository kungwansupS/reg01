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

async def extract_query_intent(query: str) -> Dict:
    """
    🆕 Analyze query intent และ expected answer type
    
    Args:
        query: User query
    
    Returns:
        Dict with intent, filters, and expected_answer_type
    """
    try:
        from app.utils.llm.llm_model import get_llm_model
        from app.config import LLM_PROVIDER, GEMINI_MODEL_NAME, OPENAI_MODEL_NAME, LOCAL_MODEL_NAME
        
        prompt = f"""วิเคราะห์คำถามนี้ให้ละเอียด:

คำถาม: "{query}"

ตอบเป็น JSON เท่านั้น (ไม่ต้องมี markdown):
{{
    "intent": "factual_query" หรือ "date_query" หรือ "policy_query" หรือ "general",
    "expected_answer_type": "date" หรือ "number" หรือ "text" หรือ "list",
    "key_entities": ["entity1", "entity2"],
    "academic_year": "256X" หรือ null,
    "semester": 1 หรือ 2 หรือ 3 หรือ null,
    "doc_type": "calendar" หรือ "regulation" หรือ null
}}

กฎ:
- intent: ประเภทคำถาม (ถามวันที่ใช้ date_query, ถามนโยบายใช้ policy_query)
- expected_answer_type: รูปแบบคำตอบที่คาดหวัง
- key_entities: สิ่งสำคัญที่ถามถึง (เช่น "เปิดเรียน", "สอบกลางภาค")
- academic_year: หากพบ "2568", "ปี 2568" → "2568"
- semester: หากพบ "ภาค 1", "เทอม 1", "เทอมนี้" (ใช้ภาคปัจจุบัน) → 1
- doc_type: "ปฏิทิน" → "calendar", "ระเบียบ" → "regulation"
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
        result = re.sub(r'```json\s*|\s*```', '', result).strip()
        intent_data = json.loads(result)
        
        logger.info(f"🎯 Intent: {intent_data.get('intent')}, Type: {intent_data.get('expected_answer_type')}")
        if intent_data.get('key_entities'):
            logger.info(f"🔑 Key entities: {intent_data['key_entities']}")
        
        return intent_data
        
    except Exception as e:
        logger.warning(f"⚠️ Intent extraction failed: {e}")
        return {"intent": "general", "expected_answer_type": "text"}

async def llm_rerank_chunks(
    query: str,
    chunks: List[Tuple[Dict, float]],
    intent_data: Dict,
    top_k: int = 5
) -> List[Tuple[Dict, float]]:
    """
    🆕 ให้ LLM ช่วยตัดสินว่า chunk ไหนตอบคำถามได้จริง
    
    Args:
        query: Original query
        chunks: List of (chunk_dict, score) tuples
        intent_data: Intent information from extract_query_intent
        top_k: Number of results to return
    
    Returns:
        Reranked chunks with new scores
    """
    if not chunks:
        return []
    
    try:
        from app.utils.llm.llm_model import get_llm_model
        from app.config import LLM_PROVIDER, GEMINI_MODEL_NAME, OPENAI_MODEL_NAME, LOCAL_MODEL_NAME
        
        # จำกัดจำนวน chunks ที่ส่งให้ LLM
        candidates = chunks[:min(15, len(chunks))]
        
        # สร้าง prompt สำหรับ reranking
        chunks_text = ""
        for idx, (chunk_dict, score) in enumerate(candidates):
            chunks_text += f"\n[{idx}] {chunk_dict['chunk'][:300]}...\n"
        
        expected_type = intent_data.get('expected_answer_type', 'text')
        key_entities = intent_data.get('key_entities', [])
        
        prompt = f"""ให้คะแนนความเกี่ยวข้องของแต่ละ chunk กับคำถาม:

คำถาม: "{query}"
ประเภทคำตอบที่ต้องการ: {expected_type}
สิ่งที่ต้องการหา: {', '.join(key_entities) if key_entities else 'ข้อมูลทั่วไป'}

Chunks:
{chunks_text}

ให้คะแนนแต่ละ chunk (0-100) ว่าตอบคำถามได้ดีแค่ไหน
ตอบเป็น JSON array เท่านั้น:
[
    {{"index": 0, "score": 85, "reason": "มีข้อมูลวันที่ชัดเจน"}},
    {{"index": 1, "score": 20, "reason": "ไม่ตรงคำถาม"}}
]

กฎ:
- คะแนน 80-100: ตอบคำถามได้ตรง
- คะแนน 50-79: เกี่ยวข้อง แต่ไม่ตรง
- คะแนน 0-49: ไม่เกี่ยวข้อง
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
        result = re.sub(r'```json\s*|\s*```', '', result).strip()
        scores = json.loads(result)
        
        # สร้าง reranked results
        reranked = []
        for item in scores:
            idx = item['index']
            new_score = item['score'] / 100.0  # Normalize to 0-1
            if 0 <= idx < len(candidates):
                chunk_dict = candidates[idx][0]
                reranked.append((chunk_dict, new_score))
                logger.debug(f"Chunk {idx}: {new_score:.2f} - {item.get('reason', '')}")
        
        # Sort by new score
        reranked.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"🎯 LLM Reranked: {len(reranked)} chunks, top score: {reranked[0][1]:.2f}")
        
        return reranked[:top_k]
        
    except Exception as e:
        logger.warning(f"⚠️ LLM reranking failed: {e}, using original ranking")
        return chunks[:top_k]

def _run_async_safely(coro):
    """
    🆕 Helper to run async functions safely in any context
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context - use nest_asyncio
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        else:
            return asyncio.run(coro)
    except RuntimeError:
        # No event loop - create new one
        return asyncio.run(coro)
    except ImportError:
        # nest_asyncio not available - run in thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()

def retrieve_top_k_chunks(
    query: str, 
    k: int = 5, 
    folder: str = PDF_QUICK_USE_FOLDER,
    use_hybrid: bool = True,
    use_llm_rerank: bool = True,
    use_intent_analysis: bool = True
) -> List[Tuple[Dict, float]]:
    """
    🔥 ค้นหาข้อมูลที่ใกล้เคียงที่สุด พร้อม:
    - Hybrid Search (dense + sparse)
    - Intent Analysis
    - LLM Reranking
    
    Args:
        query: Search query
        k: Number of results
        folder: Source folder (kept for compatibility)
        use_hybrid: Enable hybrid search (dense + sparse)
        use_llm_rerank: Enable LLM reranking (แนะนำ)
        use_intent_analysis: Enable intent detection
    
    Returns:
        List of (entry, score) tuples where entry has 'chunk' and 'source'
    """
    try:
        # Step 1: Intent Analysis
        intent_data = {}
        if use_intent_analysis:
            try:
                intent_data = _run_async_safely(extract_query_intent(query))
            except Exception as e:
                logger.warning(f"⚠️ Intent analysis error: {e}")
        
        # Extract filters from intent
        filters = {}
        for key in ['academic_year', 'semester', 'doc_type']:
            if key in intent_data and intent_data[key] is not None:
                filters[key] = intent_data[key]
        
        if filters:
            logger.info(f"🔍 Filters: {filters}")
        
        # Step 2: Hybrid Search
        if use_hybrid and hybrid_retriever.bm25_index is not None:
            # Dense search with filters
            dense_results = vector_manager.search(query, k=k*3, filter_dict=filters)
            
            # Sparse search (BM25) - ลดน้ำหนักลง
            sparse_results = hybrid_retriever.bm25_search(query, k=k*2)
            
            # Apply filters to sparse results
            if filters:
                filtered_sparse = []
                for doc, score in sparse_results:
                    include = True
                    
                    # Filter by doc_type
                    if 'doc_type' in filters:
                        if filters['doc_type'] not in doc.get('source', '').lower():
                            include = False
                    
                    # Filter by academic_year (check in chunk content)
                    if 'academic_year' in filters:
                        if filters['academic_year'] not in doc.get('chunk', ''):
                            include = False
                    
                    if include:
                        filtered_sparse.append((doc, score))
                
                sparse_results = filtered_sparse
            
            # RRF Fusion with lower weight for BM25
            fused_results = hybrid_retriever.rrf_fusion(
                dense_results, 
                sparse_results, 
                k=k*2,  # Get more candidates for reranking
                dense_weight=0.7,  # 🆕 ให้น้ำหนัก dense มากกว่า
                sparse_weight=0.3   # 🆕 ลดน้ำหนัก BM25
            )
            
            logger.info(f"🔀 Hybrid: {len(dense_results)} dense + {len(sparse_results)} sparse → {len(fused_results)} fused")
            
        else:
            # Fallback to pure semantic search
            logger.info("📡 Using pure semantic search")
            fused_results = vector_manager.search(query, k=k*2, filter_dict=filters)
        
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
        
        # Step 4: LLM Reranking (ขั้นตอนสำคัญ!)
        if use_llm_rerank and scored_chunks:
            try:
                scored_chunks = _run_async_safely(
                    llm_rerank_chunks(query, scored_chunks, intent_data, top_k=k)
                )
            except Exception as e:
                logger.warning(f"⚠️ LLM reranking error: {e}")
                scored_chunks = scored_chunks[:k]
        else:
            scored_chunks = scored_chunks[:k]
        
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