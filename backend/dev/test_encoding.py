"""Debug Unicode encoding issue for test #12."""
import requests
import unicodedata

r = requests.post(
    "http://localhost:5000/api/speech",
    data={"text": "เปิดเทอม 2/2568 วันไหน", "session_id": "enc_test_001"},
    headers={"X-API-Key": "dev-token-test"},
    timeout=30,
)
reply = r.json().get("text", "")
print(f"Raw reply repr: {repr(reply[:200])}")
print(f"NFC reply repr: {repr(unicodedata.normalize('NFC', reply[:200]))}")

kw = "17 พฤศจิกายน"
print(f"\nKeyword repr: {repr(kw)}")
print(f"NFC keyword:  {repr(unicodedata.normalize('NFC', kw))}")

# Check char-by-char around the target area
idx = reply.find("17")
if idx >= 0:
    segment = reply[idx:idx+30]
    print(f"\nSegment around '17': {repr(segment)}")
    print(f"NFC segment:        {repr(unicodedata.normalize('NFC', segment))}")
    
    # Compare each char
    nfc_seg = unicodedata.normalize('NFC', segment)
    nfc_kw = unicodedata.normalize('NFC', kw)
    print(f"\nNFC keyword in NFC segment: {nfc_kw in nfc_seg}")
    
    # NFKC
    nfkc_seg = unicodedata.normalize('NFKC', segment)
    nfkc_kw = unicodedata.normalize('NFKC', kw)
    print(f"NFKC keyword in NFKC segment: {nfkc_kw in nfkc_seg}")
else:
    print("\n'17' not found in reply!")
    print(f"Full reply: {repr(reply)}")
