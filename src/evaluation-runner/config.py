from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application settings.
    Loads variables from environment variables.
    """

    model_config = SettingsConfigDict(extra="ignore")

    CRITIC_LLM: str = "groq/meta-llama/llama-4-scout-17b-16e-instruct"
    GENERATOR_LLM: str = "groq/llama-3.1-8b-instant"
    LLM_GATEWAY_URL: str = "http://llm-gateway:8002"
    RAG_CORE_URL: str = "http://rag-core:8001"

    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"

    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "rag-documents"


settings = Settings()
