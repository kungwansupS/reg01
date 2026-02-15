"""
Pose Suggestion — Rule-Based (v3)

แทนที่ LLM-based pose suggestion ด้วย keyword matching
ไม่ต้องเรียก API — ประหยัด 1 LLM call ต่อ response
"""
import re
import logging

logger = logging.getLogger(__name__)

# Pattern → motion mapping (checked in order, first match wins)
_POSE_RULES = [
    # FlickDown → ไม่แน่ใจ, สงสัย, คิดหนัก
    (re.compile(r"(ไม่แน่ใจ|ไม่มีข้อมูล|ไม่ทราบ|ยังไม่|ไม่มีระบุ|ไม่พบ|not sure|unknown)", re.IGNORECASE), "FlickDown"),
    # Flick@Body → ปฏิเสธ, ไม่ชอบ, ไม่เห็นด้วย
    (re.compile(r"(ไม่สามารถ|ไม่ได้|ขออภัย|ขัดข้อง|ผิดพลาด|sorry|cannot|error)", re.IGNORECASE), "Flick@Body"),
    # Tap@Body → ไม่เข้าใจ, งง, ไม่ชัดเจน
    (re.compile(r"(ไม่เข้าใจ|ช่วยอธิบาย|หมายถึง|ไม่ชัดเจน|unclear)", re.IGNORECASE), "Tap@Body"),
    # Flick → เห็นด้วย, ตกลง, ยืนยัน
    (re.compile(r"(ได้เลย|ถูกต้อง|ครับ|ค่ะ|ใช่|ยืนยัน|ok|yes|correct|sure)", re.IGNORECASE), "Flick"),
    # Tap → เน้นคำ, เรียกความสนใจ (เช่น มีวันที่ หรือข้อมูลสำคัญ)
    (re.compile(r"(\d{1,2}\s*(มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม))", re.IGNORECASE), "Tap"),
    (re.compile(r"(สำคัญ|ต้อง|อย่าลืม|กำหนด|deadline|important)", re.IGNORECASE), "Tap"),
]


async def suggest_pose(text: str) -> str:
    """
    วิเคราะห์คำพูดเพื่อแนะนำท่าทาง — Rule-based (ไม่ต้องเรียก LLM)
    """
    try:
        clean_text = str(text or "").strip()
        if not clean_text:
            return "Idle"

        for pattern, motion in _POSE_RULES:
            if pattern.search(clean_text):
                logger.debug(f"Pose: {motion} (matched: {pattern.pattern[:40]})")
                return motion

        return "Idle"

    except Exception as e:
        logger.error(f"Error in suggest_pose: {e}")
        return "Idle"