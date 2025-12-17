import logging
from langchain_huggingface import HuggingFaceEmbeddings
from backend.app.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    _instance = None
    _embeddings = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance

    def get_embeddings(self):
        """
        Returns a singleton instance of HuggingFaceEmbeddings using EmbeddingGemma.
        """
        if self._embeddings is None:
            logger.info(f"Loading Embedding Model: {settings.EMBEDDING_MODEL_NAME}...")
            try:
                model_kwargs = {'device': settings.EMBEDDING_DEVICE, 'trust_remote_code': True}
                encode_kwargs = {'normalize_embeddings': settings.NORMALIZE_EMBEDDINGS}
                
                self._embeddings = HuggingFaceEmbeddings(
                    model_name=settings.EMBEDDING_MODEL_NAME,
                    model_kwargs=model_kwargs,
                    encode_kwargs=encode_kwargs
                )
                logger.info("Embedding Model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load Embedding Model: {str(e)}")
                raise e
        
        return self._embeddings

# Global accessor
def get_embedding_function():
    return EmbeddingService().get_embeddings()