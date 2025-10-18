from pydantic import BaseModel
from typing import List, Dict


class GenerationRequest(BaseModel):
	query: str
	history: List[Dict[str, str]]

class IngestionResponse(BaseModel):
	indexed_chunks: int
	status: str

class Message(BaseModel):
	role: str
	content: str

class LLMRequest(BaseModel):
	messages: List[Message]
	model: str
