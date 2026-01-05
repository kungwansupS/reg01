import logging
import asyncio
from typing import List, Dict, Tuple
from collections import defaultdict
from retriever.intent_analyzer import QueryIntent

logger = logging.getLogger("ContextDistiller")

class ContextDistiller:
    """
    กลั่นกรอง context เพื่อ:
    1. ลดความซ้ำซ้อน (deduplication)
    2. จัดลำดับความสำคัญ (prioritization)
    3. สรุปข้อมูลให้กระชับ (compression)
    4. รักษาความหลากหลาย (diversity)
    """
    
    @staticmethod
    async def distill(
        scored_chunks: List[Tuple[Dict, float, Dict]],
        query: str,
        intent_analysis: Dict,
        max_chunks: int = 5,
        max_tokens: int = 2000
    ) -> Dict:
        """
        กลั่นกรอง context
        
        Args:
            scored_chunks: chunks ที่ผ่าน evidence scoring แล้ว
            query: คำถามต้นฉบับ
            intent_analysis: ผลจาก IntentAnalyzer
            max_chunks: จำนวน chunks สูงสุด
            max_tokens: จำนวน tokens สูงสุด (ประมาณ)
        
        Returns:
            {
                "chunks": List[Dict],
                "summary": str,
                "metadata": Dict
            }
        """
        if not scored_chunks:
            return {
                "chunks": [],
                "summary": "",
                "metadata": {"total_chunks": 0, "removed_duplicates": 0}
            }
        
        # Step 1: Remove duplicates
        unique_chunks = ContextDistiller._remove_duplicates(scored_chunks)
        removed_count = len(scored_chunks) - len(unique_chunks)
        
        # Step 2: Ensure diversity
        diverse_chunks = ContextDistiller._ensure_diversity(
            unique_chunks,
            max_chunks * 2,  # เอามากกว่าเพื่อจะได้เลือกได้
            intent_analysis
        )
        
        # Step 3: Prioritize and select
        selected_chunks = ContextDistiller._prioritize_chunks(
            diverse_chunks,
            query,
            intent_analysis,
            max_chunks,
            max_tokens
        )
        
        # Step 4: Generate summary
        summary = await ContextDistiller._generate_summary(
            selected_chunks,
            query,
            intent_analysis
        )
        
        metadata = {
            "total_chunks": len(scored_chunks),
            "removed_duplicates": removed_count,
            "final_chunks": len(selected_chunks),
            "estimated_tokens": ContextDistiller._estimate_tokens(selected_chunks)
        }
        
        logger.info(f"🔬 Distilled: {metadata['total_chunks']} → {metadata['final_chunks']} chunks")
        
        return {
            "chunks": [chunk for chunk, _, _ in selected_chunks],
            "summary": summary,
            "metadata": metadata
        }
    
    @staticmethod
    def _remove_duplicates(
        scored_chunks: List[Tuple[Dict, float, Dict]],
        similarity_threshold: float = 0.85
    ) -> List[Tuple[Dict, float, Dict]]:
        """
        ลบ chunks ที่ซ้ำกัน (โดยดูจาก text similarity)
        """
        if not scored_chunks:
            return []
        
        unique = []
        seen_texts = []
        
        for chunk_dict, score, breakdown in scored_chunks:
            chunk_text = chunk_dict.get('chunk', '').lower()
            
            # Check if similar to any seen text
            is_duplicate = False
            for seen_text in seen_texts:
                similarity = ContextDistiller._text_similarity(chunk_text, seen_text)
                if similarity > similarity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique.append((chunk_dict, score, breakdown))
                seen_texts.append(chunk_text)
        
        return unique
    
    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        """Simple Jaccard similarity"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    @staticmethod
    def _ensure_diversity(
        chunks: List[Tuple[Dict, float, Dict]],
        max_chunks: int,
        intent_analysis: Dict
    ) -> List[Tuple[Dict, float, Dict]]:
        """
        รักษาความหลากหลายของ sources และ perspectives
        """
        from intent_analyzer import QueryIntent
        
        intent = intent_analysis.get('intent')
        
        # For comparative/analytical, need diversity
        if intent in [QueryIntent.COMPARATIVE, QueryIntent.ANALYTICAL]:
            return ContextDistiller._maximal_marginal_relevance(chunks, max_chunks)
        
        # For factual/procedural, just take top scored
        return chunks[:max_chunks]
    
    @staticmethod
    def _maximal_marginal_relevance(
        chunks: List[Tuple[Dict, float, Dict]],
        k: int,
        lambda_param: float = 0.7
    ) -> List[Tuple[Dict, float, Dict]]:
        """
        MMR algorithm สำหรับ diversity
        lambda_param: balance between relevance (1.0) and diversity (0.0)
        """
        if not chunks:
            return []
        
        selected = []
        remaining = list(chunks)
        
        # Start with highest scored
        selected.append(remaining.pop(0))
        
        while remaining and len(selected) < k:
            best_idx = -1
            best_score = -float('inf')
            
            for i, (chunk_dict, score, breakdown) in enumerate(remaining):
                # Relevance score
                relevance = score
                
                # Diversity penalty (similarity to selected)
                max_similarity = 0
                chunk_text = chunk_dict.get('chunk', '').lower()
                
                for sel_chunk_dict, _, _ in selected:
                    sel_text = sel_chunk_dict.get('chunk', '').lower()
                    sim = ContextDistiller._text_similarity(chunk_text, sel_text)
                    max_similarity = max(max_similarity, sim)
                
                # MMR score
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i
            
            if best_idx >= 0:
                selected.append(remaining.pop(best_idx))
            else:
                break
        
        return selected
    
    @staticmethod
    def _prioritize_chunks(
        chunks: List[Tuple[Dict, float, Dict]],
        query: str,
        intent_analysis: Dict,
        max_chunks: int,
        max_tokens: int
    ) -> List[Tuple[Dict, float, Dict]]:
        """
        เลือก chunks สำคัญที่สุดโดยคำนึงถึง token limit
        """
        selected = []
        total_tokens = 0
        
        for chunk_dict, score, breakdown in chunks:
            chunk_text = chunk_dict.get('chunk', '')
            estimated_tokens = len(chunk_text.split()) * 1.3  # rough estimate
            
            if total_tokens + estimated_tokens > max_tokens:
                # Try to compress this chunk
                compressed = ContextDistiller._compress_chunk(chunk_text, query)
                estimated_tokens = len(compressed.split()) * 1.3
                
                if total_tokens + estimated_tokens > max_tokens:
                    break  # Skip this chunk
                else:
                    # Use compressed version
                    chunk_dict_copy = chunk_dict.copy()
                    chunk_dict_copy['chunk'] = compressed
                    selected.append((chunk_dict_copy, score, breakdown))
                    total_tokens += estimated_tokens
            else:
                selected.append((chunk_dict, score, breakdown))
                total_tokens += estimated_tokens
            
            if len(selected) >= max_chunks:
                break
        
        return selected
    
    @staticmethod
    def _compress_chunk(text: str, query: str) -> str:
        """
        บีบอัดข้อความให้กระชับโดยเก็บส่วนที่เกี่ยวข้องกับ query
        """
        # Split into sentences
        sentences = text.split('.')
        
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # Score each sentence by relevance
        scored_sentences = []
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            
            sent_lower = sent.lower()
            sent_words = set(sent_lower.split())
            
            # Jaccard similarity with query
            overlap = len(query_words & sent_words)
            score = overlap / len(query_words) if query_words else 0
            
            scored_sentences.append((sent, score))
        
        # Keep top 50% most relevant sentences
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        keep_count = max(1, len(scored_sentences) // 2)
        
        kept_sentences = [s for s, _ in scored_sentences[:keep_count]]
        
        return '. '.join(kept_sentences) + '.'
    
    @staticmethod
    def _estimate_tokens(chunks: List[Tuple[Dict, float, Dict]]) -> int:
        """Estimate total tokens"""
        total_words = sum(
            len(chunk_dict.get('chunk', '').split())
            for chunk_dict, _, _ in chunks
        )
        return int(total_words * 1.3)  # Thai has ~1.3 tokens per word
    
    @staticmethod
    async def _generate_summary(
        chunks: List[Tuple[Dict, float, Dict]],
        query: str,
        intent_analysis: Dict
    ) -> str:
        """
        สร้าง summary สั้นๆ ของ context ที่เลือก
        """
        if not chunks:
            return "ไม่พบข้อมูลที่เกี่ยวข้อง"
        
        # Count sources and key info
        sources = set()
        has_dates = False
        has_steps = False
        
        for chunk_dict, _, _ in chunks:
            source = chunk_dict.get('source', '').split('/')[-1]
            sources.add(source)
            
            chunk_text = chunk_dict.get('chunk', '').lower()
            if any(w in chunk_text for w in ['วันที่', 'เวลา', '256']):
                has_dates = True
            if any(w in chunk_text for w in ['ขั้นตอน', 'วิธี', 'ก่อน', 'หลัง']):
                has_steps = True
        
        summary_parts = []
        summary_parts.append(f"พบข้อมูลจาก {len(sources)} แหล่ง")
        
        if has_dates:
            summary_parts.append("มีข้อมูลวันเวลา")
        if has_steps:
            summary_parts.append("มีขั้นตอน/วิธีการ")
        
        return " | ".join(summary_parts)

# Global singleton
context_distiller = ContextDistiller()
