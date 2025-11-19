import asyncio
import json
import logging
import os
import re
from typing import List
from urllib.parse import unquote

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from config import settings as env
from ingestion import process_and_index_documents
from ingestion_utils import S3Repository
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
            model_config = next(
                (
                    model
                    for model in models_list
                    if (
                        model.get("model_name") == env.LLM_MODEL
                        or model.get("litellm_params", {}).get("model") == env.LLM_MODEL
                        or model.get("model_info", {}).get("key") == env.LLM_MODEL
                    )
                ),
                None,
            )

            context_window = None
            if model_config:
                context_window = model_config.get("model_info", {}).get("max_input_tokens")
            if context_window is None:
                logger.warning(f"Context window info not found for model {env.LLM_MODEL}. Using default value: {env.LLM_MAX_CONTEXT_TOKENS}.")
            else:
                env.LLM_MAX_CONTEXT_TOKENS = context_window
                logger.info(f"Successfully retrieved and set context window for {env.LLM_MODEL}: {env.LLM_MAX_CONTEXT_TOKENS} tokens.")
            logger.info(f"Context window for {env.LLM_MODEL}: {env.LLM_MAX_CONTEXT_TOKENS} tokens")

        await asyncio.to_thread(process_and_index_documents)
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
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"status": "error", "reason": "RAG components are not ready yet.", "error": app.state.startup_error}
        )
    return {"status": "ok"}


@app.get("/documents", response_model=List[str])
async def list_documents():
    """Lists all documents currently in the S3 bucket."""
    try:
        s3_repo = S3Repository()
        response = s3_repo.client.list_objects_v2(Bucket=env.S3_BUCKET_NAME)
        return sorted([obj["Key"] for obj in response.get("Contents", [])])
    except Exception as e:
        logger.error(f"Failed to list documents from S3: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list documents from storage.")


@app.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    """
    Receives a file, validates it, uploads it to S3, and triggers ingestion.
    """
    # Validate
    allowed_extensions = {".pdf", ".md", ".docx"}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{file_ext}'.")

    # Upload
    try:
        s3_repo = S3Repository()
        s3_repo.client.upload_fileobj(file.file, env.S3_BUCKET_NAME, file.filename)
        logger.info(f"Successfully uploaded '{file.filename}' to S3.")
    except Exception as e:
        logger.error(f"Failed to upload file to S3: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload file to storage.")

    # Ingest
    logger.info(f"Triggering ingestion after upload of '{file.filename}'.")
    await asyncio.to_thread(process_and_index_documents)
    return {"filename": file.filename, "status": "uploaded_and_ingested"}


@app.delete("/documents/{document_name:path}")
async def delete_document(document_name: str):
    """
    Deletes a document from S3 and triggers a re-sync of the index.
    """
    decoded_doc_name = unquote(document_name)
    try:
        s3_repo = S3Repository()
        s3_repo.client.delete_object(Bucket=env.S3_BUCKET_NAME, Key=decoded_doc_name)
        logger.info(f"Successfully deleted '{decoded_doc_name}' from S3.")
    except Exception as e:
        logger.error(f"Failed to delete file from S3: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete file from storage.")

    logger.info(f"Triggering ingestion after deletion of '{decoded_doc_name}'.")
    await asyncio.to_thread(process_and_index_documents)
    return {"filename": decoded_doc_name, "status": "deleted_and_reindexed"}


@app.post("/ingest", response_model=IngestionResponse)
async def ingest():
    """
    Manually triggers a full re-sync of the S3 bucket with the vector index.
    """
    logger.info("Starting ingestion...")
    indexed_count = await asyncio.to_thread(process_and_index_documents)
    if indexed_count > 0:
        logger.info("Ingestion completed successfully.")
        return IngestionResponse(indexed_chunks=indexed_count, status="success")
    else:
        logger.info("Ingestion complete. No new documents or changes found.")
        return IngestionResponse(indexed_chunks=0, status="no_changes")


@app.post("/chat")
async def generate(request: GenerationRequest):
    try:
        formated_query = re.sub(r"(\b[ldjstnmc]|qu)'", r"\1 ", request.query.lower())
        response_generator = orchestrate_rag_flow(formated_query, request.history, request.temperature, request.strict_rag, request.rerank_threshold)
        return StreamingResponse(content=response_generator, media_type="text/event-stream")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return StreamingResponse(content=json.dumps({"type": "error", "content": str(e)}), media_type="application/jsonlines", status_code=500)
