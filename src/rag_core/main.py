import os
import json
import logging
import asyncio

from typing import List, Dict
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from retriever import orchestrate_rag_flow, get_ensemble_retriever
from ingestion import process_and_index_documents


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Pydantic models ---
class GenerationRequest(BaseModel):
	query: str
	history: List[Dict[str, str]]

class GenerationResponse(BaseModel):
	response: str
	source_chunks: List[str]
	status: str

class IngestionResponse(BaseModel):
	indexed_chunks: int
	status: str


# --- init ---
app = FastAPI(title="RAG Core Service")

# --- Endpoints ---
@app.get("/health")
async def health():
	"""
	Health check.
	"""
	return {"status": "ok"}

@app.post("/ingest", response_model=IngestionResponse)
async def ingest(data_path: str = os.getenv("DATA_PATH", "/app/src/data")):
	"""
	Start the ingestion process (Loading, Chunking and Indexing documents).
	"""
	logger.info(f"Starting ingestion for path: {data_path}")

	indexed_count = await asyncio.to_thread(process_and_index_documents, data_path)
	_, __ = get_ensemble_retriever()
	if indexed_count > 0:
		return IngestionResponse(indexed_chunks=indexed_count, status="success")
	else:
		raise HTTPException(status_code=500, detail="Error during ingestion.")

@app.post("/chat")
async def generate(request: GenerationRequest):
	try:
		response_generator = orchestrate_rag_flow(request.query, request.history)
		return StreamingResponse(
			content=response_generator,
			media_type="application/jsonlines"
		)
	except Exception as e:
		logger.error(f"An unexpected error occurred: {e}")
		return StreamingResponse(
			content = json.dumps({"type": "error", "content": str(e)}),
			media_type="application/jsonlines",
			status_code=500
		)
