import logging
import os
import tempfile
from typing import Dict, List

from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_classic.storage import EncoderBackedStore
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, UnstructuredMarkdownLoader, UnstructuredWordDocumentLoader
from langchain_community.storage import SQLStore
from langchain_core.documents import Document
from langchain_postgres.vectorstores import PGVector

from core.config import settings as env
from database import models
from database.database import SessionLocal
from utils.utils import value_deserializer, value_serializer

from .ingestion_utils import S3Repository, VectorDBRepository, get_embeddings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Ingestion")


def _load_and_process_files(user_id: str, files_to_process: Dict[str, str], s3: S3Repository) -> List[Document]:
    """Downloads files to temp storage, loads them, and tags them with hashes."""
    LOADER_MAPPING = {".pdf": PyPDFLoader, ".docx": UnstructuredWordDocumentLoader, ".md": UnstructuredMarkdownLoader}

    docs = []
    with tempfile.TemporaryDirectory() as temp_dir:
        for filename, etag in files_to_process.items():
            ext = os.path.splitext(filename)[1].lower()
            if ext not in LOADER_MAPPING:
                logger.warning(f"Skipping unsupported file: {filename}")
                continue

            local_path = os.path.join(temp_dir, filename.replace("/", "_"))
            try:
                logger.info(f"Downloading: {filename}")
                s3.download_file(user_id, filename, local_path)

                loader = LOADER_MAPPING[ext](local_path)
                pages = loader.load()
                for page in pages:
                    page.metadata["source"] = filename
                    page.metadata["file_hash"] = etag
                docs.extend(pages)
            except Exception as e:
                logger.error(f"Failed to process {filename}: {e}")
    return docs


def process_and_index_documents(user_id: str) -> int:
    """
    Main Ingestion Workflow: Syncs S3 bucket state with PGVector index.
    """
    logger.info(f"Starting Ingestion Pipeline for user_id: {user_id}...")
    s3 = S3Repository()
    db = VectorDBRepository(user_id=user_id)
    s3.ensure_bucket_exists()
    db.ensure_schema()

    # S3 vs DB diff
    s3_files = s3.get_user_files(user_id=user_id)
    indexed_files = db.get_existing_files()

    files_to_delete_from_s3 = set(indexed_files.keys()) - set(s3_files.keys())
    files_to_process = {}
    for filename, etag in s3_files.items():
        if filename not in indexed_files or indexed_files[filename] != etag:
            files_to_process[filename] = etag

    files_to_remove_from_index = files_to_delete_from_s3.union({filename for filename in files_to_process if filename in indexed_files})

    if files_to_remove_from_index:
        logger.info(f"Removing {len(files_to_remove_from_index)} obsolete/modified documents from index...")
        db.delete_documents_by_source(list(files_to_remove_from_index))

    db_session = SessionLocal()
    try:
        if files_to_process:
            logger.info(f"Processing {len(files_to_process)} new/modified documents...")
            db_session.query(models.Document).filter(models.Document.user_id == user_id, models.Document.filename.in_(files_to_process.keys())).update(
                {"status": "processing"}, synchronize_session=False
            )
            db_session.commit()

            try:
                new_docs = _load_and_process_files(user_id, files_to_process, s3)

                if new_docs:
                    logger.info(f"Indexing {len(new_docs)} pages via PDR for user {user_id}...")
                    safe_user_id = user_id.replace("-", "")
                    collection_name = f"user_{safe_user_id}_collection"
                    namespace = f"user_{safe_user_id}_parents"

                    vector_store = PGVector(collection_name=collection_name, connection=env.DB_URL, embeddings=get_embeddings())
                    vector_store.create_tables_if_not_exists()
                    sql_store = SQLStore(db_url=env.DB_URL, namespace=namespace)
                    sql_store.create_schema()
                    store = EncoderBackedStore(sql_store, key_encoder=lambda key: key, value_serializer=value_serializer, value_deserializer=value_deserializer)

                    retriever = ParentDocumentRetriever(
                        vectorstore=vector_store,
                        docstore=store,
                        child_splitter=RecursiveCharacterTextSplitter(chunk_size=env.CHUNK_SIZE_C, chunk_overlap=env.CHUNK_OVERLAP_C),
                        parent_splitter=RecursiveCharacterTextSplitter(chunk_size=env.CHUNK_SIZE_P, chunk_overlap=env.CHUNK_OVERLAP_P),
                    )
                    retriever.add_documents(new_docs, ids=None, add_to_docstore=True)

                db_session.query(models.Document).filter(models.Document.user_id == user_id, models.Document.filename.in_(files_to_process.keys())).update(
                    {"status": "completed"}, synchronize_session=False
                )
                db_session.commit()

            except Exception as e:
                logger.error(f"Failed to process documents: {e}")
                db_session.query(models.Document).filter(models.Document.user_id == user_id, models.Document.filename.in_(files_to_process.keys())).update(
                    {"status": "failed", "error_message": str(e)}, synchronize_session=False
                )
                db_session.commit()
                raise e

    finally:
        db_session.close()

    total = db.count_chunks()
    logger.info(f"Sync Complete for user {user_id}. Total Chunks in DB: {total}")
    return total
