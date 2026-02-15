"""Diagnose retrieval issues for failing test cases."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from retriever.context_selector import retrieve_top_k_chunks
from retriever.intent_analyzer import analyze_intent

FAILING_QUERIES = [
    "ถอนวิชาโดยได้รับ W ภาค 1/2568 ได้ถึงเมื่อไหร่",
    "ถอนวิชาโดยไม่ได้รับ W ภาค 1/2568 ได้ถึงเมื่อไหร่",
    "ปิดเทอม 1/2568 วันไหน",
    "เปิดเทอม 2/2568 วันไหน",
    "ถอนวิชาได้รับ W เทอม 2/2568",
    "เปิดเทอม ภาคฤดูร้อน 2568 วันไหน",
    "ถอนวิชาไม่ได้รับ W ภาคฤดูร้อน 2568",
    "ชำระค่าเทอมด้วย QR Code ได้ถึงกี่โมง",
    "จ่ายค่าเทอมด้วยบัตรเครดิตที่กองคลัง ได้ถึงกี่โมง",
    "ชำระค่าเทอมด้วยเงินสดได้ที่ไหน",
]

for q in FAILING_QUERIES:
    print(f"\n{'='*60}")
    print(f"Q: {q}")
    intent = analyze_intent(q)
    print(f"Intent: {intent['intent']} | Year: {intent.get('academic_year')} | Sem: {intent.get('semester')} | Doc: {intent.get('doc_type')}")
    
    chunks = retrieve_top_k_chunks(q, k=3, use_hybrid=True, use_rerank=True, use_intent_analysis=True)
    if not chunks:
        print("  NO CHUNKS FOUND!")
    else:
        for i, (chunk, score) in enumerate(chunks):
            text = chunk.get("chunk", "")[:200].replace("\n", " ")
            print(f"  [{i+1}] score={score:.3f} | {text}")
    
    # Also check if the answer keyword exists in ANY chunk
    answer_keywords = {
        "ถอนวิชาโดยได้รับ W ภาค 1/2568": "7 กรกฎาคม",
        "ถอนวิชาโดยไม่ได้รับ W ภาค 1/2568": "21 มิถุนายน",
        "ปิดเทอม 1/2568": "4 พฤศจิกายน",
        "เปิดเทอม 2/2568": "17 พฤศจิกายน",
        "ถอนวิชาได้รับ W เทอม 2/2568": "1 ธันวาคม",
        "เปิดเทอม ภาคฤดูร้อน 2568": "20 เมษายน",
        "ถอนวิชาไม่ได้รับ W ภาคฤดูร้อน 2568": "13",
        "ชำระค่าเทอมด้วย QR Code": "23.00",
        "จ่ายค่าเทอมด้วยบัตรเครดิตที่กองคลัง": "16.30",
        "ชำระค่าเทอมด้วยเงินสดได้ที่ไหน": "ธนาคาร",
    }
    
    for key_prefix, keyword in answer_keywords.items():
        if q.startswith(key_prefix):
            found_in_chunk = any(keyword in c.get("chunk", "") for c, _ in chunks)
            if found_in_chunk:
                print(f"  ✅ Answer keyword '{keyword}' FOUND in retrieved chunks")
            else:
                print(f"  ❌ Answer keyword '{keyword}' NOT in retrieved chunks")
            break
