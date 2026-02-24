"""
Comprehensive accuracy test against PDF source documents.
Tests the full ask_llm pipeline end-to-end via HTTP API.

Ground truth extracted from:
  1. CMU-Academic-Calendar-2568.pdf
  2. REG_payment.pdf
"""
import requests
import json
import re
import time
import sys
import unicodedata

BASE_URL = "http://localhost:5000"
API_KEY = "dev-token-accuracy-test"
SESSION_PREFIX = "accuracy_test_"

# ─── Ground Truth Test Cases ───────────────────────────────────────
# Format: (question, must_contain_keywords, must_not_contain, description)
# must_contain: at least ONE of these must appear in the reply
# must_not_contain: NONE of these should appear

TEST_CASES = [
    # ══════════════════════════════════════════════════════════════
    # ภาคการศึกษาที่ 1/2568
    # ══════════════════════════════════════════════════════════════
    (
        "วันเปิดเทอม ภาคเรียนที่ 1 ปี 2568",
        ["23 มิถุนายน 2568"],
        [],
        "เปิดเทอม 1/2568 = 23 มิ.ย. 68"
    ),
    (
        "สอบกลางภาค เทอม 1/2568 วันไหน",
        ["25", "31", "สิงหาคม"],
        [],
        "สอบกลางภาค 1/2568 = 25-31 ส.ค. 68"
    ),
    (
        "วันสอบไล่ ภาคเรียนที่ 1/2568",
        ["20", "ตุลาคม", "3 พฤศจิกายน"],
        [],
        "สอบไล่ 1/2568 = 20 ต.ค. - 3 พ.ย. 68"
    ),
    (
        "ถอนวิชาโดยได้รับ W ภาค 1/2568 ได้ถึงเมื่อไหร่",
        ["7 กรกฎาคม", "19 กันยายน"],
        [],
        "ถอน W 1/2568 = 7 ก.ค. - 19 ก.ย. 68"
    ),
    (
        "ถอนวิชาโดยไม่ได้รับ W ภาค 1/2568 ได้ถึงเมื่อไหร่",
        ["มิถุนายน", "กรกฎาคม"],
        [],
        "ถอน ไม่ได้ W 1/2568 = 21 มิ.ย. - 4 ก.ค. 68"
    ),
    (
        "ชำระเงินค่าธรรมเนียม ภาค 1/2568 วันไหน",
        ["7", "11", "กรกฎาคม"],
        [],
        "ชำระเงิน 1/2568 = 7-11 ก.ค. 68"
    ),
    (
        "วันปฐมนิเทศ นักศึกษาใหม่ปริญญาตรี ปี 2568",
        ["18 มิถุนายน"],
        [],
        "ปฐมนิเทศ ป.ตรี = 18 มิ.ย. 68"
    ),
    (
        "รายงานตัวขึ้นทะเบียน นักศึกษาใหม่ปริญญาตรี รหัส 68",
        ["10", "13", "มิถุนายน"],
        [],
        "รายงานตัว ป.ตรี 68 = 10-13 มิ.ย. 68"
    ),
    (
        "สอบ CMU-ePro ปี 2568 วันไหน",
        ["13", "17", "มิถุนายน"],
        [],
        "CMU-ePro = 13-17 มิ.ย. 68"
    ),
    (
        "สอบ CMU-eGrad ปี 2568 วันไหน",
        ["กันยายน", "CMU-eGrad"],
        [],
        "CMU-eGrad = 13-14 และ 20-21 ก.ย. 68"
    ),
    (
        "ปิดเทอม 1/2568 วันไหน",
        ["4 พฤศจิกายน"],
        [],
        "ปิดเทอม 1/2568 = 4 พ.ย. 68"
    ),

    # ══════════════════════════════════════════════════════════════
    # ภาคการศึกษาที่ 2/2568
    # ══════════════════════════════════════════════════════════════
    (
        "เปิดเทอม 2/2568 วันไหน",
        ["17 พฤศจิกายน", "17 พ.ย."],
        [],
        "เปิดเทอม 2/2568 = 17 พ.ย. 68"
    ),
    (
        "สอบกลางภาค เทอม 2/2568",
        ["19", "25", "มกราคม 2569"],
        [],
        "สอบกลางภาค 2/2568 = 19-25 ม.ค. 69"
    ),
    (
        "สอบไล่ เทอม 2/2568 วันไหน",
        ["16", "29", "มีนาคม 2569"],
        [],
        "สอบไล่ 2/2568 = 16-29 มี.ค. 69"
    ),
    (
        "ถอนวิชาได้รับ W เทอม 2/2568",
        ["1 ธันวาคม", "13 กุมภาพันธ์"],
        [],
        "ถอน W 2/2568 = 1 ธ.ค. 68 - 13 ก.พ. 69"
    ),
    (
        "ชำระเงิน เทอม 2/2568",
        ["1", "5", "ธันวาคม"],
        [],
        "ชำระเงิน 2/2568 = 1-5 ธ.ค. 68"
    ),

    # ══════════════════════════════════════════════════════════════
    # ภาคฤดูร้อน/2568
    # ══════════════════════════════════════════════════════════════
    (
        "เปิดเทอม ภาคฤดูร้อน 2568 วันไหน",
        ["20 เมษายน 2569"],
        [],
        "เปิดเทอมฤดูร้อน = 20 เม.ย. 69"
    ),
    (
        "ถอนวิชาไม่ได้รับ W ภาคฤดูร้อน 2568",
        ["13", "24", "เมษายน 2569"],
        [],
        "ถอน ไม่ได้ W ฤดูร้อน = 13-24 เม.ย. 69"
    ),

    # ══════════════════════════════════════════════════════════════
    # การชำระเงิน (REG_payment.pdf)
    # ══════════════════════════════════════════════════════════════
    (
        "ชำระค่าเทอมด้วย QR Code ได้ถึงกี่โมง",
        ["23.00", "23:00"],
        [],
        "QR Code ถึง 23.00 น."
    ),
    (
        "จ่ายค่าเทอมด้วยบัตรเครดิตที่กองคลัง ได้ถึงกี่โมง",
        ["16.30", "16:30"],
        [],
        "บัตรเครดิต กองคลัง ถึง 16.30 น."
    ),
    (
        "ชำระค่าเทอมด้วยเงินสดได้ที่ไหน",
        ["ธนาคาร"],
        [],
        "เงินสด = เคาน์เตอร์ธนาคาร"
    ),
]


