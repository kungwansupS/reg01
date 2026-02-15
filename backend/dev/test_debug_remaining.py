"""Debug remaining test failures #4, #10."""
import sys, os, unicodedata
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from retriever.context_selector import retrieve_top_k_chunks
from retriever.intent_analyzer import analyze_intent

# --- Debug #10: CMU-eGrad ---
print("=" * 60)
print("DEBUG #10: CMU-eGrad")
q = "สอบ CMU-eGrad ปี 2568 วันไหน"
intent = analyze_intent(q)
print(f"Intent: {intent}")
print(f"Semester inferred: {intent.get('semester')} (should be None for entity queries)")
print(f"Entities: {intent.get('key_entities')}")

chunks = retrieve_top_k_chunks(q, k=5, use_hybrid=True, use_rerank=True, use_intent_analysis=True)
print(f"\nRetrieved {len(chunks)} chunks:")
found_egrad = False
for i, (chunk, score) in enumerate(chunks):
    text = chunk.get("chunk", "")
    has_egrad = "CMU-eGrad" in text
    if has_egrad:
        found_egrad = True
    preview = text[:250].replace("\n", " ")
    print(f"  [{i+1}] score={score:.3f} eGrad={has_egrad} | {preview}")

if not found_egrad:
    print("\n  *** CMU-eGrad NOT in any retrieved chunk! ***")
    print("  Trying without filters...")
    chunks2 = retrieve_top_k_chunks(q, k=5, use_hybrid=True, use_rerank=True, use_intent_analysis=False)
    for i, (chunk, score) in enumerate(chunks2):
        text = chunk.get("chunk", "")
        has_egrad = "CMU-eGrad" in text
        preview = text[:250].replace("\n", " ")
        print(f"  [{i+1}] score={score:.3f} eGrad={has_egrad} | {preview}")

# --- Debug #4: Unicode normalization ---
print("\n" + "=" * 60)
print("DEBUG #4: Unicode 'กันยายน' matching")
kw = "19 กันยายน"
reply_text = "ทำได้จนถึงศุกร์ที่ 19 กันยายน 2568"
print(f"Keyword bytes: {kw.encode('utf-8').hex()}")

# Search for keyword in reply
nfc_kw = unicodedata.normalize('NFC', kw)
nfc_reply = unicodedata.normalize('NFC', reply_text)
print(f"NFC match: {nfc_kw in nfc_reply}")

nfkc_kw = unicodedata.normalize('NFKC', kw)
nfkc_reply = unicodedata.normalize('NFKC', reply_text)
print(f"NFKC match: {nfkc_kw in nfkc_reply}")

# Check Sara Am character
for c in "กันยายน":
    print(f"  char '{c}' U+{ord(c):04X} name={unicodedata.name(c, '?')}")
