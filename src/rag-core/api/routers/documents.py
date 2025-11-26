import asyncio
import logging
from typing import List
from urllib.parse import unquote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.models import DocumentResponse, IngestionResponse
from database import models
from rag.ingestion import process_and_index_documents
from rag.ingestion_utils import S3Repository
from rag.tasks import process_document_task

from .. import deps

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.get("", response_model=List[DocumentResponse])
async def list_documents(current_user: models.User = Depends(deps.get_current_user), db: Session = Depends(deps.get_db)):
    try:
        documents = db.query(models.Document).filter(models.Document.user_id == current_user.id).order_by(models.Document.created_at.desc()).all()
        return documents
    except Exception as e:
        logger.error(f"Failed to list documents for user {current_user.id}: {e}", exc_info=True)
        return []


@router.post("", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...), current_user: models.User = Depends(deps.get_current_user), db: Session = Depends(deps.get_db)):
    """
    Receives a file, validates it, uploads it to S3, and triggers ingestion.
    """

    import magic

    file_header = await file.read(2048)
    await file.seek(0)

    mime_type = magic.from_buffer(file_header, mime=True)
    allowed_mimes = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown"}
    # PDF: application/pdf
    # DOCX: application/vnd.openxmlformats-officedocument.wordprocessingml.document
    # MD: text/plain, text/markdown

    if mime_type not in allowed_mimes:
        # Fallback for markdown if it's detected as something else but has .md extension and is text
        if file.filename.lower().endswith(".md") and mime_type.startswith("text/"):
            pass
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type '{mime_type}'. Allowed: PDF, DOCX, Markdown.")

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File size exceeds the 50MB limit. Current size: {file_size / (1024 * 1024):.2f} MB")

    user_id = str(current_user.id)
    s3_repo = S3Repository()

    current_doc_count = db.query(models.Document).filter(models.Document.user_id == current_user.id).count()
    if current_doc_count >= current_user.document_limit:
        raise HTTPException(status_code=400, detail=f"Document limit reached. Your current plan allows for {current_user.document_limit} documents.")

    new_doc = models.Document(user_id=current_user.id, filename=file.filename, status="pending")
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    try:
        s3_repo.upload_file(user_id=user_id, file_stream=file.file, filename=file.filename)
        logger.info(f"Successfully uploaded file to S3 for user {user_id}.")
    except Exception as e:
        logger.error(f"Failed to upload file to S3: {e}", exc_info=True)
        new_doc.status = "failed"
        new_doc.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to upload file to storage.")

    logger.info(f"Triggering ingestion after upload by user {user_id}.")
    process_document_task.delay(user_id=user_id)
    logger.info(f"Ingestion task for user {user_id} has been queued.")
    return new_doc


@router.delete("/{document_name:path}")
async def delete_document(document_name: str, current_user: models.User = Depends(deps.get_current_user), db: Session = Depends(deps.get_db)):
    user_id = str(current_user.id)
    filename = unquote(document_name)
    s3_repo = S3Repository()

    try:
        s3_repo.delete_file(user_id=user_id, filename=filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file from storage: {e}")

    db.query(models.Document).filter(models.Document.user_id == current_user.id, models.Document.filename == filename).delete()
    db.commit()

    await asyncio.to_thread(process_and_index_documents, user_id=user_id)
    return {"filename": filename, "status": "deleted_and_reindexed"}


@router.post("/ingest", response_model=IngestionResponse)
async def ingest(current_user: models.User = Depends(deps.get_current_user)):
    """
    Manually triggers a full re-sync of the S3 bucket with the vector index.
    """
    logger.info("Starting ingestion...")
    user_id = str(current_user.id)
    indexed_count = await asyncio.to_thread(process_and_index_documents, user_id=user_id)
    if indexed_count > 0:
        logger.info("Ingestion completed successfully.")
        return IngestionResponse(indexed_chunks=indexed_count, status="success")
    else:
        logger.info("Ingestion complete. No new documents or changes found.")
        return IngestionResponse(indexed_chunks=0, status="no_changes")
