from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application settings.
    Loads variables from environment variables.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # --- LLM & Gateway Settings ---
    LLM_MODEL: str = "groq/llama-3.1-8b-instant"
    LLM_GATEWAY_URL: str = "http://llm-gateway:8002"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_CONTEXT_TOKENS: int = 30000
    LLM_STRICT_RAG: bool = False

    # --- Embedding & Reranking Models ---
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"
    CHUNK_SIZE_P: int = 1500
    CHUNK_OVERLAP_P: int = 200
    CHUNK_SIZE_C: int = 300
    CHUNK_OVERLAP_C: int = 50
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANKER_THRESHOLD: float = 0.4

    # --- Database & Data Path Settings ---
    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_NAME: str = "rag_db"
    DB_USER: str = "rag_user"
    DB_PASSWORD: str = "rag_password"
    DB_URL: str = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    COLLECTION_NAME: str = "rag_documents"
    DATA_PATH: str = "/app/src/data"


settings = Settings()
