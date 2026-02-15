"""
Rule-Based Intent Analyzer
แทนที่ LLM-based intent analysis ด้วย rule-based approach
ไม่ต้องใช้ API call ใดๆ — ทำงานได้ทันทีแบบ local
"""
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("IntentAnalyzer")

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# วันที่ / เวลา / ปฏิทิน
_DATE_QUERY_PATTERNS = [
    re.compile(r"(วันเปิด|วันปิด|เปิดเทอม|ปิดเทอม|เปิดภาค|ปิดภาค)", re.IGNORECASE),
    re.compile(r"(วันสอบ|สอบกลางภาค|สอบปลายภาค|สอบไล่)", re.IGNORECASE),
    re.compile(r"(วันถอน|ถอนวิชา|ถอนกระบวนวิชา|ดรอป)", re.IGNORECASE),
    re.compile(r"(วันลง|ลงทะเบียน|ลงเรียน)", re.IGNORECASE),
    re.compile(r"(วันชำระ|ชำระเงิน|จ่ายเงิน|ค่าธรรมเนียม|ค่าเทอม)", re.IGNORECASE),
    re.compile(r"(วันรายงานตัว|รายงานตัว|ปฐมนิเทศ)", re.IGNORECASE),
    re.compile(r"(วันสำคัญ|กำหนดการ|ปฏิทิน|ตารางสอบ)", re.IGNORECASE),
    re.compile(r"(วันไหน|เมื่อไหร่|กี่โมง|ช่วงไหน|ถึงวันไหน)", re.IGNORECASE),
    re.compile(r"(เริ่มเรียน|หยุดเรียน|วันหยุด)", re.IGNORECASE),
    re.compile(r"(CMU-eGrad|CMU-ePro)", re.IGNORECASE),
    re.compile(r"(กิจกรรม|พิธี|งาน)", re.IGNORECASE),
]

# นโยบาย / ระเบียบ
_POLICY_QUERY_PATTERNS = [
    re.compile(r"(ระเบียบ|ข้อบังคับ|กฎ|เกณฑ์|หลักเกณฑ์)", re.IGNORECASE),
    re.compile(r"(ทำยังไง|ต้องทำอะไร|ขั้นตอน|วิธี)", re.IGNORECASE),
    re.compile(r"(ไม่ทัน|ลืม|ไม่ได้|พลาด|เลยกำหนด)", re.IGNORECASE),
    re.compile(r"(เงื่อนไข|สิทธิ์|คุณสมบัติ|ข้อกำหนด)", re.IGNORECASE),
    re.compile(r"(ได้รับ\s*w|ไม่ได้รับ\s*w|ติด\s*w|ติด\s*f)", re.IGNORECASE),
    re.compile(r"(qr\s*code|บัตรเครดิต|โอนเงิน|กองคลัง)", re.IGNORECASE),
    re.compile(r"(เกรด|gpa|gpax|หน่วยกิต|credit)", re.IGNORECASE),
]

# คำถามเชิงข้อเท็จจริง
_FACTUAL_QUERY_PATTERNS = [
    re.compile(r"(ที่ไหน|อยู่ไหน|สถานที่|ห้อง)", re.IGNORECASE),
    re.compile(r"(ใคร|อาจารย์|ผู้รับผิดชอบ|ติดต่อ)", re.IGNORECASE),
    re.compile(r"(กี่|จำนวน|เท่าไหร่|เท่าไร)", re.IGNORECASE),
    re.compile(r"(คืออะไร|หมายถึง|แปลว่า|คือ)", re.IGNORECASE),
]

# ปีการศึกษา
_ACADEMIC_YEAR_PATTERN = re.compile(r"\b(25\d{2})\b")

# ภาคเรียน
_SEMESTER_PATTERNS = [
    (re.compile(r"(ภาคเรียนที่|ภาคการศึกษาที่|เทอม)\s*1", re.IGNORECASE), 1),
    (re.compile(r"(ภาคเรียนที่|ภาคการศึกษาที่|เทอม)\s*2", re.IGNORECASE), 2),
    (re.compile(r"(ภาคเรียนที่|ภาคการศึกษาที่|เทอม)\s*3", re.IGNORECASE), 3),
    (re.compile(r"ภาคฤดูร้อน", re.IGNORECASE), 3),
    (re.compile(r"1\s*/\s*25\d{2}"), 1),
    (re.compile(r"2\s*/\s*25\d{2}"), 2),
    (re.compile(r"3\s*/\s*25\d{2}"), 3),
]

