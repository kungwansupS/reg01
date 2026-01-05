import logging
import re
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
        """Thai-aware tokenization"""
        try:
            from pythainlp.tokenize import word_tokenize
            tokens = word_tokenize(text.lower(), engine='newmm')
            # Filter out very short tokens and special chars
            tokens = [t for t in tokens if len(t) > 1 and not t.isspace()]
            return tokens
        except:
            # Fallback: improved split
            text = text.lower()
            # Keep Thai chars, English, numbers together
            tokens = re.findall(r'[ก-๙a-z0-9]+', text)
            return [t for t in tokens if len(t) > 1]
    
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
        rrf_k: int = 60,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3
    ) -> List[Dict]:
        """
        Improved RRF with score normalization and weighting
        
        Args:
            dense_results: Results from vector search
            sparse_results: Results from BM25 search
            k: Number of results to return
            rrf_k: RRF constant (default 60)
            dense_weight: Weight for semantic search (0-1)
            sparse_weight: Weight for keyword search (0-1)
        
        Returns:
            Fused and ranked results
        """
        from collections import defaultdict
        import math
        
        scores = defaultdict(lambda: {'rrf': 0, 'dense': 0, 'sparse': 0})
        doc_map = {}
        
        # Normalize dense scores (0-1)
        if dense_results:
            max_dense = max([r.get('score', 0) for r in dense_results], default=1)
            min_dense = min([r.get('score', 0) for r in dense_results], default=0)
            dense_range = max_dense - min_dense or 1
        
        # Score dense results with normalization
        for rank, item in enumerate(dense_results):
            doc_id = self._get_doc_id(item)
            
            # RRF score
            rrf_score = 1.0 / (rrf_k + rank + 1)
            
            # Normalized semantic score
            raw_score = item.get('score', 0)
            norm_score = (raw_score - min_dense) / dense_range if dense_results else 0
            
            scores[doc_id]['rrf'] += rrf_score * dense_weight
            scores[doc_id]['dense'] = norm_score
            
            if doc_id not in doc_map:
                doc_map[doc_id] = item
        
        # Normalize sparse scores
        if sparse_results:
            max_sparse = max([s for _, s in sparse_results], default=1)
            sparse_range = max_sparse or 1
        
        # Score sparse results with normalization
        for rank, (doc, raw_score) in enumerate(sparse_results):
            doc_id = self._get_doc_id(doc)
            
            # RRF score
            rrf_score = 1.0 / (rrf_k + rank + 1)
            
            # Normalized BM25 score
            norm_score = raw_score / sparse_range if sparse_results else 0
            
            scores[doc_id]['rrf'] += rrf_score * sparse_weight
            scores[doc_id]['sparse'] = norm_score
            
            if doc_id not in doc_map:
                doc_map[doc_id] = doc
        
        # Calculate final hybrid score
        for doc_id in scores:
            rrf = scores[doc_id]['rrf']
            dense = scores[doc_id]['dense']
            sparse = scores[doc_id]['sparse']
            
            # Hybrid score = RRF + weighted normalized scores
            scores[doc_id]['final'] = rrf + (dense * dense_weight + sparse * sparse_weight) * 0.5
        
        # Sort by final score
        ranked = sorted(
            scores.items(), 
            key=lambda x: x[1]['final'], 
            reverse=True
        )
        
        # Return top k with all scores
        results = []
        for doc_id, score_dict in ranked[:k]:
            if doc_id in doc_map:
                result = doc_map[doc_id].copy()
                result['rrf_score'] = score_dict['rrf']
                result['hybrid_score'] = score_dict['final']
                result['dense_score'] = score_dict['dense']
                result['sparse_score'] = score_dict['sparse']
                results.append(result)
        
        logger.info(f"🔀 RRF fusion: {len(dense_results)} dense + {len(sparse_results)} sparse → {len(results)} results")
        return results
    
    def _get_doc_id(self, doc: Dict) -> str:
        """Generate consistent document ID"""
        source = doc.get('source', '')
        chunk_preview = doc.get('chunk', '')[:100]
        return f"{source}:{hash(chunk_preview)}"

# Global singleton instance
hybrid_retriever = HybridRetriever()