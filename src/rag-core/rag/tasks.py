from utils.celery_app import celery

from .ingestion import process_and_index_documents


@celery.task(name="process_document_task")
def process_document_task(user_id: str):
    """
    Celery task to process and index documents for a specific user.
    """
    process_and_index_documents(user_id=user_id)
