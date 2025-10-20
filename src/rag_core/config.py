from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application settings.
    Loads variables from environment variables.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # --- RAG Logic Settings ---
    MAX_CONTEXT_TOKENS: int = 10000
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    LLM_STRICT_RAG: bool = True

    # --- LLM & Gateway Settings ---
    LLM_MODEL: str = "llama-3.1-8b-instant"
    LLM_GATEWAY_URL: str = "http://llm-gateway:8002"

    # --- Embedding & Reranking Models ---
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANKER_THRESHOLD: float = 0.4

    # --- Database & Data Path Settings ---
    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    COLLECTION_NAME: str = "rag_documents_collection"
    DATA_PATH: str = "/app/src/data"


settings = Settings()
