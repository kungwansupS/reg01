import logging
from app.utils.llm.llm_model import get_llm_model, log_llm_usage
from app.prompt.motion_prompt import motion_prompt
from app.config import LLM_PROVIDER

logger = logging.getLogger(__name__)

def suggest_pose(text: str) -> str:
    """
    รับข้อความ แล้วให้ LLM แนะนำท่าทางที่เหมาะสม
    """
    try:
        prompt = motion_prompt.format(text=text)
        model = get_llm_model()

        if LLM_PROVIDER == "gemini":
            response = model.generate_content(prompt)
            reply = response.text.strip().replace('"', '')

        elif LLM_PROVIDER == "openai":
            from app.config import OPENAI_MODEL_NAME
            response = model.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
            )
            reply = response.choices[0].message.content.strip().replace('"', '')

        else:
            raise ValueError(f"❌ ไม่รู้จัก LLM_PROVIDER: {LLM_PROVIDER}")

        log_llm_usage(response, context="suggest_pose")
        print("POSE:" + reply)
        return reply

    except Exception as e:
        logger.exception("Gemini Error in suggest_pose")
        return "none"

