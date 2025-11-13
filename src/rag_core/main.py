import asyncio
import json
import logging
import os
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from ingestion import process_and_index_documents
from models import GenerationRequest, IngestionResponse
from retriever import build_retriever, init_components, orchestrate_rag_flow

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- init ---
app = FastAPI(title="RAG Core Service")

app.state.rad_ready = False
app.state.startup_error = None


@app.on_event("startup")
async def startup_event():
    """
    On startup, run ingestion and initialize the retrieval components.
    """
    logger.info("Application starting up...")
    try:
        data_path = os.getenv("DATA_PATH", "/app/src/data")
        await asyncio.to_thread(process_and_index_documents, data_path)
        await asyncio.to_thread(init_components)
        await build_retriever()
        app.state.rad_ready = True
        logger.info("Application startup complete. Ready to serve requests.")
    except Exception as e:
        logger.error(f"FATAL: RAG initialization failed during startup: {e}", exc_info=True)


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
    if indexed_count > 0:
        logger.info("Ingestion completed successfully.")
        return IngestionResponse(indexed_chunks=indexed_count, status="success")
    else:
        raise HTTPException(status_code=500, detail="Error during ingestion.")


@app.post("/chat")
async def generate(request: GenerationRequest):
    try:
        formated_query = re.sub(r"(\b[ldjstnmc]|qu)'", r"\1 ", request.query.lower())
        response_generator = orchestrate_rag_flow(formated_query, request.history)
        return StreamingResponse(content=response_generator, media_type="text/event-stream")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return StreamingResponse(content=json.dumps({"type": "error", "content": str(e)}), media_type="application/jsonlines", status_code=500)
