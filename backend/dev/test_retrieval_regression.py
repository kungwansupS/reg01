"""Regression checks for known retrieval failure patterns."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from retriever.context_selector import retrieve_top_k_chunks


CASES = [
    "เปิดเทอม 2/2568 วันไหน",
    "ถอนวิชาโดยได้รับ W เทอม 2/2568",
    "ชำระค่าเทอมด้วย QR Code ได้ถึงกี่โมง",
    "สอบ CMU-eGrad ปี 2568 วันไหน",
]


def test_retrieval_regression_non_empty():
    for query in CASES:
        chunks = retrieve_top_k_chunks(
            query,
            k=3,
            use_hybrid=True,
            use_rerank=False,
            use_intent_analysis=True,
        )
        assert isinstance(chunks, list)
        assert len(chunks) > 0, f"retrieval empty for query: {query}"


def main() -> int:
    try:
        test_retrieval_regression_non_empty()
        print(f"retrieval_regression PASS ({len(CASES)} cases)")
        return 0
    except AssertionError as exc:
        print(f"retrieval_regression FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
