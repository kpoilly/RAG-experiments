import asyncio
import json
import logging
import os
import re

import httpx

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse

from ingestion import process_and_index_documents
from models import GenerationRequest, IngestionResponse
from retriever import build_retriever, init_components, orchestrate_rag_flow
from config import settings as env

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- init ---
app = FastAPI(title="RAG Core Service")

app.state.rad_ready = False
app.state.startup_error = None


@app.on_event("startup")
async def startup_event():
    """
    On startup, get model info, run ingestion and initialize the retrieval components.
    """
    logger.info("Application starting up...")
    try:
        model_info_url = f"{env.LLM_GATEWAY_URL}/model/info"
        async with httpx.AsyncClient() as client:
            response = await client.get(model_info_url)
            response.raise_for_status()
            all_models_info = response.json()

            models_list = all_models_info.get("data", [])
            model_config = next((model for model in models_list if (
                model.get("model_name") == env.LLM_MODEL or 
                model.get("litellm_params", {}).get("model") == env.LLM_MODEL or 
                model.get("model_info", {}).get("key") == env.LLM_MODEL)), None)

            context_window = None
            if model_config :
                context_window = model_config.get("model_info", {}).get("max_input_tokens")
            if context_window is None:
                logger.warning(f"Context window info not found for model {env.LLM_MODEL}. Using default value: {env.LLM_MAX_CONTEXT_TOKENS}.")
            else:
                env.LLM_MAX_CONTEXT_TOKENS = context_window
                logger.info(f"Successfully retrieved and set context window for {env.LLM_MODEL}: {env.LLM_MAX_CONTEXT_TOKENS} tokens.")
            logger.info(f"Context window for {env.LLM_MODEL}: {env.LLM_MAX_CONTEXT_TOKENS} tokens")

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
    if not app.state.rad_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "reason": "RAG components are not ready yet.", "error": app.state.startup_error},
        )
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
        response_generator = orchestrate_rag_flow(formated_query, request.history, request.temperature, request.strict_rag, request.rerank_threshold)
        return StreamingResponse(content=response_generator, media_type="text/event-stream")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return StreamingResponse(content=json.dumps({"type": "error", "content": str(e)}), media_type="application/jsonlines", status_code=500)
