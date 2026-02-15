"""
Focused test: only the 3 questions that consistently fail due to Groq rate limits.
Run this SEPARATELY (not after the full test suite) so the quota is fresh.
"""
import requests
import re
import time
import sys
import unicodedata

BASE_URL = "http://localhost:5000"
API_KEY = "dev-token-accuracy-test"

FALLBACK_MARKERS = ["ขออภัย ระบบสรุปอัตโนมัติขัดข้องชั่วคราว", "ระบบขัดข้องชั่วคราว"]

def _normalize_text(text: str) -> str:
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'\s+', ' ', text)
    return text

TEST_CASES = [
    (
        "สอบ CMU-eGrad ปี 2568 วันไหน",
        ["กันยายน", "CMU-eGrad"],
        [],
        "CMU-eGrad = 13-14 และ 20-21 ก.ย. 68"
    ),
    (
        "ปิดเทอม 1/2568 วันไหน",
        ["4 พฤศจิกายน", "พฤศจิกายน"],
        [],
        "ปิดเทอม 1/2568 = 4 พ.ย. 68"
    ),
    (
        "เปิดเทอม 2/2568 วันไหน",
        ["17 พฤศจิกายน", "17 พ.ย."],
        [],
        "เปิดเทอม 2/2568 = 17 พ.ย. 68"
    ),
]

def run_test(question, must_contain, must_not_contain, description, session_id):
    form_data = {"text": question, "session_id": session_id}
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
        is_fallback = any(m in reply for m in FALLBACK_MARKERS)
        reply_norm = _normalize_text(reply)

        found_any = False
        for keyword in must_contain:
            kw_norm = _normalize_text(keyword)
            if kw_norm in reply_norm:
                found_any = True
                break

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
    print("=" * 60)
    print("  Focused test: 3 remaining questions")
    print("=" * 60)

    try:
        requests.get(f"{BASE_URL}/", timeout=3)
    except Exception:
        print("ERROR: Server not running at", BASE_URL)
        sys.exit(1)

    passed = 0
    failed = 0

    for i, (question, must_contain, must_not_contain, desc) in enumerate(TEST_CASES):
        session_id = f"focused_test_{i:03d}"
        ok, reason, reply, is_fallback = run_test(question, must_contain, must_not_contain, desc, session_id)

        if ok:
            passed += 1
            print(f"  [PASS] {desc}")
        else:
            failed += 1
            print(f"  [FAIL] {desc}")
            print(f"         Reason: {reason}")
            if is_fallback:
                print(f"         (Rate limit fallback)")
            if reply:
                clean = reply.replace("[Bot พี่เร็ก] ", "")[:250]
                print(f"         Reply: {clean}")

        # 30s delay between questions
        if i < len(TEST_CASES) - 1:
            time.sleep(30)

    print()
    print("=" * 60)
    print(f"  Results: {passed}/{len(TEST_CASES)} passed")
    print("=" * 60)
    return failed


if __name__ == "__main__":
    sys.exit(main())
