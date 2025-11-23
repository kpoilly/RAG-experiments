from pydantic import BaseModel


class RAGConfigResponse(BaseModel):
    llm_model: str
    llm_side_model: str
    embedding_model: str
    reranker_model: str
    chunk_size_p: int
    chunk_overlap_p: int
    chunk_size_c: int
    chunk_overlap_c: int