# ประเภทเอกสาร
_DOC_TYPE_PATTERNS = [
    (re.compile(r"(qr\s*code|บัตรเครดิต|เงินสด|ช่องทาง.*ชำระ|วิธี.*ชำระ|จ่าย.*ค่าเทอม|ชำระ.*ค่าเทอม|ตัดบัญชี)", re.IGNORECASE), "payment"),
    (re.compile(r"(ปฏิทิน|calendar|วันเปิด|วันปิด|วันสอบ|วันถอน|วันชำระ|ตารางสอบ|กำหนดการ)", re.IGNORECASE), "calendar"),
    (re.compile(r"(ระเบียบ|ข้อบังคับ|regulation|กฎ|เกณฑ์)", re.IGNORECASE), "regulation"),
    (re.compile(r"(หลักสูตร|curriculum|สาขา|วิชา)", re.IGNORECASE), "curriculum"),
]

# Expected answer type
_ANSWER_TYPE_PATTERNS = [
    (re.compile(r"(วันไหน|เมื่อไหร่|วันที่|ถึงวันไหน|เริ่มวัน)", re.IGNORECASE), "date"),
    (re.compile(r"(กี่|จำนวน|เท่าไหร่|เท่าไร|how many|how much)", re.IGNORECASE), "number"),
    (re.compile(r"(รายชื่อ|อะไรบ้าง|มีอะไร|ประกอบด้วย)", re.IGNORECASE), "list"),
]

# Key entity extraction
_ENTITY_PATTERNS = [
    (re.compile(r"เปิด(เทอม|ภาค|เรียน|ภาคเรียน|ภาคการศึกษา)", re.IGNORECASE), "เปิดภาคการศึกษา"),
    (re.compile(r"ปิด(เทอม|ภาค|เรียน)", re.IGNORECASE), "ปิดภาคการศึกษา"),
    (re.compile(r"สอบกลางภาค", re.IGNORECASE), "สอบกลางภาค"),
    (re.compile(r"สอบ(ปลายภาค|ไล่)", re.IGNORECASE), "สอบปลายภาค"),
    (re.compile(r"(ถอน|ดรอป)\s*(วิชา|กระบวนวิชา)?", re.IGNORECASE), "ถอนกระบวนวิชา"),
    (re.compile(r"(ลงทะเบียน|ลงเรียน)", re.IGNORECASE), "ลงทะเบียน"),
    (re.compile(r"(ชำระ|จ่าย)\s*(เงิน|ค่า)", re.IGNORECASE), "ชำระเงินค่าธรรมเนียม"),
    (re.compile(r"(รายงานตัว)", re.IGNORECASE), "รายงานตัว"),
    (re.compile(r"(ปฐมนิเทศ)", re.IGNORECASE), "ปฐมนิเทศ"),
    (re.compile(r"(CMU-eGrad)", re.IGNORECASE), "CMU-eGrad"),
    (re.compile(r"(CMU-ePro)", re.IGNORECASE), "CMU-ePro"),
    (re.compile(r"(ได้รับ\s*w|ติด\s*w)", re.IGNORECASE), "ได้รับ W"),
    (re.compile(r"(ไม่ได้รับ\s*w)", re.IGNORECASE), "ไม่ได้รับ W"),
    (re.compile(r"(qr\s*code)", re.IGNORECASE), "QR Code"),
    (re.compile(r"(บัตรเครดิต)", re.IGNORECASE), "บัตรเครดิต"),
]


def _infer_current_semester() -> tuple:
    """อนุมานภาคเรียนปัจจุบันจากเดือนในปฏิทิน"""
    now = datetime.now()
    month = now.month
    year_be = now.year + 543

    if 5 <= month <= 10:
        return year_be, 1
    elif 11 <= month <= 12:
        return year_be, 2
    elif 1 <= month <= 3:
        return year_be - 1, 2
    else:  # April - May
        return year_be - 1, 3


