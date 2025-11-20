import os
import logging
import asyncio
from typing import List
from urllib.parse import unquote

from fastapi import APIRouter, File, HTTPException, UploadFile, Depends

from .. import deps
from database import models
from core.config import settings as env
from core.models import IngestionResponse
from rag.ingestion import process_and_index_documents
from rag.ingestion_utils import S3Repository


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

@router.get("", response_model=List[str])
async def list_documents(
    s3_repo: S3Repository = Depends(deps.get_s3_repo),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Lists all documents currently in the S3 bucket."""
    try:
        response = s3_repo.client.list_objects_v2(Bucket=env.S3_BUCKET_NAME)
        return sorted([obj["Key"] for obj in response.get("Contents", [])])
    except Exception as e:
        logger.error(f"Failed to list documents from S3: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list documents from storage.")


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    s3_repo: S3Repository = Depends(deps.get_s3_repo),
    current_user: models.User = Depends(deps.get_current_user)
):
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
        s3_repo.client.upload_fileobj(file.file, env.S3_BUCKET_NAME, file.filename)
        logger.info(f"Successfully uploaded '{file.filename}' to S3.")
    except Exception as e:
        logger.error(f"Failed to upload file to S3: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload file to storage.")

    # Ingest
    logger.info(f"Triggering ingestion after upload of '{file.filename}'.")
    await asyncio.to_thread(process_and_index_documents)
    return {"filename": file.filename, "status": "uploaded_and_ingested"}


@router.delete("/{document_name:path}")
async def delete_document(
    document_name: str,
    s3_repo: S3Repository = Depends(deps.get_s3_repo),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Deletes a document from S3 and triggers a re-sync of the index.
    """
    decoded_doc_name = unquote(document_name)
    try:
        s3_repo.client.delete_object(Bucket=env.S3_BUCKET_NAME, Key=decoded_doc_name)
        logger.info(f"Successfully deleted '{decoded_doc_name}' from S3.")
    except Exception as e:
        logger.error(f"Failed to delete file from S3: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete file from storage.")

    logger.info(f"Triggering ingestion after deletion of '{decoded_doc_name}'.")
    await asyncio.to_thread(process_and_index_documents)
    return {"filename": decoded_doc_name, "status": "deleted_and_reindexed"}

@router.post("/ingest", response_model=IngestionResponse)
async def ingest(current_user: models.User = Depends(deps.get_current_user)):
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
