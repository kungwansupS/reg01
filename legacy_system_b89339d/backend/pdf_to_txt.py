import os
import fitz  # PyMuPDF
import hashlib
import logging
import asyncio
import time
from typing import List, Tuple, Optional, Dict
from collections import deque
from dotenv import load_dotenv
from app.config import PDF_INPUT_FOLDER, PDF_QUICK_USE_FOLDER, debug_list_files

load_dotenv()

PDF_FOLDER = PDF_INPUT_FOLDER
OUTPUT_FOLDER = PDF_QUICK_USE_FOLDER
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HASH_RECORD_FILE = os.path.join(BASE_DIR, "app/cache/file_hashes.txt")

# ========================================================================
# ✅ Multi-Provider Rate Limit Configuration
# ========================================================================
MAX_CHUNK_SIZE = 3000
MAX_PAGES_PER_CHUNK = 5
OVERLAP_SIZE = 200

# Rate Limits per Provider (TPM = Tokens Per Minute, RPM = Requests Per Minute)
RATE_LIMITS = {
    "gemini": {
        "tpm_limit": 15000,
        "safe_tpm": 13000,
        "rpm_limit": 30,
        "safe_rpm": 25, 
        "batch_size": 1,
        "batch_delay": 1.0,
        "window_seconds": 60
    }
}

# Retry configuration
RETRY_DELAY = 2.0
MAX_RETRIES = 5

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
logger = logging.getLogger(__name__)

# ========================================================================
# ✅ LLM Configuration - Gemini Gemma-3-27b-it
# ========================================================================
from google import genai
from google.genai import types

# ใช้ Gemini API โดยตรง - จะหา API key จาก GOOGLE_API_KEY environment variable
try:
    client = genai.Client()
    logger.info("✅ Gemini client initialized")
except Exception as e:
    logger.warning(f"⚠️ Failed to initialize Gemini client: {e}")
    client = None

MODEL_NAME = "gemma-3-27b-it" 

TOTAL_PDF_FILES = 0

def calculate_progress(total_files: int) -> float:
    hashes = load_previous_hashes()
    completed = len(hashes)
    if total_files == 0:
        return 100.0
    return (completed / total_files) * 100


def get_gemini_client():
    """สร้าง Gemini client instance"""
    global client
    if client is None:
        try:
            client = genai.Client()
            logger.info(f"✅ Loaded Gemini client for model: {MODEL_NAME}")
        except Exception as e:
            logger.error(f"❌ Failed to load Gemini client: {e}")
            raise
    return client

# Initialize client
llm_client = None

def init_llm_model():
    """Initialize LLM client"""
    global llm_client
    llm_client = get_gemini_client()
    return llm_client

