"""
Comprehensive Bot Accuracy & Speed Test
Tests ~60 questions across 10+ categories including edge cases.
Measures accuracy (keyword matching) and response time.
Skips rate-limit wait time from measurements.
"""
import requests
import json
import re
import time
import sys
import os
import unicodedata
from datetime import datetime

BASE_URL = "http://localhost:5000"
API_KEY = "comprehensive-test-key"
SESSION_PREFIX = "comp_test_"
RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_results.json")

# ─── Test Cases ───────────────────────────────────────────────────
# Format: (category, question, must_contain_any, must_not_contain, description)

TEST_CASES = [
    # ══════════════════════════════════════════════════════════════
    # CAT 1: ปฏิทินการศึกษา ภาค 1/2568 (Calendar Semester 1)
    # ══════════════════════════════════════════════════════════════
    ("cal_sem1", "วันเปิดเทอม ภาคเรียนที่ 1 ปี 2568", ["23 มิถุนายน"], [], "เปิดเทอม 1/2568"),
    ("cal_sem1", "สอบกลางภาค เทอม 1/2568 วันไหน", ["25", "31", "สิงหาคม"], [], "สอบกลางภาค 1/2568"),
    ("cal_sem1", "วันสอบไล่ ภาคเรียนที่ 1/2568", ["20", "ตุลาคม", "3 พฤศจิกายน"], [], "สอบไล่ 1/2568"),
    ("cal_sem1", "ปิดเทอม 1/2568 วันไหน", ["4 พฤศจิกายน"], [], "ปิดเทอม 1/2568"),
    ("cal_sem1", "ลงทะเบียนเรียนล่วงหน้า เทอม 1/2568 ช่วงไหน", ["5", "11", "พฤษภาคม"], [], "ลงทะเบียนล่วงหน้า 1/2568"),
    ("cal_sem1", "ประกาศผลการศึกษา เทอม 1/2568 วันไหน", ["14 พฤศจิกายน"], [], "ประกาศผล 1/2568"),

    # ══════════════════════════════════════════════════════════════
    # CAT 2: ปฏิทินการศึกษา ภาค 2/2568 (Calendar Semester 2)
    # ══════════════════════════════════════════════════════════════
    ("cal_sem2", "เปิดเทอม 2/2568 วันไหน", ["17 พฤศจิกายน"], [], "เปิดเทอม 2/2568"),
    ("cal_sem2", "สอบกลางภาค เทอม 2/2568", ["19", "25", "มกราคม"], [], "สอบกลางภาค 2/2568"),
    ("cal_sem2", "สอบไล่ เทอม 2/2568 วันไหน", ["16", "29", "มีนาคม"], [], "สอบไล่ 2/2568"),
    ("cal_sem2", "ปิดเทอม 2/2568 วันไหน", ["30 มีนาคม"], [], "ปิดเทอม 2/2568"),
    ("cal_sem2", "ลงทะเบียนล่วงหน้า เทอม 2/2568", ["6", "12", "ตุลาคม"], [], "ลงทะเบียนล่วงหน้า 2/2568"),
    ("cal_sem2", "ประกาศผลการศึกษา เทอม 2/2568", ["10 เมษายน"], [], "ประกาศผล 2/2568"),

    # ══════════════════════════════════════════════════════════════
    # CAT 3: ภาคฤดูร้อน/2568 (Summer)
    # ══════════════════════════════════════════════════════════════
    ("cal_summer", "เปิดเทอม ภาคฤดูร้อน 2568 วันไหน", ["20 เมษายน 2569"], [], "เปิดเทอมฤดูร้อน"),
    ("cal_summer", "ลงทะเบียนล่วงหน้า ภาคฤดูร้อน 2568", ["30 มีนาคม", "5 เมษายน"], [], "ลงทะเบียนล่วงหน้าฤดูร้อน"),
    ("cal_summer", "ชำระเงิน ภาคฤดูร้อน 2568", ["27 เมษายน", "1 พฤษภาคม"], [], "ชำระเงินฤดูร้อน"),

    # ══════════════════════════════════════════════════════════════
    # CAT 4: การถอนวิชา (Withdrawal)
    # ══════════════════════════════════════════════════════════════
    ("withdraw", "ถอนวิชาโดยได้รับ W ภาค 1/2568 ได้ถึงเมื่อไหร่", ["7 กรกฎาคม", "19 กันยายน"], [], "ถอน W 1/2568"),
    ("withdraw", "ถอนวิชาโดยไม่ได้รับ W ภาค 1/2568 ได้ถึงเมื่อไหร่", ["มิถุนายน", "กรกฎาคม"], [], "ถอน ไม่ W 1/2568"),
    ("withdraw", "ถอนวิชาได้รับ W เทอม 2/2568", ["1 ธันวาคม", "13 กุมภาพันธ์"], [], "ถอน W 2/2568"),
    ("withdraw", "ถอนวิชาไม่ได้รับ W ภาคฤดูร้อน 2568", ["13", "24", "เมษายน"], [], "ถอน ไม่ W ฤดูร้อน"),
    ("withdraw", "ดรอปวิชา เทอม 1/2568 ได้ถึงวันไหน", ["กรกฎาคม", "กันยายน"], [], "ดรอป=ถอน synonym test"),

    # ══════════════════════════════════════════════════════════════
    # CAT 5: การชำระเงิน (Payment)
    # ══════════════════════════════════════════════════════════════
    ("payment", "ชำระเงินค่าธรรมเนียม ภาค 1/2568 วันไหน", ["7", "11", "กรกฎาคม"], [], "ชำระเงิน 1/2568"),
    ("payment", "ชำระเงิน เทอม 2/2568", ["1", "5", "ธันวาคม"], [], "ชำระเงิน 2/2568"),
    ("payment", "ชำระค่าเทอมด้วย QR Code ได้ถึงกี่โมง", ["23.00", "23:00"], [], "QR Code เวลา"),
    ("payment", "จ่ายค่าเทอมด้วยบัตรเครดิตที่กองคลัง ได้ถึงกี่โมง", ["16.30", "16:30"], [], "บัตรเครดิตกองคลัง"),
    ("payment", "ชำระค่าเทอมด้วยเงินสดได้ที่ไหน", ["ธนาคาร"], [], "เงินสดที่ไหน"),
    ("payment", "จ่ายค่าเทอมออนไลน์ได้ถึงกี่โมง", ["23.00", "23:00"], [], "ออนไลน์เวลา"),
    ("payment", "ช่องทางชำระค่าเทอมมีอะไรบ้าง", ["QR", "เงินสด", "บัตรเครดิต"], [], "ช่องทางทั้งหมด"),

    # ══════════════════════════════════════════════════════════════
    # CAT 6: นักศึกษาใหม่ (New Students)
    # ══════════════════════════════════════════════════════════════
    ("new_student", "วันปฐมนิเทศ นักศึกษาใหม่ปริญญาตรี ปี 2568", ["18 มิถุนายน"], [], "ปฐมนิเทศ ป.ตรี"),
    ("new_student", "รายงานตัวขึ้นทะเบียน นักศึกษาใหม่ปริญญาตรี รหัส 68", ["10", "13", "มิถุนายน"], [], "รายงานตัว ป.ตรี"),
    ("new_student", "สอบ CMU-ePro ปี 2568 วันไหน", ["13", "17", "มิถุนายน"], [], "CMU-ePro"),
    ("new_student", "ปฐมนิเทศ บัณฑิตศึกษา 2568", ["20 มิถุนายน"], [], "ปฐมนิเทศ บัณฑิตศึกษา"),
    ("new_student", "ประชุมผู้ปกครอง ปี 2568 วันไหน", ["13 มิถุนายน"], [], "ประชุมผู้ปกครอง"),

    # ══════════════════════════════════════════════════════════════
    # CAT 7: บัณฑิตศึกษา (Graduate)
    # ══════════════════════════════════════════════════════════════
    ("graduate", "สอบ CMU-eGrad ปี 2568 วันไหน", ["กันยายน"], [], "CMU-eGrad"),
    ("graduate", "รายงานตัว บัณฑิตศึกษา รอบ 1 รหัส 68 วันไหน", ["5 มีนาคม"], [], "รายงานตัว บัณฑิตศึกษา รอบ 1"),
    ("graduate", "ส่งเอกสารขอขยายเวลา บัณฑิตศึกษา เทอม 1/2568", ["1 กันยายน"], [], "ขยายเวลา บัณฑิต"),

    # ══════════════════════════════════════════════════════════════
    # CAT 8: กำหนดการอื่นๆ (Other Deadlines)
    # ══════════════════════════════════════════════════════════════
    ("misc", "ส่งเอกสารย้ายสาขาวิชา เทอม 1/2568", ["27 มิถุนายน"], [], "ย้ายสาขา 1/2568"),
    ("misc", "แก้อักษร I ปริญญาตรี เทอม 1/2568 ส่งเมื่อไหร่", ["22 กรกฎาคม"], [], "แก้ I ป.ตรี 1/2568"),
    ("misc", "ขอรับอักษร I เทอม 1/2568 ช่วงไหน", ["14 ตุลาคม", "3 พฤศจิกายน"], [], "ขอรับ I 1/2568"),
    ("misc", "พ้นสถานภาพนักศึกษา เทอม 1/2568 วันไหน", ["23 กรกฎาคม"], [], "พ้นสถานภาพ 1/2568"),
    ("misc", "ยื่นคำร้องขอ V เทอม 1/2568", ["21", "25", "กรกฎาคม"], [], "ขอ V 1/2568"),

    # ══════════════════════════════════════════════════════════════
    # CAT 9: คำถามภาษาอังกฤษ (English Questions)
    # ══════════════════════════════════════════════════════════════
    ("english", "When does semester 1/2568 start?", ["23", "June", "มิถุนายน"], [], "English: semester start"),
    ("english", "When is the midterm exam for semester 1/2568?", ["25", "31", "August", "สิงหาคม"], [], "English: midterm"),
    ("english", "How can I pay tuition fees?", ["QR", "credit", "บัตรเครดิต", "ธนาคาร", "bank"], [], "English: payment methods"),

    # ══════════════════════════════════════════════════════════════
    # CAT 10: Greeting / Casual (ทดสอบ Tier 1 Cache)
    # ══════════════════════════════════════════════════════════════
    ("greeting", "สวัสดีครับ", ["สวัสดี", "พี่เร็ก"], [], "ทักทาย ไทย"),
    ("greeting", "ขอบคุณครับ", ["ยินดี"], [], "ขอบคุณ"),
    ("greeting", "hi", ["Hi", "hello", "Hello", "Reg", "help"], [], "English greeting"),
    ("greeting", "คุณเป็นใคร", ["เร็ก", "ผู้ช่วย", "AI"], [], "ถามตัวตน"),

    # ══════════════════════════════════════════════════════════════
    # CAT 11: Edge Cases — คำถามที่คาดว่า bot อาจตอบผิด
    # ══════════════════════════════════════════════════════════════
    # 11a: คำถามที่ไม่มีในฐานข้อมูล → ควรปฏิเสธตอบ
    ("edge_no_data", "ค่าหอพักมหาวิทยาลัยเชียงใหม่เท่าไหร่", ["ไม่มีข้อมูล", "ไม่มีระบุ", "ไม่ทราบ", "ไม่มี"], [], "ไม่มีข้อมูลหอพัก"),
    ("edge_no_data", "เกรดเฉลี่ยขั้นต่ำสำหรับเกียรตินิยมคือเท่าไหร่", ["ไม่มีข้อมูล", "ไม่มีระบุ", "ไม่ทราบ", "ไม่มี"], [], "ไม่มีข้อมูลเกียรตินิยม"),
    ("edge_no_data", "ที่จอดรถมหาวิทยาลัยอยู่ตรงไหน", ["ไม่มีข้อมูล", "ไม่มีระบุ", "ไม่ทราบ", "ไม่มี"], [], "ไม่มีข้อมูลที่จอดรถ"),

    # 11b: คำถามปีที่ไม่มีข้อมูล
    ("edge_wrong_year", "เปิดเทอม 1/2567 วันไหน", ["ไม่มีข้อมูล", "ไม่มีระบุ", "ไม่ทราบ", "2568", "ไม่มี"], [], "ถามปี 2567 (ไม่มีในฐาน)"),

    # 11c: คำถามซับซ้อน (ถามหลายเรื่อง)
    ("edge_complex", "เปิดเทอม 1/2568 วันไหน แล้วชำระเงินได้เมื่อไหร่", ["23 มิถุนายน", "กรกฎาคม"], [], "ถามซ้อน 2 เรื่อง"),

    # 11d: คำถามคลุมเครือ
    ("edge_ambiguous", "เปิดเทอมเมื่อไหร่", ["มิถุนายน", "พฤศจิกายน", "เมษายน", "2568"], [], "ถามเปิดเทอมไม่ระบุภาค"),
    ("edge_ambiguous", "ถอนวิชาได้ถึงเมื่อไหร่", ["กรกฎาคม", "กันยายน", "กุมภาพันธ์", "เมษายน", "พฤษภาคม"], [], "ถามถอนไม่ระบุภาค"),

    # 11e: คำถามที่ใช้คำ synonym / ภาษาพูด
    ("edge_synonym", "ดรอปวิชาคืออะไร", ["ถอน", "กระบวนวิชา", "W"], [], "ดรอป synonym"),
    ("edge_synonym", "จ่ายตังค่าเทอมยังไง", ["QR", "บัตรเครดิต", "ธนาคาร", "เงินสด", "ชำระ"], [], "จ่ายตัง ภาษาพูด"),
    ("edge_synonym", "เมื่อไหร่เริ่มเรียน", ["มิถุนายน", "พฤศจิกายน", "เมษายน", "23", "17", "20"], [], "เริ่มเรียน synonym"),

    # 11f: Adversarial — ถามให้เดา/สมมุติ
    ("edge_adversarial", "คิดว่าเทอม 1 ปีหน้าจะเปิดวันไหน", ["ไม่มีข้อมูล", "ไม่มีระบุ", "ไม่ทราบ", "2568", "ไม่", "ยัง"], [], "ถามให้เดาอนาคต"),
    ("edge_adversarial", "ควรเรียนกี่วิชาต่อเทอม", ["ไม่มีข้อมูล", "ไม่มีระบุ", "ไม่ทราบ", "ไม่", "แนะนำ", "ขึ้นอยู่"], [], "ถามความเห็นส่วนตัว"),
]


