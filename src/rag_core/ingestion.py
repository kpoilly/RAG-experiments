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
        conn.commit()
        cur.close()
        conn.close()
    except psycopg.Error as e:
        logger.error(f"Error initializing database: {e}")
        raise


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

    collection_name = env.COLLECTION_NAME

    try:
        with psycopg.connect(env.DB_URL.replace("+psycopg", "")) as conn:
            with conn.cursor() as cur:
                try:
                    query = """
                    SELECT id FROM langchain_pg_embedding
                    WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s);
                    """
                    cur.execute(query, (collection_name,))
                    existing_hashes = {row[0].split("_")[0] for row in cur.fetchall() if row[0]}
                    logger.info(f"Found {len(existing_hashes)} existing document hashes in the database.")
                except psycopg.errors.UndefinedTable:
                    logger.warning("The embedding table does not exist yet. Proceeding with empty database.")
                    existing_hashes = set()

                current_hashes = {calculate_file_hash(path): path for path in files}
                current_hashes = {h: p for h, p in current_hashes.items() if h}

                hashes_to_rm = existing_hashes - set(current_hashes.keys())
                if hashes_to_rm:
                    logger.info(f"Found {len(hashes_to_rm)} documents to remove.")
                    delete_query = """
                    DELETE FROM langchain_pg_embedding
                    WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s)
                    AND SPLIT_PART(id, '_', 1) = ANY(%s);
                    """
                    cur.execute(delete_query, (collection_name, list(hashes_to_rm)))
                    conn.commit()
                    logger.info(f"Deleted chunks for {len(hashes_to_rm)} documents.")
    except psycopg.Error as e:
        logger.error(f"Error during read/delete phase: {e}", exc_info=True)
        return 0

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
            collection_name=collection_name,
            connection=env.DB_URL,
            pre_delete_collection=False,
            ids=[doc.metadata["chunk_id"] for doc in new_documents_to_add],
        )
        logger.info("New chunks added successfully.")

    total_chunks = 0
    try:
        with psycopg.connect(env.DB_URL.replace("+psycopg", "")) as conn:
            with conn.cursor() as cur:
                count_query = """
                SELECT COUNT(*) FROM langchain_pg_embedding
                WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s);
                """
                cur.execute(count_query, (collection_name,))
                res = cur.fetchone()
                total_chunks = res[0] if res else 0

    except psycopg.Error as e:
        logger.error(f"Error counting total chunks: {e}", exc_info=True)
        total_chunks = len(new_documents_to_add)

    logger.info(f"Ingestion Sync Complete. {len(new_documents_to_add)} new documents indexed. Total chunks in DB: {total_chunks}")
    return total_chunks


if __name__ == "__main__":
    process_and_index_documents()