# ========================================================================
# ✅ Universal Token & Request Tracker
# ========================================================================
class UniversalRateLimitTracker:
    """
    ติดตาม Token และ Request limits สำหรับทุก provider
    รองรับ TPM และ RPM limits พร้อมกัน
    """
    
    def __init__(self, provider: str = "gemini"):
        self.provider = provider
        self.config = RATE_LIMITS.get(provider, RATE_LIMITS["gemini"])
        
        # Token tracking
        self.tpm_limit = self.config["safe_tpm"]
        self.token_usage = deque()  # (timestamp, tokens)
        
        # Request tracking
        self.rpm_limit = self.config["safe_rpm"]
        self.request_times = deque()  # timestamps only
        
        self.window_seconds = self.config["window_seconds"]
        self.lock = asyncio.Lock()
        
        # Statistics
        self.total_tokens = 0
        self.total_requests = 0
        
        logger.info(f"🔧 Rate Limiter initialized for: {provider}")
        logger.info(f"   TPM Limit: {self.tpm_limit:,}")
        logger.info(f"   RPM Limit: {self.rpm_limit:,}")
        logger.info(f"   Batch Size: {self.config['batch_size']}")
        logger.info(f"   Batch Delay: {self.config['batch_delay']}s")
    
    def _cleanup_old_data(self, current_time: float):
        """ลบข้อมูลที่เก่ากว่า window"""
        cutoff_time = current_time - self.window_seconds
        
        # Cleanup tokens
        while self.token_usage and self.token_usage[0][0] < cutoff_time:
            self.token_usage.popleft()
        
        # Cleanup requests
        while self.request_times and self.request_times[0] < cutoff_time:
            self.request_times.popleft()
    
    def _get_current_usage(self, current_time: float) -> Dict[str, int]:
        """คำนวณ usage ปัจจุบัน"""
        self._cleanup_old_data(current_time)
        
        return {
            "tokens": sum(tokens for _, tokens in self.token_usage),
            "requests": len(self.request_times)
        }
    
    async def wait_if_needed(self, estimated_tokens: int):
        """รอถ้าใกล้เกิน rate limit (ทั้ง TPM และ RPM)"""
        async with self.lock:
            now = time.time()
            usage = self._get_current_usage(now)
            
            wait_reasons = []
            max_wait_time = 0
            
            # ✅ Check TPM limit
            if usage["tokens"] + estimated_tokens > self.tpm_limit:
                # หา timestamp ของ token ที่ต้องรอให้หมดอายุ
                temp_tokens = 0
                for timestamp, tokens in self.token_usage:
                    temp_tokens += tokens
                    if temp_tokens + estimated_tokens > self.tpm_limit:
                        wait_time = timestamp + self.window_seconds - now + 0.5
                        if wait_time > 0:
                            wait_reasons.append(f"TPM: {usage['tokens']}/{self.tpm_limit}")
                            max_wait_time = max(max_wait_time, wait_time)
                        break
            
            # ✅ Check RPM limit
            if usage["requests"] + 1 > self.rpm_limit:
                # หา timestamp ของ request แรกที่ต้องรอให้หมดอายุ
                if self.request_times:
                    oldest_request = self.request_times[0]
                    wait_time = oldest_request + self.window_seconds - now + 0.5
                    if wait_time > 0:
                        wait_reasons.append(f"RPM: {usage['requests']}/{self.rpm_limit}")
                        max_wait_time = max(max_wait_time, wait_time)
            
            # ✅ รอถ้าจำเป็น
            if max_wait_time > 0:
                logger.warning(
                    f"⏳ Rate limit protection ({', '.join(wait_reasons)}). "
                    f"Waiting {max_wait_time:.1f}s..."
                )
                await asyncio.sleep(max_wait_time)
                
                # Cleanup after waiting
                self._cleanup_old_data(time.time())
    
    async def record_usage(self, tokens_used: int):
        """บันทึกการใช้ token และ request"""
        async with self.lock:
            now = time.time()
            self.token_usage.append((now, tokens_used))
            self.request_times.append(now)
            self.total_tokens += tokens_used
            self.total_requests += 1
    
    def get_stats(self) -> Dict:
        """ดึงสถิติการใช้งาน"""
        now = time.time()
        usage = self._get_current_usage(now)
        
        return {
            "provider": self.provider,
            "current_tpm": usage["tokens"],
            "tpm_limit": self.tpm_limit,
            "tpm_percent": (usage["tokens"] / self.tpm_limit * 100) if self.tpm_limit != float('inf') else 0,
            "current_rpm": usage["requests"],
            "rpm_limit": self.rpm_limit,
            "rpm_percent": (usage["requests"] / self.rpm_limit * 100) if self.rpm_limit != float('inf') else 0,
            "total_tokens": self.total_tokens,
            "total_requests": self.total_requests,
            "batch_size": self.config["batch_size"],
            "batch_delay": self.config["batch_delay"]
        }

# ✅ จะถูกสร้างตอน runtime
rate_limiter = None

def init_rate_limiter():
    """Initialize rate limiter for Gemini"""
    global rate_limiter
    rate_limiter = UniversalRateLimitTracker("gemini")
    return rate_limiter

# ========================================================================
# Helper Functions
# ========================================================================

def fix_encoding_errors(text):
    """แก้ไขปัญหา encoding ภาษาไทย"""
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
    """บันทึก hash ทั้งหมด (ใช้ตอนจบการทำงาน)"""
    os.makedirs(os.path.dirname(HASH_RECORD_FILE), exist_ok=True)
    with open(HASH_RECORD_FILE, "w", encoding="utf-8") as f:
        for filename, hashval in hash_dict.items():
            f.write(f"{filename}||{hashval}\n")

def save_single_hash(rel_path: str, file_hash: str):
    """
    ✅ บันทึก hash ของไฟล์เดียวทันที (incremental save)
    """
    try:
        existing_hashes = load_previous_hashes()
        existing_hashes[rel_path] = file_hash
        
        os.makedirs(os.path.dirname(HASH_RECORD_FILE), exist_ok=True)
        with open(HASH_RECORD_FILE, "w", encoding="utf-8") as f:
            for filename, hashval in existing_hashes.items():
                f.write(f"{filename}||{hashval}\n")
        
        logger.info(f"  💾 Hash saved: {os.path.basename(rel_path)}")
        return True
    except Exception as e:
        logger.error(f"  ⚠️ Failed to save hash for {rel_path}: {e}")
        return False