FALLBACK_MARKERS = [
    "ขออภัย ระบบสรุปอัตโนมัติขัดข้องชั่วคราว",
    "ระบบขัดข้องชั่วคราว",
    "ขออภัยครับ ระบบขัดข้อง",
]


def _normalize_text(text):
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def run_single_test(category, question, must_contain, must_not_contain, description, session_id):
    form_data = {"text": question, "session_id": session_id}
    start_time = time.time()
    try:
        r = requests.post(
            f"{BASE_URL}/api/speech",
            data=form_data,
            headers={"X-API-Key": API_KEY},
            timeout=120,
        )
        elapsed = round(time.time() - start_time, 2)

        if r.status_code != 200:
            return {
                "pass": False, "reason": f"HTTP {r.status_code}",
                "reply": "", "time_s": elapsed,
                "is_retryable": True, "category": category,
                "question": question, "description": description,
            }

        data = r.json()
        reply = data.get("text", "")
        is_fallback = any(m in reply for m in FALLBACK_MARKERS)
        reply_norm = _normalize_text(reply)

        # Check must_contain (at least one keyword)
        found_any = not must_contain  # if empty list, auto-pass
        for kw in must_contain:
            if _normalize_text(kw) in reply_norm:
                found_any = True
                break

        # Check must_not_contain
        found_bad = [kw for kw in must_not_contain if _normalize_text(kw) in reply_norm]

        if not found_any:
            return {
                "pass": False, "reason": f"Missing: {must_contain}",
                "reply": reply, "time_s": elapsed,
                "is_retryable": is_fallback, "category": category,
                "question": question, "description": description,
            }
        if found_bad:
            return {
                "pass": False, "reason": f"Forbidden: {found_bad}",
                "reply": reply, "time_s": elapsed,
                "is_retryable": False, "category": category,
                "question": question, "description": description,
            }

        return {
            "pass": True, "reason": "OK",
            "reply": reply, "time_s": elapsed,
            "is_retryable": False, "category": category,
            "question": question, "description": description,
        }

    except requests.exceptions.Timeout:
        return {
            "pass": False, "reason": "Timeout (120s)",
            "reply": "", "time_s": 120.0,
            "is_retryable": True, "category": category,
            "question": question, "description": description,
        }
    except Exception as e:
        return {
            "pass": False, "reason": str(e),
            "reply": "", "time_s": 0,
            "is_retryable": True, "category": category,
            "question": question, "description": description,
        }


