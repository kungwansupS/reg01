import logging
import re
from typing import List

from ..repositories.knowledge_store import KnowledgeStore
from ..repositories.session_store import SessionStore
from ..schemas import AssistantReply, RetrievedChunk
from .llm_gateway import LLMGateway


logger = logging.getLogger(__name__)

UNKNOWN_INFO_TH = "ข้อมูลส่วนนี้ไม่มีระบุ"
UNKNOWN_INFO_EN = "I do not have verified information for that yet."
TEMP_ERROR_TH = "ขออภัยครับ ระบบกำลังไม่พร้อมใช้งานชั่วคราว กรุณาลองใหม่อีกครั้ง"


class AssistantService:
    def __init__(self, session_store: SessionStore, kb: KnowledgeStore, gateway: LLMGateway) -> None:
        self.session_store = session_store
        self.kb = kb
        self.gateway = gateway

    async def answer(self, session_id: str, platform: str, message: str) -> AssistantReply:
        text = (message or "").strip()
        if not text:
            return AssistantReply(
                text="ยังไม่ได้รับคำถามครับ กรุณาพิมพ์คำถามอีกครั้ง",
                motion="Idle",
                provider="none",
                model="none",
                sources=[],
            )

        self.session_store.append_message(session_id, platform, "user", text)

        deterministic = self._deterministic_reply(text)
        if deterministic:
            self.session_store.append_message(session_id, platform, "model", deterministic)
            return AssistantReply(
                text=deterministic,
                motion=self._pick_motion(deterministic),
                provider="rule",
                model="deterministic",
                sources=[],
            )

        sources = self.kb.search(text, k=5)
        history = self.session_store.get_recent_messages(session_id, limit=10)

        system_prompt = (
            "You are REG-01, a university assistant. "
            "Always answer in the same language as the user. "
            "Use only the provided context for factual claims. "
            "If context is missing or insufficient, clearly say: "
            "'ข้อมูลส่วนนี้ไม่มีระบุ' for Thai users, or "
            "'I do not have verified information for that yet.' for non-Thai users. "
            "Be concise, natural, and helpful."
        )
        history_text = "\n".join([f"{role}: {msg}" for role, msg in history])
        context = self._format_context(sources)
        user_prompt = (
            f"Recent chat:\n{history_text}\n\n"
            f"User question:\n{text}\n\n"
            f"Reference context:\n{context}\n\n"
            "Answer using context-first grounding and avoid fabricating details."
        )

        try:
            answer_text, provider, model_name = await self.gateway.generate(system_prompt, user_prompt)
            answer_text = self._post_process(answer_text, sources, text)
        except Exception as exc:
            logger.error("Assistant failed: %s", exc)
            answer_text = TEMP_ERROR_TH
            provider = "none"
            model_name = "none"

        self.session_store.append_message(session_id, platform, "model", answer_text)
        return AssistantReply(
            text=answer_text,
            motion=self._pick_motion(answer_text),
            provider=provider,
            model=model_name,
            sources=sources,
        )

    def _deterministic_reply(self, text: str) -> str | None:
        lower = text.lower().strip()
        if lower in {"สวัสดี", "hello", "hi", "hey"}:
            return "สวัสดีครับ ผมพร้อมช่วยตอบคำถามเกี่ยวกับมหาวิทยาลัยครับ"
        if "ขอบคุณ" in text or "thank" in lower:
            return "ยินดีครับ หากต้องการข้อมูลเพิ่มเติมถามได้เลย"
        if re.search(r"^(test|ping)$", lower):
            return "ระบบพร้อมใช้งานครับ"
        return None

    def _format_context(self, sources: List[RetrievedChunk]) -> str:
        if not sources:
            return "NO_CONTEXT"
        blocks = []
        for idx, item in enumerate(sources, start=1):
            blocks.append(f"[{idx}] source={item.source}\n{item.chunk[:1800]}")
        return "\n\n".join(blocks)

    def _pick_motion(self, text: str) -> str:
        lower = text.lower()
        if "ขออภัย" in text or "sorry" in lower:
            return "Sad"
        if "ยินดี" in text or "สวัสดี" in text or "thank" in lower:
            return "Wave"
        if UNKNOWN_INFO_TH in text or UNKNOWN_INFO_EN.lower() in lower:
            return "Idle"
        return "Talking"

    def _post_process(self, answer_text: str, sources: List[RetrievedChunk], user_text: str) -> str:
        answer_text = (answer_text or "").strip()
        if not answer_text:
            return self._unknown_text(user_text)

        answer_text = answer_text.replace("<think>", "").replace("</think>", "").strip()
        if not sources:
            return self._unknown_text(user_text)
        return answer_text

    def _unknown_text(self, user_text: str) -> str:
        has_thai = bool(re.search(r"[\u0E00-\u0E7F]", user_text or ""))
        return UNKNOWN_INFO_TH if has_thai else UNKNOWN_INFO_EN