def estimate_tokens(text: str, provider: str = "gemini") -> int:
    """
    ประมาณการ tokens ตาม provider
    """
    # Count character types
    thai_chars = sum(1 for c in text if '\u0e00' <= c <= '\u0e7f')
    eng_chars = sum(1 for c in text if c.isalpha() and c.isascii())
    numbers = sum(1 for c in text if c.isdigit())
    spaces = sum(1 for c in text if c.isspace())
    other = len(text) - thai_chars - eng_chars - numbers - spaces
    
    # Gemini uses SentencePiece (similar to Claude)
    tokens = (
        thai_chars * 0.7 +
        eng_chars * 0.3 +
        numbers * 0.2 +
        spaces * 0.1 +
        other * 0.4
    )
    
    return int(tokens) + 100

def smart_chunk_text(text: str, max_size: int = MAX_CHUNK_SIZE, overlap: int = OVERLAP_SIZE) -> List[str]:
    """แบ่งข้อความเป็น chunks แบบอัจฉริยะ"""
    if len(text) <= max_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + max_size, len(text))
        
        if end < len(text):
            newline_pos = text.rfind('\n', start, end)
            if newline_pos > start + max_size // 2:
                end = newline_pos + 1
            else:
                period_pos = text.rfind('。', start, end)
                if period_pos == -1:
                    period_pos = text.rfind('.', start, end)
                
                if period_pos > start + max_size // 2:
                    end = period_pos + 1
                else:
                    space_pos = text.rfind(' ', start, end)
                    if space_pos > start + max_size // 2:
                        end = space_pos + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - overlap if end < len(text) else end
    
    return chunks

TARGET_TOKENS = 13000
MAX_TOKENS = 15000
MIN_TOKENS = 2000

def extract_pages_in_groups(doc: fitz.Document) -> List[Tuple[int, str]]:
    """
    Group pages by estimated token size (content-aware)
    """
    page_groups = []

    current_text = ""
    current_tokens = 0
    group_start = 0

    for i in range(len(doc)):
        page_text = doc.load_page(i).get_text()
        page_text = fix_encoding_errors(page_text)

        header = f"\n--- หน้า {i+1} ---\n"
        combined = header + page_text

        page_tokens = estimate_tokens(combined, "gemini")

        if page_tokens > MAX_TOKENS:
            if current_text:
                page_groups.append((group_start, current_text))

            page_groups.append((i, combined))
            current_text = ""
            current_tokens = 0
            continue

        if current_tokens + page_tokens > MAX_TOKENS:
            page_groups.append((group_start, current_text))
            current_text = combined
            current_tokens = page_tokens
            group_start = i
            continue

        if not current_text:
            group_start = i

        current_text += combined
        current_tokens += page_tokens

    if current_text:
        page_groups.append((group_start, current_text))

    return page_groups

# ========================================================================
# ✅ LLM Functions with Universal Rate Limit Handling
# ========================================================================

