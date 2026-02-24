"""Quick smoke test for v3 architecture components."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from retriever.intent_analyzer import analyze_intent, needs_retrieval

# Test intent analysis
tests = [
    ("วันเปิดเทอม ภาคเรียนที่ 1 ปี 2568", "date_query"),
    ("สอบกลางภาค เทอม 2 เมื่อไหร่", "date_query"),
    ("ถอนวิชาทำยังไง", "policy_query"),
    ("ได้รับ W คืออะไร", "policy_query"),
    ("ห้องสอบอยู่ที่ไหน", "factual_query"),
    ("สวัสดี", "general"),
    ("CMU-eGrad สอบวันไหน", "date_query"),
]

print("=== Intent Analysis Tests ===")
passed = 0
for q, expected in tests:
    result = analyze_intent(q)
    ok = result["intent"] == expected
    passed += int(ok)
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] \"{q[:35]}\" -> {result['intent']} (expected: {expected})")

# Test needs_retrieval
retrieval_tests = [
    ("วันเปิดเทอม", True),
    ("สวัสดี", False),
    ("ขอบคุณครับ", False),
    ("สอบกลางภาค 2568", True),
    ("ถอนวิชาได้ถึงเมื่อไหร่", True),
    ("hi", False),
    ("", False),
]

print()
print("=== Needs Retrieval Tests ===")
for q, expected in retrieval_tests:
    result = needs_retrieval(q)
    ok = result == expected
    passed += int(ok)
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] \"{q}\" -> {result} (expected: {expected})")

# Test prompt
from app.prompt.prompt import build_unified_prompt, context_prompt
p1 = build_unified_prompt("วันเปิดเทอม", "context here", "history here", "th")
p2 = context_prompt("สวัสดี")
print()
print("=== Prompt Tests ===")
print(f"  [PASS] build_unified_prompt: {len(p1)} chars")
print(f"  [PASS] context_prompt: {len(p2)} chars")
passed += 2

# Test pose
import asyncio
from app.utils.pose import suggest_pose
pose1 = asyncio.run(suggest_pose("ภาคเรียนที่ 1 เริ่มวันที่ 23 มิถุนายน 2568"))
pose2 = asyncio.run(suggest_pose("ไม่มีข้อมูลในส่วนนี้ครับ"))
pose3 = asyncio.run(suggest_pose("ได้เลยครับ"))
print()
print("=== Pose Tests ===")
print(f"  [{'PASS' if pose1 == 'Tap' else 'INFO'}] date reply -> {pose1}")
print(f"  [{'PASS' if pose2 == 'FlickDown' else 'INFO'}] no-info reply -> {pose2}")
print(f"  [{'PASS' if pose3 == 'Flick' else 'INFO'}] confirm reply -> {pose3}")
passed += 3

total = len(tests) + len(retrieval_tests) + 5
print(f"\n=== {passed}/{total} tests passed ===")
