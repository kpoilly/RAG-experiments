from typing import List

from pydantic import BaseModel, Field


class RAGConfigResponse(BaseModel):
    llm_model: str
    llm_side_model: str
    embedding_model: str
    reranker_model: str
    chunk_size_p: int
    chunk_overlap_p: int
    chunk_size_c: int
    chunk_overlap_c: int


class ModelInfo(BaseModel):
    model_name: str = Field(..., description="The display name or alias for the model.")
    model_id: str = Field(..., description="The full model ID to be used in API calls.")


class ModelListResponse(BaseModel):
    models: List[ModelInfo]