async def organize_chunk_with_llm_retry(
    chunk_text: str, 
    filename: str, 
    chunk_index: int, 
    total_chunks: int
) -> str:
    """
    ประมวลผล chunk ด้วย universal rate limit protection
    """
    global llm_client
    if llm_client is None:
        llm_client = init_llm_model()
    
    prompt = f"""
        ต่อไปนี้คือข้อความที่ดึงมาจากไฟล์ PDF ชื่อว่า {filename}:

        ---
        {chunk_text}
        ---

        โปรดจัดเรียงเนื้อหาให้เป็นระเบียบตามหัวข้อ ปีการศึกษา / กำหนดการ / หมวดหมู่ โดยไม่แปล
        ให้ขึ้นหัวเรื่องอย่างเหมาะสม เหมือนบันทึกช่วยจำสำหรับ rag ที่จะแบ่งเป็น chunk ย่อยๆ

        แบ่งช่วงด้วย "===================" การแบ่งช่วงพยายามไม่ให้เกิน 3000 ตัวอักษรหากทำได้
        และแบ่งส่วนเป็นส่วนๆ ตัวอย่างเช่น 

            ===================
            filename.pdf

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
        
        เนื้อหาย่อยทั้งหมดจะต้องระบุเนื้อหาหลักเอาไว้ด้วยและเนื้อหาย่อยทั้งหมดต้องย่อยให้ละเอียดแบ่งให้ได้มากที่สุด ควรมีการกำกับเทอมและปีการศึกษาเอาไว้ในทุก chunk ที่มีความละเอียดอ่อน
        ทั้งนี้ขึ้นอยู่กับข้อมูลด้วยว่าเป็นประเภทไหนแต่จะต้องเก็บใจความสำคัญสำหรับไฟล์เอาไว้ เนื่องจาก"==================="จะทำการตัดเนื้อหา อาจทำให้ข้อมูลหาย และอาจตัดเนื้อหาที่ไม่มีสาระสำคัญทิ้งได้

        """

    # ประมาณการ tokens
    estimated_tokens = estimate_tokens(prompt, "gemini")
    
    for attempt in range(MAX_RETRIES):
        try:
            await rate_limiter.wait_if_needed(estimated_tokens)
            
            stats = rate_limiter.get_stats()
            logger.info(
                f"  📤 Chunk {chunk_index + 1}/{total_chunks} "
                f"[TPM: {stats['tpm_percent']:.0f}%, RPM: {stats['rpm_percent']:.0f}%] "
                f"(attempt {attempt + 1})"
            )
            
            response = await asyncio.to_thread(
                llm_client.models.generate_content,
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=4096
                )
            )
            
            result = response.text
            
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                tokens_used = response.usage_metadata.total_token_count
                await rate_limiter.record_usage(tokens_used)
                logger.debug(f"  📊 Actual tokens used: {tokens_used}")
            else:
                await rate_limiter.record_usage(estimated_tokens)
            
            logger.info(f"  ✅ Chunk {chunk_index + 1} processed ({len(result)} chars)")
            
            return result.strip()
            
        except Exception as e:
            error_msg = str(e)
            
            if "rate_limit" in error_msg.lower() or "429" in error_msg or "quota" in error_msg.lower() or "resource_exhausted" in error_msg.lower():
                wait_time = RETRY_DELAY * (2 ** attempt)
                
                import re
                match = re.search(r'try again in ([\d.]+)s', error_msg)
                if match:
                    wait_time = float(match.group(1)) + 0.5
                
                logger.warning(f"  ⏳ Rate limit hit. Waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
                
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"  ❌ Max retries reached for chunk {chunk_index + 1}")
                    return ""
            else:
                logger.error(f"  ❌ Error on chunk {chunk_index + 1}: {e}")
                
                if attempt == MAX_RETRIES - 1:
                    return ""
                
                await asyncio.sleep(RETRY_DELAY)
    
    return ""

async def merge_processed_chunks(chunks: List[str], filename: str) -> str:
    """รวม chunks (ไม่ใช้ LLM เพื่อประหยัด)"""
    if not chunks:
        return ""
    
    if len(chunks) == 1:
        return chunks[0]
    
    combined = "\n\n===================\n\n".join(chunks)
    logger.info(f"  📦 Merged {len(chunks)} chunks → {len(combined)} chars (no LLM)")
    
    return combined

# ========================================================================
# Main Processing Functions
# ========================================================================

