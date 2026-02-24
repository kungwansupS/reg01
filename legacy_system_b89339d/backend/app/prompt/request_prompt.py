from app.prompt.multi_language.request_prompt_th import request_prompt_th
from app.prompt.multi_language.request_prompt_en import request_prompt_en
from app.prompt.multi_language.request_prompt_zh import request_prompt_zh
from app.prompt.multi_language.request_prompt_ja import request_prompt_ja

def get_language_instruction(language_code: str) -> str:
    if language_code.startswith("th"):
        return "ตอบเป็นภาษาไทยแบบภาษาพูดที่สุภาพ ชัดเจน เหมาะกับการอ่านออกเสียง"
    elif language_code.startswith("en"):
        return "Respond in clear, spoken-style English suitable for TTS. Avoid slang."
    elif language_code.startswith("zh"):
        return "請用簡體中文作答，不要使用拼音或翻譯"
    elif language_code.startswith("ja"):
        return "日本語で丁寧に答えてください。話し言葉スタイルでお願いします。"
    else:
        return "ตอบด้วยภาษาพูดที่เหมาะกับการอ่านออกเสียง"
    
def get_request_prompt(language_code: str) -> str:
    if language_code.startswith("th"):
        return request_prompt_th
    elif language_code.startswith("en"):
        return request_prompt_en
    elif language_code.startswith("zh"):
        return request_prompt_zh
    elif language_code.startswith("ja"):
        return request_prompt_ja
    return request_prompt_en