FALLBACK_MARKERS = ["ขออภัย ระบบสรุปอัตโนมัติขัดข้องชั่วคราว", "ระบบขัดข้องชั่วคราว"]


def _normalize_text(text: str) -> str:
    """NFC normalize + collapse whitespace for robust matching."""
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def run_test(question, must_contain, must_not_contain, description, session_id):
    """Run a single test case against the API."""
    form_data = {
        "text": question,
        "session_id": session_id,
    }
    try:
        r = requests.post(
            f"{BASE_URL}/api/speech",
            data=form_data,
            headers={"X-API-Key": API_KEY},
            timeout=120,
        )
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}", "", True

        data = r.json()
        reply = data.get("text", "")

        # Detect rate-limit fallback
        is_fallback = any(m in reply for m in FALLBACK_MARKERS)

        # Normalize Unicode + whitespace for Thai text comparison
        reply_norm = _normalize_text(reply)

        # Check must_contain (at least one keyword must be present)
        found_any = False
        for keyword in must_contain:
            kw_norm = _normalize_text(keyword)
            if kw_norm in reply_norm:
                found_any = True
                break

        # Check must_not_contain
        found_bad = []
        for keyword in must_not_contain:
            kw_norm = _normalize_text(keyword)
            if kw_norm in reply_norm:
                found_bad.append(keyword)

        if not found_any:
            return False, f"Missing keywords: {must_contain}", reply, is_fallback
        if found_bad:
            return False, f"Found forbidden: {found_bad}", reply, False

        return True, "OK", reply, False

    except Exception as e:
        return False, str(e), "", True


