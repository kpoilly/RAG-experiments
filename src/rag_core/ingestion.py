import glob
import hashlib
import logging
import os
from typing import Optional

import psycopg
import torch
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_experimental.text_splitter import SemanticChunker
from langchain_postgres.vectorstores import PGVector

from config import settings as env

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- DB set up ---
def initialize_database():
    """
    Initialize the PostgreSQL database and create the necessary table if it doesn't exist.
    """
    try:
        logger.info("Connecting to PostgreSQL to initialize database schema...")
        conn = psycopg.connect(env.DB_URL.replace("+psycopg", ""))
        cur = conn.cursor()

        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        logger.info("pgvector extension is enabled.")

        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {env.TABLE_NAME} (
            chunk_id TEXT PRIMARY KEY,
            document_hash TEXT,
            page_content TEXT,
            metadata JSONB
        );
        """

        cur.execute(create_table_query)
        conn.commit()
        logger.info(f"Table '{env.TABLE_NAME}' created successfully.")
        cur.close()

    except psycopg.Error as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        if conn:
            conn.close()
        logger.info(f"Database initialized and table '{env.TABLE_NAME}' is ready.")


_EMBEDDER: Optional[HuggingFaceEmbeddings] = None


def get_embeddings():
    """
    Load the embeddings model.
    """
    logger.info("Loading embeddings model...")
    global _EMBEDDER
    if _EMBEDDER is None:
        logger.info(f"Initializing embeddings model ({env.EMBEDDING_MODEL})...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        _EMBEDDER = HuggingFaceEmbeddings(model_name=env.EMBEDDING_MODEL, model_kwargs={"device": device})
    logger.info("Embeddings model loaded.")
    return _EMBEDDER


# --- Haching and files ID ---
def calculate_file_hash(file_path: str) -> str:
    """
    Calculate the hash of a file for stable ID.
    """
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as file:
            while True:
                chunk = file.read(4096)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Failed to hash file {file_path}: {e}")
        return ""


def create_chunk_id(doc_hash: str, chunk_index: int) -> str:
    """Create a stable ID for a chunk."""
    return f"{doc_hash}_{chunk_index}"


# --- Ingestion ---
def process_and_index_documents(data_dir: str = "/app/src/data") -> int:
    """
    Loads PDF documents, chunks and index them in PGVector using a batch approach.

    Args:
        data_dir: path to the data directory.
    Returns:
        total number of indexed documents.
    """
    logger.info(f"Starting ingestion from {data_dir}...")
    initialize_database()

    files = glob.glob(os.path.join(data_dir, "*.pdf"))
    if not files:
        logger.error(f"No PDF files found in {data_dir}")
        return 0

    try:
        conn = psycopg.connect(env.DB_URL.replace("+psycopg", ""))
        cur = conn.cursor()
    except psycopg.OperationalError as e:
        logger.error(f"Error connecting to PostgreSQL: {e}")
        return 0

    cur.execute(f"SELECT DISTINCT document_hash FROM {env.TABLE_NAME};")
    existing_hashes = {row[0] for row in cur.fetchall()}
    logger.info(f"Found {len(existing_hashes)} existing document hashes in the database.")

    current_hashes = {calculate_file_hash(path): path for path in files}
    current_hashes = {h: p for h, p in current_hashes.items() if h}

    hashes_to_rm = existing_hashes - set(current_hashes.keys())
    if hashes_to_rm:
        logger.info(f"Found {len(hashes_to_rm)} documents to remove.")
        cur.execute(f"DELETE FROM {env.TABLE_NAME} WHERE document_hash = ANY(%s)", (list(hashes_to_rm),))
        conn.commit()
        logger.info(f"Deleted chunks for {len(hashes_to_rm)} documents.")

    new_documents_to_add = []
    embedder = get_embeddings()
    text_splitter = SemanticChunker(embedder, breakpoint_threshold_type="percentile")

    for doc_hash, path in current_hashes.items():
        if doc_hash not in existing_hashes:
            try:
                logger.info(f"Preparing new/modified document for batch indexing: {os.path.basename(path)}")
                loader = PyPDFLoader(path)
                documents = loader.load()
                chunks = text_splitter.split_documents(documents)

                for i, chunk in enumerate(chunks):
                    metadata = chunk.metadata
                    metadata["document_hash"] = doc_hash
                    metadata["chunk_id"] = create_chunk_id(doc_hash, i)
                    metadata["source"] = os.path.basename(path)

                    new_doc = Document(page_content=chunk.page_content, metadata=metadata)
                    new_documents_to_add.append(new_doc)

            except Exception as e:
                logger.error(f"Error preparing document {path} for indexing: {e}")
                return 0

    if new_documents_to_add:
        logger.info(f"Adding {len(new_documents_to_add)} new chunks to the database...")
        PGVector.from_documents(
            documents=new_documents_to_add,
            embedding=embedder,
            collection_name=env.TABLE_NAME,
            connection=env.DB_URL,
            ids=[doc.metadata["chunk_id"] for doc in new_documents_to_add],
            pre_delete_collection=False,
        )
        logger.info("New chunks added successfully.")

    cur.execute(f"SELECT COUNT(*) FROM {env.TABLE_NAME};")
    total_chunks = cur.fetchone()[0]
    cur.close()
    conn.close()

    logger.info(f"Ingestion Sync Complete. {len(new_documents_to_add)} new documents indexed. Total chunks in DB: {total_chunks}")
    return total_chunks


if __name__ == "__main__":
    process_and_index_documents()
