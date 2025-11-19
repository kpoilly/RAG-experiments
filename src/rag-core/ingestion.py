import logging
import os
import tempfile
from typing import Dict, List, Set

from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_classic.storage import EncoderBackedStore
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, UnstructuredMarkdownLoader, UnstructuredWordDocumentLoader
from langchain_community.storage import SQLStore
from langchain_core.documents import Document
from langchain_postgres.vectorstores import PGVector

from config import DB_URL
from config import settings as env
from ingestion_utils import S3Repository, VectorDBRepository, get_embeddings
from utils import value_deserializer, value_serializer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Ingestion")


def _build_retriever() -> ParentDocumentRetriever:
    """Configures the Parent Document Retriever (PDR) stack."""
    # Child
    vector_store = PGVector(collection_name=env.COLLECTION_NAME, connection=DB_URL, embeddings=get_embeddings())

    # Parent
    sql_store = SQLStore(db_url=DB_URL, namespace=f"{env.COLLECTION_NAME}_parents")

    store = EncoderBackedStore(sql_store, key_encoder=lambda key: key, value_serializer=value_serializer, value_deserializer=value_deserializer)

    return ParentDocumentRetriever(
        vectorstore=vector_store,
        docstore=store,
        child_splitter=RecursiveCharacterTextSplitter(chunk_size=env.CHUNK_SIZE_C, chunk_overlap=env.CHUNK_OVERLAP_C, separators=["\n\n", "\n", " "]),
        parent_splitter=RecursiveCharacterTextSplitter(chunk_size=env.CHUNK_SIZE_P, chunk_overlap=env.CHUNK_OVERLAP_P, separators=["\n#", "\n##", "\n\n\n"]),
    )


def _load_and_process_files(hashes_to_add: Set[str], s3_map: Dict[str, str], s3: S3Repository) -> List[Document]:
    """Downloads files to temp storage, loads them, and tags them with hashes."""
    LOADER_MAPPING = {".pdf": PyPDFLoader, ".docx": UnstructuredWordDocumentLoader, ".md": UnstructuredMarkdownLoader}

    docs = []
    with tempfile.TemporaryDirectory() as temp_dir:
        for doc_hash in hashes_to_add:
            key = s3_map[doc_hash]
            ext = os.path.splitext(key)[1].lower()

            if ext not in LOADER_MAPPING:
                logger.warning(f"Skipping unsupported: {key}")
                continue

            local_path = os.path.join(temp_dir, key.replace("/", "_"))
            try:
                logger.info(f"Downloading: {key}")
                s3.download_file(key, local_path)
                loader = LOADER_MAPPING[ext](local_path)
                pages = loader.load()

                for page in pages:
                    page.metadata["document_hash"] = doc_hash
                docs.extend(pages)
            except Exception as e:
                logger.error(f"Failed to process {key}: {e}")
    return docs


def process_and_index_documents() -> int:
    """
    Main Ingestion Workflow: Syncs S3 bucket state with PGVector index.
    """
    logger.info("Starting Ingestion Pipeline...")
    s3 = S3Repository()
    db = VectorDBRepository()
    s3.ensure_bucket_exists()
    db.ensure_schema()

    # S3 vs DB diff
    s3_files = s3.get_file_hashes()
    current_hashes = set(s3_files.keys())
    stored_hashes = db.get_existing_hashes()

    to_add = current_hashes - stored_hashes
    to_remove = stored_hashes - current_hashes

    if to_remove:
        logger.info(f"Removing {len(to_remove)} obsolete documents...")
        db.delete_documents(to_remove)

    if to_add:
        logger.info(f"Adding {len(to_add)} new documents...")
        new_docs = _load_and_process_files(to_add, s3_files, s3)

        if new_docs:
            logger.info(f"Indexing {len(new_docs)} pages via PDR...")
            retriever = _build_retriever()
            retriever.add_documents(new_docs, ids=None, add_to_docstore=True)

    total = db.count_chunks()
    logger.info(f"Sync Complete. Total Chunks in DB: {total}")
    return total


if __name__ == "__main__":
    process_and_index_documents()