def main():
    print("=" * 70)
    print("  REG-01 v3 Accuracy Test")
    print(f"  Testing {len(TEST_CASES)} questions against ground truth")
    print("=" * 70)
    print()

    # Check server is running
    try:
        requests.get(f"{BASE_URL}/", timeout=3)
    except Exception:
        print("ERROR: Server not running at", BASE_URL)
        print("Please start the server first: python run.py")
        sys.exit(1)

    passed = 0
    failed = 0
    failures = []
    retryable = []  # (index, question, must_contain, must_not_contain, desc)

    for i, (question, must_contain, must_not_contain, desc) in enumerate(TEST_CASES):
        session_id = f"{SESSION_PREFIX}{i:03d}"
        ok, reason, reply, is_retryable = run_test(question, must_contain, must_not_contain, desc, session_id)

        if ok:
            passed += 1
            print(f"  [PASS] #{i+1:2d} {desc}")
        else:
            print(f"  [FAIL] #{i+1:2d} {desc}")
            print(f"         Reason: {reason}")
            if reply:
                clean = reply.replace("[Bot พี่เร็ก] ", "")[:150]
                print(f"         Reply:  {clean}")
            if is_retryable:
                retryable.append((i, question, must_contain, must_not_contain, desc))
                print(f"         → Will retry (rate limit / timeout)")
            else:
                failed += 1
                failures.append((i + 1, question, desc, reason, reply))

        # Delay between requests to avoid Groq free tier rate limiting
        time.sleep(30)

    # ── Retry phase: retry rate-limit/timeout failures ──────────────
    max_retry_rounds = 2
    for retry_round in range(max_retry_rounds):
        if not retryable:
            break
        print()
        print(f"  ── Retry round {retry_round + 1} ({len(retryable)} questions) ──")
        print(f"  Cooling down 60s before retries...")
        time.sleep(60)

        still_retryable = []
        for idx, question, must_contain, must_not_contain, desc in retryable:
            session_id = f"{SESSION_PREFIX}retry{retry_round}_{idx:03d}"
            ok, reason, reply, is_retryable = run_test(question, must_contain, must_not_contain, desc, session_id)

            if ok:
                passed += 1
                print(f"  [PASS] #{idx+1:2d} {desc} (retry {retry_round + 1})")
            else:
                print(f"  [FAIL] #{idx+1:2d} {desc} (retry {retry_round + 1})")
                print(f"         Reason: {reason}")
                if is_retryable and retry_round < max_retry_rounds - 1:
                    still_retryable.append((idx, question, must_contain, must_not_contain, desc))
                    print(f"         → Will retry again")
                else:
                    failed += 1
                    failures.append((idx + 1, question, desc, reason, reply))
            time.sleep(30)

        retryable = still_retryable

    # Count remaining retryable as failures
    for idx, question, must_contain, must_not_contain, desc in retryable:
        failed += 1
        failures.append((idx + 1, question, desc, "Rate limit exhausted after retries", ""))

    print()
    print("=" * 70)
    print(f"  Results: {passed}/{len(TEST_CASES)} passed ({100*passed/len(TEST_CASES):.0f}%)")
    if failures:
        print(f"  Failed:  {failed}")
    print("=" * 70)

    if failures:
        print()
        print("  FAILURES DETAIL:")
        print("-" * 70)
        for num, q, desc, reason, reply in failures:
            print(f"  #{num} [{desc}]")
            print(f"    Q: {q}")
            print(f"    Reason: {reason}")
            if reply:
                clean = reply.replace("[Bot พี่เร็ก] ", "")
                print(f"    Reply: {clean[:300]}")
            print()

    return len(failures)


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
