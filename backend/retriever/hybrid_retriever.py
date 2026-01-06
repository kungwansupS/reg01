import logging
from rank_bm25 import BM25Okapi
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger("HybridRetriever")

class HybridRetriever:
    """
    🔥 Hybrid Search combining Dense (Semantic) + Sparse (BM25) with:
    - Thai tokenization support
    - Weighted RRF fusion
    - Better error handling
    """
    def __init__(self):
        self.bm25_index = None
        self.documents = []
        self.corpus_tokens = []
        self.use_thai_tokenizer = False
        
        # Try to import Thai tokenizer
        try:
            from pythainlp.tokenize import word_tokenize
            self.thai_tokenizer = word_tokenize
            self.use_thai_tokenizer = True
            logger.info("✅ Thai tokenizer (pythainlp) loaded")
        except ImportError:
            logger.warning("⚠️ pythainlp not found, using basic tokenization")
            self.thai_tokenizer = None
        
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
        try:
            self.bm25_index = BM25Okapi(self.corpus_tokens)
            logger.info(f"✅ BM25 index built with {len(chunks)} documents")
        except Exception as e:
            logger.error(f"❌ BM25 index build failed: {e}")
            self.bm25_index = None
    
    def _tokenize(self, text: str) -> List[str]:
        """
        🆕 Improved tokenization with Thai support
        
        Args:
            text: Text to tokenize
        
        Returns:
            List of tokens
        """
        if not text:
            return []
        
        # Use Thai tokenizer if available
        if self.use_thai_tokenizer and self.thai_tokenizer:
            try:
                # Use newmm engine for better accuracy
                tokens = self.thai_tokenizer(text.lower(), engine='newmm')
                # Filter out single characters and whitespace
                tokens = [t for t in tokens if len(t) > 1 and not t.isspace()]
                return tokens
            except Exception as e:
                logger.warning(f"⚠️ Thai tokenization failed: {e}, falling back to basic")
        
        # Fallback: basic tokenization
        # Split by whitespace and common punctuation
        import re
        tokens = re.findall(r'\w+', text.lower())
        return [t for t in tokens if len(t) > 1]
    
    def bm25_search(self, query: str, k: int = 10) -> List[Tuple[Dict, float]]:
        """
        BM25 keyword search
        
        Args:
            query: Search query
            k: Number of results to return
        
        Returns:
            List of (document, score) tuples
        """
        if not self.bm25_index:
            logger.warning("⚠️ BM25 index not built yet")
            return []
        
        try:
            query_tokens = self._tokenize(query)
            
            if not query_tokens:
                logger.warning("⚠️ Query tokenization resulted in empty tokens")
                return []
            
            scores = self.bm25_index.get_scores(query_tokens)
            
            # Get top k results with scores > 0
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
            
            if results:
                logger.debug(f"BM25 found {len(results)} results, top score: {results[0][1]:.2f}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ BM25 search error: {e}")
            return []
    
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
        🆕 Weighted Reciprocal Rank Fusion algorithm
        
        Args:
            dense_results: Results from vector search
            sparse_results: Results from BM25 search
            k: Number of results to return
            rrf_k: RRF constant (default 60)
            dense_weight: Weight for dense results (0-1)
            sparse_weight: Weight for sparse results (0-1)
        
        Returns:
            Fused and ranked results
        """
        scores = defaultdict(float)
        doc_map = {}
        
        # Normalize weights
        total_weight = dense_weight + sparse_weight
        if total_weight > 0:
            dense_weight = dense_weight / total_weight
            sparse_weight = sparse_weight / total_weight
        else:
            dense_weight = 0.5
            sparse_weight = 0.5
        
        # Score dense results (weighted)
        for rank, item in enumerate(dense_results):
            doc_id = self._get_doc_id(item)
            score = dense_weight * (1.0 / (rrf_k + rank + 1))
            scores[doc_id] += score
            if doc_id not in doc_map:
                doc_map[doc_id] = item
        
        # Score sparse results (weighted)
        for rank, (doc, _) in enumerate(sparse_results):
            doc_id = self._get_doc_id(doc)
            score = sparse_weight * (1.0 / (rrf_k + rank + 1))
            scores[doc_id] += score
            if doc_id not in doc_map:
                doc_map[doc_id] = doc
        
        # Sort by fused score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Return top k with scores
        results = []
        for doc_id, score in ranked[:k]:
            if doc_id in doc_map:
                result = doc_map[doc_id].copy() if isinstance(doc_map[doc_id], dict) else doc_map[doc_id]
                if isinstance(result, dict):
                    result['rrf_score'] = score
                results.append(result)
        
        logger.info(
            f"🔀 RRF fusion (dense: {dense_weight:.1%}, sparse: {sparse_weight:.1%}): "
            f"{len(dense_results)} + {len(sparse_results)} → {len(results)} results"
        )
        
        return results
    
    def _get_doc_id(self, doc: Dict) -> str:
        """
        Generate unique document ID
        
        Args:
            doc: Document dict
        
        Returns:
            Unique ID string
        """
        source = doc.get('source', '')
        chunk_preview = doc.get('chunk', '')[:50]
        index = doc.get('index', 0)
        return f"{source}_{index}_{chunk_preview}"

# Global singleton instance
hybrid_retriever = HybridRetriever()