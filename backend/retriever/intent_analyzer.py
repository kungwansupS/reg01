import logging
import asyncio
from typing import Dict, List
from enum import Enum

logger = logging.getLogger("IntentAnalyzer")

class QueryIntent(Enum):
    """ประเภทของความต้องการในคำถาม"""
    FACTUAL = "factual"              # ถามข้อเท็จจริง (วันที่, เวลา, สถานที่)
    PROCEDURAL = "procedural"        # ถามวิธีการ/ขั้นตอน
    COMPARATIVE = "comparative"      # เปรียบเทียบ
    ANALYTICAL = "analytical"        # วิเคราะห์/สรุป
    CONVERSATIONAL = "conversational" # สนทนาทั่วไป

class IntentAnalyzer:
    """
    วิเคราะห์ความต้องการจากคำถาม เพื่อปรับกลยุทธ์การค้นหา
    """
    
    @staticmethod
    async def analyze_intent(query: str) -> Dict:
        """
        วิเคราะห์ intent และสกัดข้อมูลสำคัญ
        
        Returns:
            {
                "intent": QueryIntent,
                "keywords": List[str],
                "temporal_refs": List[str],  # วันที่, ปี, ภาค
                "entities": List[str],        # ชื่อเฉพาะ, หน่วยงาน
                "confidence": float
            }
        """
        try:
            from app.utils.llm.llm_model import get_llm_model
            from app.config import LLM_PROVIDER, GEMINI_MODEL_NAME, OPENAI_MODEL_NAME, LOCAL_MODEL_NAME
            
            prompt = f"""วิเคราะห์คำถามนี้อย่างละเอียด:
"{query}"

ตอบเป็น JSON:
{{
    "intent": "factual|procedural|comparative|analytical|conversational",
    "keywords": ["คำสำคัญ1", "คำสำคัญ2", ...],
    "temporal_refs": ["2568", "ภาค 1", ...],
    "entities": ["ชื่อหน่วยงาน", "ชื่อกิจกรรม", ...],
    "confidence": 0.0-1.0
}}

คำอธิบาย intent:
- factual: ถามข้อเท็จจริงเฉพาะเจาะจง (วันที่, เวลา, ชื่อ)
- procedural: ถามวิธีการ/ขั้นตอน (ทำอย่างไร, สมัครยังไง)
- comparative: เปรียบเทียบ (ต่างกันอย่างไร, ดีกว่า)
- analytical: ขอวิเคราะห์/สรุป (สรุปให้หน่อย, เป็นยังไง)
- conversational: สนทนาทั่วไป (สวัสดี, ขอบคุณ)

กฎ:
- keywords: คำที่มีน้ำหนักสูง 5-10 คำ
- temporal_refs: ข้อมูลเวลา (ปี/ภาค/เดือน/วัน)
- entities: ชื่อเฉพาะทุกประเภท
- confidence: ความมั่นใจในการจัด intent (0.7+ = มั่นใจ)
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
            
            import json
            import re
            result = re.sub(r'```json\s*|\s*```', '', result).strip()
            
            analysis = json.loads(result)
            
            # Convert intent string to enum
            try:
                analysis['intent'] = QueryIntent(analysis['intent'])
            except:
                analysis['intent'] = QueryIntent.FACTUAL
            
            logger.info(f"🎯 Intent: {analysis['intent'].value} (confidence: {analysis.get('confidence', 0):.2f})")
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Intent analysis failed: {e}")
            # Fallback: simple pattern matching
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
                "k_multiplier": int,     # ดึงมากกว่า k เท่าไร
                "dense_weight": float,   # น้ำหนัก semantic
                "sparse_weight": float,  # น้ำหนัก keyword
                "keyword_boost": float,  # boost สำหรับ keyword match
                "need_diversity": bool   # ต้องการความหลากหลาย
            }
        """
        intent = analysis.get('intent', QueryIntent.FACTUAL)
        confidence = analysis.get('confidence', 0.5)
        
        if intent == QueryIntent.FACTUAL:
            # Factual: ต้องการความแม่นยำสูง
            return {
                'k_multiplier': 2,
                'dense_weight': 0.4,
                'sparse_weight': 0.6,  # เน้น keyword
                'keyword_boost': 0.4,
                'need_diversity': False
            }
        
        elif intent == QueryIntent.PROCEDURAL:
            # Procedural: ต้องการลำดับขั้นตอน
            return {
                'k_multiplier': 3,
                'dense_weight': 0.5,
                'sparse_weight': 0.5,
                'keyword_boost': 0.3,
                'need_diversity': True
            }
        
        elif intent == QueryIntent.COMPARATIVE:
            # Comparative: ต้องการหลายแหล่ง
            return {
                'k_multiplier': 4,
                'dense_weight': 0.6,
                'sparse_weight': 0.4,
                'keyword_boost': 0.2,
                'need_diversity': True
            }
        
        elif intent == QueryIntent.ANALYTICAL:
            # Analytical: ต้องการข้อมูลกว้าง
            return {
                'k_multiplier': 4,
                'dense_weight': 0.7,
                'sparse_weight': 0.3,
                'keyword_boost': 0.2,
                'need_diversity': True
            }
        
        else:  # CONVERSATIONAL
            # Conversational: ไม่ต้องการมาก
            return {
                'k_multiplier': 1,
                'dense_weight': 0.6,
                'sparse_weight': 0.4,
                'keyword_boost': 0.1,
                'need_diversity': False
            }

# Global singleton
intent_analyzer = IntentAnalyzer()