def analyze_intent(query: str) -> Dict:
    """
    วิเคราะห์ intent ของคำถามแบบ rule-based
    ไม่ต้องเรียก LLM — ทำงานได้ทันที

    Args:
        query: คำถามจากผู้ใช้

    Returns:
        Dict with intent, expected_answer_type, key_entities,
        academic_year, semester, doc_type
    """
    text = " ".join(str(query or "").strip().split())
    if not text:
        return {"intent": "general", "expected_answer_type": "text"}

    # Detect intent
    # Policy patterns get a +1 bonus because "how-to" questions
    # often contain date-related keywords (e.g. "ถอนวิชาทำยังไง")
    # but the user intent is policy/procedure, not a date lookup.
    intent = "general"
    date_score = sum(1 for p in _DATE_QUERY_PATTERNS if p.search(text))
    policy_score = sum(1 for p in _POLICY_QUERY_PATTERNS if p.search(text))
    factual_score = sum(1 for p in _FACTUAL_QUERY_PATTERNS if p.search(text))

    if policy_score > 0 and policy_score >= date_score:
        intent = "policy_query"
    elif date_score > 0 and date_score > policy_score:
        intent = "date_query"
    elif factual_score > 0:
        intent = "factual_query"

    # Expected answer type
    expected_answer_type = "text"
    for pattern, answer_type in _ANSWER_TYPE_PATTERNS:
        if pattern.search(text):
            expected_answer_type = answer_type
            break
    if intent == "date_query" and expected_answer_type == "text":
        expected_answer_type = "date"

    # Key entities
    key_entities = []
    for pattern, entity in _ENTITY_PATTERNS:
        if pattern.search(text):
            key_entities.append(entity)
    key_entities = list(dict.fromkeys(key_entities))  # dedupe

    # Academic year
    academic_year = None
    year_match = _ACADEMIC_YEAR_PATTERN.search(text)
    if year_match:
        academic_year = year_match.group(1)

    # Semester
    semester = None
    for pattern, sem_num in _SEMESTER_PATTERNS:
        if pattern.search(text):
            semester = sem_num
            break

    # Document type (detect BEFORE year/semester inference)
    doc_type = None
    for pattern, dtype in _DOC_TYPE_PATTERNS:
        if pattern.search(text):
            doc_type = dtype
            break

    # ถ้าไม่ได้ระบุปี/เทอม ให้อนุมานจากเวลาปัจจุบัน
    # แต่ไม่อนุมานสำหรับ payment queries (ไม่มี year/semester filter)
    # และไม่อนุมาน semester เมื่อมี specific entities (เช่น CMU-eGrad)
    # เพราะ entity อาจอยู่ใน semester อื่นที่ไม่ใช่ปัจจุบัน
    if doc_type != "payment":
        if academic_year is None and (intent == "date_query" or date_score > 0):
            inferred_year, inferred_sem = _infer_current_semester()
            academic_year = str(inferred_year)
            # Only infer semester if user didn't mention specific entities
            if semester is None and not key_entities:
                semester = inferred_sem
        if doc_type is None and intent == "date_query":
            doc_type = "calendar"

    result = {
        "intent": intent,
        "expected_answer_type": expected_answer_type,
        "key_entities": key_entities,
        "academic_year": academic_year,
        "semester": semester,
        "doc_type": doc_type,
    }

    logger.info(
        "Intent: %s | Type: %s | Entities: %s | Year: %s | Sem: %s | Doc: %s",
        intent, expected_answer_type, key_entities,
        academic_year, semester, doc_type,
    )

    return result


def needs_retrieval(query: str) -> bool:
    """
    ตรวจสอบว่าคำถามนี้ต้องการค้นหาจาก knowledge base หรือไม่

    คำถามทั่วไป เช่น "สวัสดี", "ขอบคุณ" ไม่ต้องค้นหา
    """
    text = " ".join(str(query or "").strip().split()).lower()
    if not text:
        return False

    # Greeting / casual chat — ไม่ต้อง retrieve
    # Note: \b doesn't work with Thai script, so use startswith or exact match
    casual_starts_th = [
        "สวัสดี", "หวัดดี", "ขอบคุณ", "ขอบใจ", "บาย", "ลาก่อน", "ไปก่อน",
        "เป็นใคร", "ชื่ออะไร", "คุณคือใคร", "พี่เร็กคือใคร",
    ]
    casual_exact_th = ["ดี", "ดีครับ", "ดีค่ะ", "โอเค", "ได้เลย"]
    casual_starts_en = [
        "hi", "hello", "hey", "yo", "thank", "thanks", "bye",
        "you are", "who are",
    ]

    for start in casual_starts_th:
        if text.startswith(start) and len(text) < len(start) + 15:
            return False
    if text in casual_exact_th:
        return False
    for start in casual_starts_en:
        if text.startswith(start) and len(text) < len(start) + 15:
            return False

    # Very short messages (1-3 chars) likely not real questions
    if len(text) <= 3:
        return False

    return True
