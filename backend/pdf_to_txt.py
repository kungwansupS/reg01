import os
import fitz  # PyMuPDF
import hashlib
import logging
from dotenv import load_dotenv
from app.config import PDF_INPUT_FOLDER, PDF_QUICK_USE_FOLDER, debug_list_files
from app.utils.llm.llm_model import get_llm_model, log_llm_usage

load_dotenv()

PDF_FOLDER = PDF_INPUT_FOLDER
OUTPUT_FOLDER = PDF_QUICK_USE_FOLDER
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HASH_RECORD_FILE = os.path.join(BASE_DIR, "app/cache/file_hashes.txt")


os.makedirs(OUTPUT_FOLDER, exist_ok=True)
logger = logging.getLogger(__name__)

model = get_llm_model()

def fix_encoding_errors(text):
    replacements = {
        '': 'ุ', '': 'ิ', '': 'ิ', '': 'ื', '': 'ี',
        '': 'ู', '': 'ุ', '': 'ฺ', '': 'ฦ', '': '๋',
        '': '่', '': '้', '': '๊', '': '๋', '': '์',
        '': 'ํ', '': 'ำ', '': '็',
    }
    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)
    return text

def get_file_hash(filepath):
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def load_previous_hashes():
    if not os.path.exists(HASH_RECORD_FILE):
        return {}
    with open(HASH_RECORD_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return {line.split("||")[0]: line.strip().split("||")[1] for line in lines if "||" in line}

def save_hashes(hash_dict):
    with open(HASH_RECORD_FILE, "w", encoding="utf-8") as f:
        for filename, hashval in hash_dict.items():
            f.write(f"{filename}||{hashval}\n")

def organize_with_llm(raw_text, filename):
    prompt = f"""
        ต่อไปนี้คือข้อความที่ดึงมาจากไฟล์ PDF ชื่อว่า {filename}:

        ---
        {raw_text}
        ---

        โปรดจัดเรียงเนื้อหาให้เป็นระเบียบตามหัวข้อ ปีการศึกษา / กำหนดการ / หมวดหมู่ โดยไม่แปล
        ให้ขึ้นหัวเรื่องอย่างเหมาะสม เหมือนบันทึกช่วยจำ

        แบ่งช่วงด้วย "===================" การแบ่งช่วงพยายามไม่ให้เกิน 3000 ตัวอักษรหากทำได้
        และแบ่งส่วนเป็นส่วนๆ ตัวอย่างเช่น 

            ===================

            **ภาคการศึกษาที่ 1/....**

            *   **การลงทะเบียน:**
                *   วันลงทะเบียนเรียนล่วงหน้า: ....
                *   วันที่อาจารย์ที่ปรึกษาให้ความเห็นชอบการลงทะเบียนเรียนล่วงหน้า: ....
                *   วันประกาศผลการลงทะเบียนล่วงหน้า: ....
                *   วันยกเลิกกระบวนวิชาที่ไม่ผ่านเงื่อนไข (Prerequisite):....
                *   วันลงทะเบียน เพิ่ม ถอน และเปลี่ยนตอนกระบวนวิชา: ....
                *   วันประมวลผลการลงทะเบียน เพิ่ม ถอน และเปลี่ยนตอนกระบวนวิชา: ....
                *   วันลงทะเบียน เพิ่ม และเปลี่ยนตอนกระบวนวิชาผ่านภาควิชา: ....
                *   วันที่อาจารย์ที่ปรึกษาให้ความเห็นชอบการลงทะเบียนเรียน: ....
                *   วันประกาศผลสรุปการลงทะเบียน เพิ่ม ถอนกระบวนวิชา: ....
                *   วันลงทะเบียน เพิ่ม เปลี่ยนตอนกระบวนวิชาหลังกำหนด: ....

            ===================

            **ภาคการศึกษาที่ 1/....**

            *   **นักศึกษาใหม่:**
                *   วันรายงานตัวขึ้นทะเบียนเป็นนักศึกษาปริญญาตรี รหัส....: ....
                *   วันรายงานตัวขึ้นทะเบียนเป็นนักศึกษาบัณฑิตศึกษา รหัส 68.... ....
                *   วันรายงานตัวขึ้นทะเบียนเป็นนักศึกษาบัณฑิตศึกษา รหัส 68.... (รอบที่ 2): ....
                *   วันรายงานตัวขึ้นทะเบียนเป็นนักศึกษาบัณฑิตศึกษา รหัส 68.... (รอบที่ 3): ....
                *   วันประชุมผู้ปกครองนักศึกษาใหม่ ระดับปริญญาตรี: ....
                *   วันทดสอบความรู้และทักษะภาษาอังกฤษ ระดับปริญญาตรี ชั้นปีที่ 1 (CMU-ePro): ....
                *   วันจัดกิจกรรมคณะ - วิทยาลัย ระดับปริญญาตรี: ....
                *   วันปฐมนิเทศนักศึกษาใหม่ สำหรับนักศึกษาปริญญาตรี: ....
                *   วันปฐมนิเทศนักศึกษาใหม่ สำหรับนักศึกษาบัณฑิตศึกษา: ....
                *   วันลงทะเบียนกระบวนวิชานักศึกษาใหม่ รหัส 68...: ....
        
        เนื้อหาย่อยทั้งหมดจะต้องระบุเนื้อหาหลักเอาไว้ด้วยและเนื้อหาย่อยทั้งหมดต้องย่อยให้ละเอียดแบ่งให้ได้มากที่สุด
        ทั้งนี้ขึ้นอยู่กับข้อมูลด้วยว่าเป็นประเภทไหนแต่จะต้องเก็บใจความสำคัญสำหรับไฟล์เอาไว้ เนื่องจาก"==================="จะทำการตัดเนื้อหา อาจทำให้ข้อมูลหาย และอาจตัดเนื้อหาที่ไม่มีสาระสำคัญทิ้งได้

        """
    try:
        logger.info(f"ส่ง prompt ให้ LLM สำหรับไฟล์ {filename}")
        response = model.generate_content(prompt)
        log_llm_usage(response, f"organize PDF: {filename}")
        return response.text
    except Exception as e:
        logger.error(f"LLM error: {e}")
        return ""

def process_pdfs():
    logger.info(f"ตรวจโฟลเดอร์: {PDF_FOLDER}")
    old_hashes = load_previous_hashes()
    new_hashes = {}
    pdf_paths = set()
    pdf_found = False

    for root, _, files in os.walk(PDF_FOLDER):
        for filename in sorted(files):
            if filename.endswith(".pdf"):
                pdf_found = True
                pdf_path = os.path.join(root, filename)
                rel_path = os.path.relpath(pdf_path, PDF_FOLDER).replace("\\", "/")
                pdf_paths.add(rel_path)
                file_hash = get_file_hash(pdf_path)
                new_hashes[rel_path] = file_hash

                logger.info(f"เจอ PDF: {rel_path}")

                if rel_path in old_hashes and old_hashes[rel_path] == file_hash:
                    logger.info(f"ข้าม: {rel_path} (ยังไม่เปลี่ยน)")
                    continue

                logger.info(f"แปลงใหม่: {rel_path}")
                doc = fitz.open(pdf_path)
                raw_text = ""
                for i in range(len(doc)):
                    text = doc.load_page(i).get_text()
                    raw_text += f"- หน้า {i+1} ---" + fix_encoding_errors(text)
                organized = organize_with_llm(raw_text, filename)
                if organized.strip():
                    out_path = os.path.join(OUTPUT_FOLDER, rel_path).replace(".pdf", ".txt")
                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(organized)
                    logger.info(f"สร้างไฟล์ TXT ที่: {out_path}")
                else:
                    logger.warning(f"ไม่สามารถจัดเรียงไฟล์ {filename} ได้ — ข้ามการบันทึก")

    if not pdf_found:
        logger.warning("ไม่พบไฟล์ PDF ใน docs/")

    for root, _, files in os.walk(OUTPUT_FOLDER):
        for filename in files:
            if filename.endswith(".txt"):
                txt_path = os.path.join(root, filename)
                rel_txt = os.path.relpath(txt_path, OUTPUT_FOLDER).replace("\\", "/")
                rel_pdf = rel_txt.replace(".txt", ".pdf")
                if rel_pdf not in pdf_paths:
                    logger.info(f"ลบไฟล์ที่ไม่มีต้นฉบับ: {rel_txt}")
                    os.remove(txt_path)

    save_hashes(new_hashes)

    existing_txt = []
    for root, _, files in os.walk(OUTPUT_FOLDER):
        for f in files:
            if f.endswith(".txt"):
                existing_txt.append(os.path.relpath(os.path.join(root, f), OUTPUT_FOLDER).replace("\\", "/"))
    logger.info(f"ไฟล์ TXT ที่มีอยู่หลังประมวลผล: {existing_txt}")
    logger.info("ตรวจสอบและจัดเรียง PDF เสร็จสิ้น")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    process_pdfs()