def main():
    print("=" * 72)
    print("  REG-01 Comprehensive Accuracy & Speed Test")
    print(f"  {len(TEST_CASES)} questions across {len(set(c[0] for c in TEST_CASES))} categories")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    # Check server
    try:
        requests.get(f"{BASE_URL}/", timeout=3)
    except Exception:
        print("ERROR: Server not running at", BASE_URL)
        sys.exit(1)

    all_results = []
    retryable_indices = []

    for i, (cat, question, must_contain, must_not, desc) in enumerate(TEST_CASES):
        session_id = f"{SESSION_PREFIX}{i:03d}"
        result = run_single_test(cat, question, must_contain, must_not, desc, session_id)
        all_results.append(result)

        status = "PASS" if result["pass"] else "FAIL"
        emoji = "✓" if result["pass"] else "✗"
        print(f"  [{status}] #{i+1:2d} ({result['time_s']:5.1f}s) {desc}")

        if not result["pass"]:
            print(f"         Reason: {result['reason']}")
            if result["reply"]:
                clean = result["reply"].replace("[Bot พี่เร็ก] ", "")[:120]
                print(f"         Reply:  {clean}")
            if result["is_retryable"]:
                retryable_indices.append(i)
                print(f"         → Will retry")

        # Small delay between requests
        time.sleep(8)

    # ── Retry phase ──
    if retryable_indices:
        print(f"\n  ── Retry phase: {len(retryable_indices)} questions ──")
        print(f"  Cooling down 45s...")
        time.sleep(45)

        for idx in retryable_indices:
            cat, question, must_contain, must_not, desc = TEST_CASES[idx]
            session_id = f"{SESSION_PREFIX}retry_{idx:03d}"
            result = run_single_test(cat, question, must_contain, must_not, desc, session_id)

            if result["pass"]:
                all_results[idx] = result
                print(f"  [PASS] #{idx+1:2d} ({result['time_s']:5.1f}s) {desc} (retry)")
            else:
                all_results[idx] = result
                print(f"  [FAIL] #{idx+1:2d} ({result['time_s']:5.1f}s) {desc} (retry)")
                if result["reply"]:
                    clean = result["reply"].replace("[Bot พี่เร็ก] ", "")[:120]
                    print(f"         Reply: {clean}")

            time.sleep(10)

    # ── Analysis ──
    passed = sum(1 for r in all_results if r["pass"])
    failed = len(all_results) - passed
    total = len(all_results)

    # Timing (exclude retryable failures from avg)
    valid_times = [r["time_s"] for r in all_results if r["pass"] or not r["is_retryable"]]
    avg_time = sum(valid_times) / len(valid_times) if valid_times else 0
    min_time = min(valid_times) if valid_times else 0
    max_time = max(valid_times) if valid_times else 0
    pass_times = [r["time_s"] for r in all_results if r["pass"]]
    avg_pass_time = sum(pass_times) / len(pass_times) if pass_times else 0

    # Per-category stats
    categories = {}
    for r in all_results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0, "times": []}
        categories[cat]["total"] += 1
        if r["pass"]:
            categories[cat]["passed"] += 1
            categories[cat]["times"].append(r["time_s"])

    # Failures detail
    failures = [r for r in all_results if not r["pass"]]

    print()
    print("=" * 72)
    print(f"  RESULTS: {passed}/{total} passed ({100*passed/total:.1f}%)")
    print(f"  Failed:  {failed}")
    print(f"  Avg response time (passed): {avg_pass_time:.2f}s")
    print(f"  Min/Max time: {min_time:.2f}s / {max_time:.2f}s")
    print("=" * 72)

    print()
    print("  PER-CATEGORY BREAKDOWN:")
    print("  " + "-" * 60)
    cat_names = {
        "cal_sem1": "ปฏิทิน เทอม 1/2568",
        "cal_sem2": "ปฏิทิน เทอม 2/2568",
        "cal_summer": "ปฏิทิน ภาคฤดูร้อน",
        "withdraw": "การถอนวิชา",
        "payment": "การชำระเงิน",
        "new_student": "นักศึกษาใหม่",
        "graduate": "บัณฑิตศึกษา",
        "misc": "กำหนดการอื่นๆ",
        "english": "คำถามภาษาอังกฤษ",
        "greeting": "ทักทาย/Greeting",
        "edge_no_data": "Edge: ไม่มีข้อมูล",
        "edge_wrong_year": "Edge: ปีที่ไม่มี",
        "edge_complex": "Edge: คำถามซับซ้อน",
        "edge_ambiguous": "Edge: คลุมเครือ",
        "edge_synonym": "Edge: คำ synonym",
        "edge_adversarial": "Edge: Adversarial",
    }
    for cat, stats in sorted(categories.items()):
        name = cat_names.get(cat, cat)
        pct = 100 * stats["passed"] / stats["total"] if stats["total"] > 0 else 0
        avg_t = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
        print(f"  {name:30s} {stats['passed']:2d}/{stats['total']:2d} ({pct:5.1f}%)  avg {avg_t:.1f}s")

    if failures:
        print()
        print("  FAILURES DETAIL:")
        print("  " + "-" * 60)
        for r in failures:
            print(f"  [{r['category']}] {r['description']}")
            print(f"    Q: {r['question']}")
            print(f"    Reason: {r['reason']}")
            if r["reply"]:
                clean = r["reply"].replace("[Bot พี่เร็ก] ", "")[:250]
                print(f"    Reply: {clean}")
            print()

    # Save results JSON
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "accuracy_pct": round(100 * passed / total, 1),
        "avg_response_time_s": round(avg_pass_time, 2),
        "min_time_s": round(min_time, 2),
        "max_time_s": round(max_time, 2),
        "categories": {
            cat: {
                "name": cat_names.get(cat, cat),
                "passed": stats["passed"],
                "total": stats["total"],
                "accuracy_pct": round(100 * stats["passed"] / stats["total"], 1) if stats["total"] > 0 else 0,
                "avg_time_s": round(sum(stats["times"]) / len(stats["times"]), 2) if stats["times"] else 0,
            }
            for cat, stats in sorted(categories.items())
        },
        "failures": [
            {
                "category": r["category"],
                "description": r["description"],
                "question": r["question"],
                "reason": r["reason"],
                "reply": r["reply"][:300] if r["reply"] else "",
            }
            for r in failures
        ],
        "all_results": [
            {
                "idx": i + 1,
                "category": r["category"],
                "description": r["description"],
                "question": r["question"],
                "pass": r["pass"],
                "time_s": r["time_s"],
                "reason": r["reason"],
                "reply": r["reply"][:200] if r["reply"] else "",
            }
            for i, r in enumerate(all_results)
        ],
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n  Results saved to: {RESULTS_FILE}")

    return failed


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