async def process_single_pdf_async(
    pdf_path: str, 
    filename: str, 
    rel_path: str,
    file_hash: str
) -> bool:
    """ประมวลผล PDF ไฟล์เดียว"""
    try:
        logger.info(f"📄 Processing: {filename}")
        
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        logger.info(f"  📊 Total pages: {total_pages}")
        
        page_groups = extract_pages_in_groups(doc)
        logger.info(f"  📦 Split into {len(page_groups)} groups")
        
        processed_chunks = []
        
        batch_delay = rate_limiter.config["batch_delay"]
        
        for i, (_, text) in enumerate(page_groups):
            result = await organize_chunk_with_llm_retry(
                text, 
                filename, 
                i, 
                len(page_groups)
            )
            
            if result:
                processed_chunks.append(result)
            
            if i < len(page_groups) - 1:
                await asyncio.sleep(batch_delay)
        
        if not processed_chunks:
            logger.warning(f"  ⚠️ No content processed for {filename}")
            return False
        
        final_text = await merge_processed_chunks(processed_chunks, filename)
        
        out_path = os.path.join(OUTPUT_FOLDER, rel_path).replace(".pdf", ".txt")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(final_text)
        
        stats = rate_limiter.get_stats()
        logger.info(
            f"  ✅ Saved: {out_path} ({len(final_text)} chars) "
            f"[Total: {stats['total_tokens']:,} tokens, {stats['total_requests']} requests]"
        )
        
        save_single_hash(rel_path, file_hash)

        completed = len(load_previous_hashes())
        progress = calculate_progress(TOTAL_PDF_FILES)

        logger.info(
            f"📈 Conversion Progress: {progress:.2f}% "
            f"({completed}/{TOTAL_PDF_FILES} files completed)"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Error processing {filename}: {e}")
        import traceback
        traceback.print_exc()
        return False

async def process_pdfs_async():
    """ประมวลผล PDF ทั้งหมด"""
    init_rate_limiter()
    init_llm_model()
    
    logger.info(f"🔍 Scanning folder: {PDF_FOLDER}")
    
    old_hashes = load_previous_hashes()
    new_hashes = {}
    pdf_paths = set()

    for root, _, files in os.walk(PDF_FOLDER):
        for filename in files:
            if filename.endswith(".pdf"):
                rel_path = os.path.relpath(
                    os.path.join(root, filename), PDF_FOLDER
                ).replace("\\", "/")
                pdf_paths.add(rel_path)

    global TOTAL_PDF_FILES
    TOTAL_PDF_FILES = len(pdf_paths)

    logger.info(f"📊 Total PDF files detected: {TOTAL_PDF_FILES}")
    
    files_to_process = []
    
    for root, _, files in os.walk(PDF_FOLDER):
        for filename in sorted(files):
            if filename.endswith(".pdf"):
                pdf_path = os.path.join(root, filename)
                rel_path = os.path.relpath(pdf_path, PDF_FOLDER).replace("\\", "/")
                pdf_paths.add(rel_path)
                
                file_hash = get_file_hash(pdf_path)
                new_hashes[rel_path] = file_hash
                
                if rel_path in old_hashes and old_hashes[rel_path] == file_hash:
                    logger.info(f"⭐️ Skipping: {rel_path} (unchanged)")
                    continue
                
                files_to_process.append((pdf_path, filename, rel_path, file_hash))
    
    if not files_to_process:
        logger.info("✅ All files are up to date")
        save_hashes(new_hashes)
        return
    
    stats = rate_limiter.get_stats()
    logger.info(f"📋 Found {len(files_to_process)} files to process")
    logger.info(f"⚙️ Provider: {stats['provider']}")
    logger.info(f"⚙️ Model: {MODEL_NAME}")
    logger.info(f"⚙️ TPM Limit: {stats['tpm_limit']:,}")
    logger.info(f"⚙️ RPM Limit: {stats['rpm_limit']:,}")
    logger.info(f"⚙️ Batch Size: {stats['batch_size']}, Delay: {stats['batch_delay']}s")
    logger.info(f"💡 Hash saved after each file (resumable)")
    
    start_time = time.time()
    success_count = 0
    
    batch_delay = rate_limiter.config["batch_delay"]
    
    for i, (pdf_path, filename, rel_path, file_hash) in enumerate(files_to_process):
        logger.info(f"\n🔒 [{i+1}/{len(files_to_process)}] {filename}")
        
        success = await process_single_pdf_async(pdf_path, filename, rel_path, file_hash)
        if success:
            success_count += 1
        
        if i < len(files_to_process) - 1:
            logger.info(f"⏳ Waiting {batch_delay}s before next file...")
            await asyncio.sleep(batch_delay)
    
    total_time = time.time() - start_time
    final_stats = rate_limiter.get_stats()
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ Processing Complete!")
    logger.info(f"  Files: {success_count}/{len(files_to_process)}")
    logger.info(f"  Time: {total_time:.1f}s ({total_time/len(files_to_process):.1f}s/file)")
    logger.info(f"  Tokens: {final_stats['total_tokens']:,}")
    logger.info(f"  Requests: {final_stats['total_requests']}")
    logger.info(f"  Provider: {final_stats['provider']}")
    logger.info(f"  Model: {MODEL_NAME}")
    logger.info('='*60)
    
    for root, _, files in os.walk(OUTPUT_FOLDER):
        for filename in files:
            if filename.endswith(".txt"):
                txt_path = os.path.join(root, filename)
                rel_txt = os.path.relpath(txt_path, OUTPUT_FOLDER).replace("\\", "/")
                rel_pdf = rel_txt.replace(".txt", ".pdf")
                if rel_pdf not in pdf_paths:
                    logger.info(f"🗑️ Removing orphaned file: {rel_txt}")
                    os.remove(txt_path)
    
    save_hashes(new_hashes)
    logger.info("✅ PDF processing complete")

def process_pdfs():
    """Synchronous wrapper"""
    asyncio.run(process_pdfs_async())

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    process_pdfs()