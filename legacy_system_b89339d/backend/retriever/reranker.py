"""
Cross-Encoder Reranker
แทนที่ LLM-based reranking ด้วย cross-encoder model ที่ทำงาน local
ไม่ต้องใช้ API call — ประหยัด token และเร็วกว่า LLM reranking มาก

Model: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
- Multilingual (รองรับภาษาไทย)
- ขนาดเล็ก (~135MB)
- แม่นยำกว่า bi-encoder สำหรับ reranking
"""
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger("Reranker")

_cross_encoder = None
_CROSS_ENCODER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


def _get_cross_encoder():
    """Lazy load cross-encoder model"""
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading cross-encoder model: {_CROSS_ENCODER_MODEL}")
            _cross_encoder = CrossEncoder(_CROSS_ENCODER_MODEL, max_length=512)
            logger.info("Cross-encoder model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder: {e}")
            _cross_encoder = None
    return _cross_encoder


def rerank_chunks(
    query: str,
    chunks: List[Tuple[Dict, float]],
    top_k: int = 5,
    min_score: float = -10.0,
) -> List[Tuple[Dict, float]]:
    """
    Rerank chunks ด้วย cross-encoder model (local, ไม่ต้องใช้ API)

    Args:
        query: คำถามจากผู้ใช้
        chunks: List of (chunk_dict, original_score) tuples
        top_k: จำนวนผลลัพธ์ที่ต้องการ
        min_score: คะแนนต่ำสุดที่จะรวม

    Returns:
        Reranked list of (chunk_dict, new_score) tuples
    """
    if not chunks:
        return []

    if len(chunks) <= 1:
        return chunks[:top_k]

    encoder = _get_cross_encoder()
    if encoder is None:
        logger.warning("Cross-encoder not available, using original ranking")
        return chunks[:top_k]

    try:
        # จำกัดจำนวน chunks ที่ส่งให้ cross-encoder (ประหยัดเวลา)
        candidates = chunks[:min(20, len(chunks))]

        # สร้าง query-document pairs สำหรับ cross-encoder
        pairs = [
            (query, chunk_dict.get("chunk", "")[:1000])
            for chunk_dict, _ in candidates
        ]

        # Cross-encoder scoring (local, ไม่มี API cost)
        scores = encoder.predict(pairs, show_progress_bar=False)

        # สร้าง reranked results
        reranked = []
        for idx, score in enumerate(scores):
            score_float = float(score)
            if score_float >= min_score:
                chunk_dict = candidates[idx][0]
                reranked.append((chunk_dict, score_float))

        # Sort by cross-encoder score (descending)
        reranked.sort(key=lambda x: x[1], reverse=True)

        if reranked:
            logger.info(
                "Cross-encoder reranked: %d chunks, top score: %.3f, bottom score: %.3f",
                len(reranked),
                reranked[0][1],
                reranked[-1][1],
            )

        return reranked[:top_k]

    except Exception as e:
        logger.error(f"Cross-encoder reranking failed: {e}")
        return chunks[:top_k]


def is_reranker_available() -> bool:
    """ตรวจสอบว่า cross-encoder model พร้อมใช้งานหรือไม่"""
    return _get_cross_encoder() is not None
