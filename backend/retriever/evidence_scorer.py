import logging
import asyncio
from typing import List, Dict, Tuple
import re
from retriever.intent_analyzer import QueryIntent

logger = logging.getLogger("EvidenceScorer")

class EvidenceScorer:
    """
    ให้คะแนนความน่าเชื่อถือของ context chunks
    พิจารณาจาก: relevance, specificity, recency, source quality
    """
    
    @staticmethod
    async def score_evidence(
        query: str,
        chunks: List[Tuple[Dict, float]],
        intent_analysis: Dict
    ) -> List[Tuple[Dict, float, Dict]]:
        """
        ให้คะแนนหลักฐานแต่ละชิ้น
        
        Args:
            query: คำถามต้นฉบับ
            chunks: List of (chunk_dict, retrieval_score)
            intent_analysis: ผลจาก IntentAnalyzer
        
        Returns:
            List of (chunk_dict, final_score, score_breakdown)
        """
        if not chunks:
            return []
        
        keywords = intent_analysis.get('keywords', [])
        temporal_refs = intent_analysis.get('temporal_refs', [])
        entities = intent_analysis.get('entities', [])
        
        scored_chunks = []
        
        for chunk_dict, retrieval_score in chunks:
            chunk_text = chunk_dict.get('chunk', '')
            source = chunk_dict.get('source', '')
            
            # 1. Relevance Score (จาก retrieval + keyword match)
            relevance = retrieval_score
            
            # 2. Specificity Score (มีข้อมูลเฉพาะเจาะจงแค่ไหน)
            specificity = EvidenceScorer._calculate_specificity(
                chunk_text, 
                keywords, 
                temporal_refs, 
                entities
            )
            
            # 3. Completeness Score (ความสมบูรณ์ของข้อมูล)
            completeness = EvidenceScorer._calculate_completeness(
                chunk_text,
                intent_analysis
            )
            
            # 4. Source Quality Score
            source_quality = EvidenceScorer._calculate_source_quality(source)
            
            # 5. Recency Score (ปีการศึกษาล่าสุด)
            recency = EvidenceScorer._calculate_recency(chunk_text)
            
            # Combined score with weights
            weights = {
                'relevance': 0.35,
                'specificity': 0.25,
                'completeness': 0.20,
                'source_quality': 0.10,
                'recency': 0.10
            }
            
            final_score = (
                relevance * weights['relevance'] +
                specificity * weights['specificity'] +
                completeness * weights['completeness'] +
                source_quality * weights['source_quality'] +
                recency * weights['recency']
            )
            
            score_breakdown = {
                'relevance': round(relevance, 3),
                'specificity': round(specificity, 3),
                'completeness': round(completeness, 3),
                'source_quality': round(source_quality, 3),
                'recency': round(recency, 3),
                'final': round(final_score, 3)
            }
            
            scored_chunks.append((chunk_dict, final_score, score_breakdown))
        
        # Sort by final score
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"📊 Evidence scored: top score = {scored_chunks[0][1]:.3f}")
        
        return scored_chunks
    
    @staticmethod
    def _calculate_specificity(
        text: str,
        keywords: List[str],
        temporal_refs: List[str],
        entities: List[str]
    ) -> float:
        """
        คะแนนความเฉพาะเจาะจง
        - มีวันที่/เวลาที่ชัดเจน
        - มีชื่อเฉพาะ/หน่วยงาน
        - มีตัวเลขที่เกี่ยวข้อง
        """
        text_lower = text.lower()
        score = 0.0
        
        # Check temporal refs (0.3)
        temporal_count = sum(1 for t in temporal_refs if t.lower() in text_lower)
        score += min(temporal_count / max(len(temporal_refs), 1), 1.0) * 0.3
        
        # Check entities (0.3)
        entity_count = sum(1 for e in entities if e.lower() in text_lower)
        score += min(entity_count / max(len(entities), 1), 1.0) * 0.3
        
        # Check for specific patterns (0.4)
        has_date = bool(re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text))
        has_time = bool(re.search(r'\d{1,2}:\d{2}', text))
        has_numbers = bool(re.search(r'\d+', text))
        
        pattern_score = (has_date * 0.2 + has_time * 0.1 + has_numbers * 0.1)
        score += pattern_score
        
        return min(score, 1.0)
    
    @staticmethod
    def _calculate_completeness(text: str, intent_analysis: Dict) -> float:
        """
        คะแนนความสมบูรณ์ตาม intent
        - Factual: มีคำตอบที่ชัดเจน
        - Procedural: มีขั้นตอนครบ
        - Comparative: มีทั้ง 2 ฝ่าย
        """
        from intent_analyzer import QueryIntent
        
        intent = intent_analysis.get('intent')
        text_lower = text.lower()
        
        if intent == QueryIntent.FACTUAL:
            # มีคำตอบเฉพาะเจาะจง
            answer_indicators = ['คือ', 'ได้แก่', 'เท่ากับ', 'จำนวน']
            score = sum(0.25 for w in answer_indicators if w in text_lower)
            return min(score, 1.0)
        
        elif intent == QueryIntent.PROCEDURAL:
            # มีลำดับขั้นตอน
            step_indicators = ['ขั้นตอน', 'ขั้น', 'ที่ 1', 'ที่ 2', 'ก่อน', 'หลัง', 'จากนั้น']
            score = sum(0.15 for w in step_indicators if w in text_lower)
            return min(score, 1.0)
        
        elif intent == QueryIntent.COMPARATIVE:
            # มีการเปรียบเทียบ
            compare_indicators = ['แต่', 'ขณะที่', 'ในขณะ', 'ส่วน', 'กรณี']
            score = sum(0.25 for w in compare_indicators if w in text_lower)
            return min(score, 1.0)
        
        else:
            # Default: ความยาวเหมาะสม
            length_score = min(len(text) / 500, 1.0)
            return length_score * 0.5 + 0.5
    
    @staticmethod
    def _calculate_source_quality(source: str) -> float:
        """
        คะแนนคุณภาพแหล่งที่มา
        - เอกสารทางการ > ข้อมูลทั่วไป
        """
        source_lower = source.lower()
        
        # Official documents
        if any(w in source_lower for w in ['regulation', 'announcement', 'policy', 'ระเบียบ', 'ข้อบังคับ']):
            return 1.0
        
        # Calendar/Schedule
        if any(w in source_lower for w in ['calendar', 'schedule', 'ปฏิทิน']):
            return 0.9
        
        # Guidelines
        if any(w in source_lower for w in ['guide', 'manual', 'คู่มือ', 'แนวทาง']):
            return 0.8
        
        # General info
        return 0.6
    
    @staticmethod
    def _calculate_recency(text: str) -> float:
        """
        คะแนนความใหม่ของข้อมูล (จากปีการศึกษา)
        ปี 2568 = 1.0, ปี 2567 = 0.8, เก่ากว่า = 0.5
        """
        # Find academic year
        years = re.findall(r'25[0-9]{2}', text)
        
        if not years:
            return 0.5  # ไม่มีปี = ข้อมูลทั่วไป
        
        latest_year = max(int(y) for y in years)
        
        if latest_year >= 2568:
            return 1.0
        elif latest_year >= 2567:
            return 0.8
        elif latest_year >= 2566:
            return 0.6
        else:
            return 0.4
    
    @staticmethod
    async def explain_scores(
        top_chunks: List[Tuple[Dict, float, Dict]],
        n: int = 3
    ) -> str:
        """
        สร้างคำอธิบายสำหรับ top N chunks
        เพื่อ debug และเข้าใจการให้คะแนน
        """
        if not top_chunks:
            return "ไม่พบหลักฐาน"
        
        explanations = []
        
        for i, (chunk_dict, final_score, breakdown) in enumerate(top_chunks[:n], 1):
            chunk_preview = chunk_dict.get('chunk', '')[:100]
            source = chunk_dict.get('source', '').split('/')[-1]
            
            exp = f"""
Chunk #{i} (Score: {final_score:.3f})
Source: {source}
Preview: {chunk_preview}...
Breakdown:
  - Relevance: {breakdown['relevance']:.3f}
  - Specificity: {breakdown['specificity']:.3f}
  - Completeness: {breakdown['completeness']:.3f}
  - Source Quality: {breakdown['source_quality']:.3f}
  - Recency: {breakdown['recency']:.3f}
"""
            explanations.append(exp)
        
        return "\n".join(explanations)

# Global singleton
evidence_scorer = EvidenceScorer()
