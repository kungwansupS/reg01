import logging
import asyncio
from typing import Dict, List
from enum import Enum

logger = logging.getLogger("IntentAnalyzer")

class QueryIntent(Enum):
    """ประเภทของความต้องการในคำถาม"""
    FACTUAL = "factual"
    PROCEDURAL = "procedural"
    COMPARATIVE = "comparative"
    ANALYTICAL = "analytical"
    CONVERSATIONAL = "conversational"

class IntentAnalyzer:
    """วิเคราะห์ความต้องการจากคำถาม เพื่อปรับกลยุทธ์การค้นหา"""
    
    @staticmethod
    async def analyze_intent(query: str) -> Dict:
        """
        วิเคราะห์ intent และสกัดข้อมูลสำคัญ
        
        Returns:
            {
                "intent": QueryIntent,
                "keywords": List[str],
                "temporal_refs": List[str],
                "entities": List[str],
                "confidence": float
            }
        """
        try:
            from app.utils.llm.llm_model import get_llm_model
            from app.config import LLM_PROVIDER, GEMINI_MODEL_NAME, OPENAI_MODEL_NAME, LOCAL_MODEL_NAME
            
            prompt = f"""วิเคราะห์คำถามนี้อย่างละเอียด:
"{query}"

ตอบเป็น JSON เท่านั้น (ไม่ต้องมีคำอธิบายเพิ่มเติม):
{{
    "intent": "factual",
    "keywords": ["คำสำคัญ1", "คำสำคัญ2"],
    "temporal_refs": ["2568", "ภาค 1"],
    "entities": ["ชื่อหน่วยงาน"],
    "confidence": 0.9
}}

คำอธิบาย intent:
- factual: ถามข้อเท็จจริงเฉพาะเจาะจง
- procedural: ถามวิธีการ/ขั้นตอน
- comparative: เปรียบเทียบ
- analytical: ขอวิเคราะห์/สรุป
- conversational: สนทนาทั่วไป"""
            
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
            
            import json
            import re
            
            # Clean response
            result = re.sub(r'```json\s*|\s*```', '', result).strip()
            
            # Try to extract JSON object (handle extra text after JSON)
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result, re.DOTALL)
            if json_match:
                result = json_match.group(0)
            
            # Parse JSON with fallback
            try:
                # Try to decode just the first complete JSON object
                decoder = json.JSONDecoder()
                analysis, _ = decoder.raw_decode(result)
            except json.JSONDecodeError:
                # Fallback: standard parse
                analysis = json.loads(result)
            
            # Convert intent string to enum
            try:
                intent_str = analysis.get('intent', 'factual')
                analysis['intent'] = QueryIntent(intent_str)
            except (KeyError, ValueError):
                analysis['intent'] = QueryIntent.FACTUAL
            
            # Ensure all required fields exist
            analysis.setdefault('keywords', [])
            analysis.setdefault('temporal_refs', [])
            analysis.setdefault('entities', [])
            analysis.setdefault('confidence', 0.5)
            
            logger.info(f"🎯 Intent: {analysis['intent'].value} (confidence: {analysis.get('confidence', 0):.2f})")
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Intent analysis failed: {e}")
            return IntentAnalyzer._fallback_analysis(query)
    
    @staticmethod
    def _fallback_analysis(query: str) -> Dict:
        """Simple pattern-based fallback"""
        query_lower = query.lower()
        
        # Detect intent by keywords
        if any(w in query_lower for w in ['วันที่', 'เมื่อไหร่', 'วันไหน', 'กี่โมง']):
            intent = QueryIntent.FACTUAL
        elif any(w in query_lower for w in ['ทำอย่างไร', 'ยังไง', 'ขั้นตอน', 'วิธี']):
            intent = QueryIntent.PROCEDURAL
        elif any(w in query_lower for w in ['ต่างกัน', 'เหมือนกัน', 'เปรียบเทียบ']):
            intent = QueryIntent.COMPARATIVE
        elif any(w in query_lower for w in ['สรุป', 'วิเคราะห์', 'อธิบาย']):
            intent = QueryIntent.ANALYTICAL
        else:
            intent = QueryIntent.FACTUAL
        
        return {
            'intent': intent,
            'keywords': [],
            'temporal_refs': [],
            'entities': [],
            'confidence': 0.5
        }
    
    @staticmethod
    def get_search_params(analysis: Dict) -> Dict:
        """
        แปลง intent เป็นพารามิเตอร์สำหรับ search
        
        Returns:
            {
                "k_multiplier": int,
                "dense_weight": float,
                "sparse_weight": float,
                "keyword_boost": float,
                "need_diversity": bool
            }
        """
        intent = analysis.get('intent', QueryIntent.FACTUAL)
        confidence = analysis.get('confidence', 0.5)
        
        if intent == QueryIntent.FACTUAL:
            return {
                'k_multiplier': 2,
                'dense_weight': 0.4,
                'sparse_weight': 0.6,
                'keyword_boost': 0.4,
                'need_diversity': False
            }
        
        elif intent == QueryIntent.PROCEDURAL:
            return {
                'k_multiplier': 3,
                'dense_weight': 0.5,
                'sparse_weight': 0.5,
                'keyword_boost': 0.3,
                'need_diversity': True
            }
        
        elif intent == QueryIntent.COMPARATIVE:
            return {
                'k_multiplier': 4,
                'dense_weight': 0.6,
                'sparse_weight': 0.4,
                'keyword_boost': 0.2,
                'need_diversity': True
            }
        
        elif intent == QueryIntent.ANALYTICAL:
            return {
                'k_multiplier': 4,
                'dense_weight': 0.7,
                'sparse_weight': 0.3,
                'keyword_boost': 0.2,
                'need_diversity': True
            }
        
        else:  # CONVERSATIONAL
            return {
                'k_multiplier': 1,
                'dense_weight': 0.6,
                'sparse_weight': 0.4,
                'keyword_boost': 0.1,
                'need_diversity': False
            }

# Global singleton
intent_analyzer = IntentAnalyzer()