"""Debug: call API for CMU-eGrad and check context chunks."""
import requests
import json

r = requests.post(
    "http://localhost:5000/api/speech",
    data={"text": "สอบ CMU-eGrad ปี 2568 วันไหน", "session_id": "debug_egrad_check"},
    headers={"X-API-Key": "dev-token-accuracy-test"},
    timeout=120,
)
d = r.json()
print("Reply:", d.get("text", ""))
print()

# Check debug info
debug = d.get("debug", {})
rag = debug.get("rag", {})
chunks = rag.get("retrieved", [])
print(f"Retrieved chunks: {len(chunks)}")
for c in chunks:
    preview = c.get("chunk_preview", "")
    has_egrad = "CMU-eGrad" in preview or "eGrad" in preview
    print(f"  [{c.get('rank')}] score={c.get('score')} eGrad_in_preview={has_egrad}")
    print(f"       {preview[:200]}")
    print()

# Check if CMU-eGrad is anywhere in the full response debug
full_debug_str = json.dumps(debug, ensure_ascii=False)
if "CMU-eGrad" in full_debug_str:
    print("CMU-eGrad FOUND in debug output")
else:
    print("CMU-eGrad NOT FOUND in debug output")
