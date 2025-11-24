from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application settings.
    Loads variables from environment variables.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # --- LLM & Gateway Settings ---
    LLM_GATEWAY_URL: str = "http://llm-gateway:8002"
    LLM_MAX_CONTEXT_TOKENS: int = 30000

    # --- Embedding & Reranking Models ---
    RERANKER_MODEL: str = "jinaai/jina-reranker-v2-base-multilingual"
    EMBEDDING_MODEL: str = "optimal"
    CHUNK_SIZE_P: int = 1500
    CHUNK_OVERLAP_P: int = 200
    CHUNK_SIZE_C: int = 300
    CHUNK_OVERLAP_C: int = 50

    # --- Database & Data Storage Settings ---
    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_NAME: str = "rag_db"
    DB_USER: str = "rag_user"
    DB_PASSWORD: str = "rag_password"

    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "rag-documents"

    @property
    def DB_URL(self) -> str:
        return f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # --- Security ---
    JWT_SECRET_KEY: str
    ENCRYPTION_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- User Settings ---
    USER_DOCUMENT_LIMIT: int = 20

    # --- Service Account ---
    SERVICE_ACCOUNT_EMAIL: str
    SERVICE_ACCOUNT_PASSWORD: str


settings = Settings()


MODELS_CONFIG = {
    "fast": {"name": "intfloat/multilingual-e5-small", "source": "Xenova/multilingual-e5-small", "dim": 384, "filename": "onnx/model_quantized.onnx"},
    "optimal": {"name": "intfloat/multilingual-e5-base", "source": "Xenova/multilingual-e5-base", "dim": 768, "filename": "onnx/model_quantized.onnx"},
    "quality": {"name": "intfloat/multilingual-e5-large", "source": "Xenova/multilingual-e5-large", "dim": 1024, "filename": "onnx/model_quantized.onnx"},
}
