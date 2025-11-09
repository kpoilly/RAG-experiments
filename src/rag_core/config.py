from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application settings.
    Loads variables from environment variables.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # --- RAG Logic Settings ---
    MAX_CONTEXT_TOKENS: int = 6000
    LLM_STRICT_RAG: bool = True

    # --- LLM & Gateway Settings ---
    LLM_MODEL: str = "llama-3.1-8b-instant"
    LLM_GATEWAY_URL: str = "http://llm-gateway:8002"

    # --- Embedding & Reranking Models ---
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANKER_THRESHOLD: float = 0.4

    # --- Database & Data Path Settings ---
    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_NAME: str = "rag_db"
    DB_USER: str = "rag_user"
    DB_PASSWORD: str = "rag_password"
    TABLE_NAME: str = "rag_documents"

    DB_URL_ASYNC: str = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    DB_URL_PSYCOG2: str = f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST} port={DB_PORT}"

    DATA_PATH: str = "/app/src/data"


settings = Settings()
