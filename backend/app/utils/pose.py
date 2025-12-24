import logging
from app.utils.llm.llm_model import get_llm_model, log_llm_usage
from app.prompt.motion_prompt import motion_prompt
from app.config import (
    LLM_PROVIDER, 
    GEMINI_MODEL_NAME, 
    OPENAI_MODEL_NAME, 
    LOCAL_MODEL_NAME
)

logger = logging.getLogger(__name__)

async def suggest_pose(text: str) -> str:
    """
    วิเคราะห์ข้อความแล้วแนะนำท่าทาง (Async Version)
    """
    try:
        prompt = motion_prompt.format(text=text)
        model = get_llm_model()

        if LLM_PROVIDER == "gemini":
            # เรียกใช้ผ่าน .aio (Async Client ของ GenAI SDK)
            response = await model.aio.models.generate_content(
                model=GEMINI_MODEL_NAME, 
                contents=prompt
            )
            reply = response.text.strip().replace('"', '')

        elif LLM_PROVIDER in ["openai", "local"]:
            m_name = OPENAI_MODEL_NAME if LLM_PROVIDER == "openai" else LOCAL_MODEL_NAME
            # ต้อง await เนื่องจาก model เป็น AsyncOpenAI
            response = await model.chat.completions.create(
                model=m_name,
                messages=[{"role": "user", "content": prompt}],
            )
            reply = response.choices[0].message.content.strip().replace('"', '')

        else:
            raise ValueError(f"❌ ไม่รู้จัก LLM_PROVIDER: {LLM_PROVIDER}")

        log_llm_usage(response, context="suggest_pose")
        print("POSE:" + reply)
        return reply

    except Exception as e:
        logger.error(f"❌ Error in suggest_pose: {e}")
        return "none"