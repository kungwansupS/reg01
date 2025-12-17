from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance

from config import RAGConfig


class RAGCore:
    """Singleton core components for RAG"""

    @staticmethod
    @lru_cache(maxsize=1)
    def get_embeddings():
        print(f"🔹 Loading Embedding Model: {RAGConfig.EMBEDDING_MODEL_NAME}")

        embeddings = HuggingFaceEmbeddings(
            model_name=RAGConfig.EMBEDDING_MODEL_NAME,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": RAGConfig.NORMALIZE_EMBEDDINGS},
        )

        dim = len(embeddings.embed_query("test"))
        print(f"🔹 Detected embedding dimension: {dim}")

        return embeddings

    @staticmethod
    @lru_cache(maxsize=1)
    def get_vector_store():
        embeddings = RAGCore.get_embeddings()
        client = QdrantClient(path=RAGConfig.VECTOR_DB_PATH)

        if not client.collection_exists(RAGConfig.COLLECTION_NAME):
            print(f"🆕 Creating Qdrant collection: {RAGConfig.COLLECTION_NAME}")
            client.create_collection(
                collection_name=RAGConfig.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=len(embeddings.embed_query("test")),
                    distance=Distance.COSINE,
                ),
            )

        return QdrantVectorStore(
            client=client,
            collection_name=RAGConfig.COLLECTION_NAME,
            embedding=embeddings,
        )

    @staticmethod
    def get_retriever():
        return RAGCore.get_vector_store().as_retriever(
            search_type=RAGConfig.SEARCH_TYPE,
            search_kwargs={
                "k": RAGConfig.K,
                "fetch_k": RAGConfig.FETCH_K,
                "lambda_mult": RAGConfig.LAMBDA_MULT,
            },
        )
