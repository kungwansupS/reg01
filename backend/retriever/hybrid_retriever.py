import logging
from rank_bm25 import BM25Okapi
from collections import defaultdict
from typing import List, Dict, Tuple

logger = logging.getLogger("HybridRetriever")

class HybridRetriever:
    """
    Hybrid Search combining Dense (Semantic) + Sparse (BM25) with RRF fusion
    """
    def __init__(self):
        self.bm25_index = None
        self.documents = []
        self.corpus_tokens = []
        
    def build_index(self, chunks: List[Dict]):
        """
        Build BM25 index from document chunks
        
        Args:
            chunks: List of dicts with 'chunk', 'source', 'index' keys
        """
        if not chunks:
            logger.warning("⚠️ No chunks provided for BM25 indexing")
            return
        
        # Tokenize documents
        self.documents = chunks
        self.corpus_tokens = [
            self._tokenize(chunk['chunk']) 
            for chunk in chunks
        ]
        
        # Build BM25 index
        self.bm25_index = BM25Okapi(self.corpus_tokens)
        logger.info(f"✅ BM25 index built with {len(chunks)} documents")
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization - split by whitespace"""
        return text.lower().split()
    
    def bm25_search(self, query: str, k: int = 10) -> List[Tuple[Dict, float]]:
        """
        BM25 keyword search
        
        Returns:
            List of (document, score) tuples
        """
        if not self.bm25_index:
            logger.warning("⚠️ BM25 index not built yet")
            return []
        
        query_tokens = self._tokenize(query)
        scores = self.bm25_index.get_scores(query_tokens)
        
        # Get top k results
        top_indices = sorted(
            range(len(scores)), 
            key=lambda i: scores[i], 
            reverse=True
        )[:k]
        
        results = [
            (self.documents[i], float(scores[i]))
            for i in top_indices
            if scores[i] > 0
        ]
        
        return results
    
    def rrf_fusion(
        self, 
        dense_results: List[Dict], 
        sparse_results: List[Tuple[Dict, float]], 
        k: int = 5,
        rrf_k: int = 60
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion algorithm
        
        Args:
            dense_results: Results from vector search
            sparse_results: Results from BM25 search
            k: Number of results to return
            rrf_k: RRF constant (default 60)
        
        Returns:
            Fused and ranked results
        """
        scores = defaultdict(float)
        doc_map = {}
        
        # Score dense results
        for rank, item in enumerate(dense_results):
            doc_id = f"{item.get('source', '')}_{item.get('chunk', '')[:50]}"
            scores[doc_id] += 1.0 / (rrf_k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = item
        
        # Score sparse results
        for rank, (doc, _) in enumerate(sparse_results):
            doc_id = f"{doc.get('source', '')}_{doc.get('chunk', '')[:50]}"
            scores[doc_id] += 1.0 / (rrf_k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc
        
        # Sort by fused score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Return top k with scores
        results = []
        for doc_id, score in ranked[:k]:
            if doc_id in doc_map:
                result = doc_map[doc_id].copy()
                result['rrf_score'] = score
                results.append(result)
        
        logger.info(f"🔀 RRF fusion: {len(dense_results)} dense + {len(sparse_results)} sparse → {len(results)} results")
        return results

# Global singleton instance
hybrid_retriever = HybridRetriever()
