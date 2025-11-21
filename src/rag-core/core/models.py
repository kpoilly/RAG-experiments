from typing import List, Optional

from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    query: str
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    strict_rag: Optional[bool] = None
    rerank_threshold: Optional[float] = Field(default=None, ge=-10.0, le=10.0)


class IngestionResponse(BaseModel):
    indexed_chunks: int
    status: str


class Message(BaseModel):
    role: str
    content: str


class LLMRequest(BaseModel):
    messages: List[Message]
    model: str
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    stream: Optional[bool] = None


class ExpandedQueries(BaseModel):
    queries: List[str] = Field(description="A list of 3 or fewer standalone search queries.")
