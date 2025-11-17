import glob
import hashlib
import logging
import os
from typing import Optional

import psycopg
import torch
from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_classic.storage import EncoderBackedStore
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, UnstructuredMarkdownLoader, UnstructuredWordDocumentLoader
from langchain_community.storage import SQLStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres.vectorstores import PGVector

from config import settings as env
from utils import value_deserializer, value_serializer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- DB set up ---
def initialize_database():
    """
    Initialize the PostgreSQL database and create the necessary table if it doesn't exist.
    """
    try:
        logger.info("Connecting to PostgreSQL to initialize database schema...")
        with psycopg.connect(env.DB_URL.replace("+psycopg", "")) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                logger.info("pgvector extension is enabled.")

                create_table_query = """
                CREATE TABLE IF NOT EXISTS langchain_key_value_stores (
                    namespace VARCHAR,
                    key VARCHAR,
                    value BYTEA,
                    PRIMARY KEY (namespace, key)
                );
                """
                cur.execute(create_table_query)
                logger.info("SQLStore table 'langchain_key_value_stores' is ready.")

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

    supported_extensions = ["*.pdf", "*.docx", "*.md"]
    files = []
    for ext in supported_extensions:
        files.extend(glob.glob(os.path.join(data_dir, ext)))
    if not files:
        logger.error(f"No files found in {data_dir}")
        hashes_to_rm = ["%"]

    collection_name = env.COLLECTION_NAME

    existing_hashes = set()
    current_hashes = {calculate_file_hash(path): path for path in files if calculate_file_hash(path)}

    try:
        with psycopg.connect(env.DB_URL.replace("+psycopg", "")) as conn:
            with conn.cursor() as cur:
                try:
                    query = """
                    SELECT DISTINCT cmetadata ->> 'document_hash' FROM langchain_pg_embedding
                    WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s);
                    """
                    cur.execute(query, (collection_name,))
                    existing_hashes = {row[0] for row in cur.fetchall() if row[0]}
                    logger.info(f"Found {len(existing_hashes)} existing document hashes in the database.")
                except psycopg.errors.UndefinedTable:
                    logger.warning("The embedding table does not exist yet. Proceeding with empty database.")

                hashes_to_rm = existing_hashes - set(current_hashes.keys())

                if not files:
                    hashes_to_rm = existing_hashes

                if hashes_to_rm:
                    logger.info(f"Found {len(hashes_to_rm)} documents to remove.")

                    get_parent_keys_query = """
                    SELECT DISTINCT cmetadata ->> 'doc_id' FROM langchain_pg_embedding
                    WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s)
                    AND cmetadata ->> 'document_hash' = ANY(%s);
                    """
                    cur.execute(get_parent_keys_query, (collection_name, list(hashes_to_rm)))
                    parent_keys = [row[0] for row in cur.fetchall()]

                    if parent_keys:
                        delete_query_children = """
                        DELETE FROM langchain_pg_embedding
                        WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s)
                        AND cmetadata ->> 'doc_id' = ANY(%s);
                        """
                        cur.execute(delete_query_children, (collection_name, parent_keys))
                        logger.info(f"Deleted chunks for {len(hashes_to_rm)} documents.")
                        delete_query_parents = """
                        DELETE FROM langchain_key_value_stores
                        WHERE namespace = %s AND key = ANY(%s);
                        """
                        cur.execute(delete_query_parents, (f"{collection_name}_parents", parent_keys))
                        logger.info(f"Deleted {len(parent_keys)} parent documents from docstore.")
    except psycopg.errors.UndefinedTable:
        logger.warning("The embedding or kv table does not exist yet. Proceeding with empty database.")
    except psycopg.Error as e:
        logger.error(f"Error during read/delete phase: {e}", exc_info=True)
        return 0

    new_documents_to_add = []
    for doc_hash, path in current_hashes.items():
        if doc_hash not in existing_hashes:
            try:
                logger.info(f"Preparing new/modified document for indexing: {os.path.basename(path)}")
                if path.endswith(".pdf"):
                    loader = PyPDFLoader(path)
                elif path.endswith(".docx"):
                    loader = UnstructuredWordDocumentLoader(path)
                elif path.endswith(".md"):
                    loader = UnstructuredMarkdownLoader(path)
                else:
                    logger.warning(f"Unsupported file type for {path}, skipping.")
                    continue

                loaded_pages = loader.load()
                for page in loaded_pages:
                    page.metadata["document_hash"] = doc_hash
                new_documents_to_add.extend(loaded_pages)

            except Exception as e:
                logger.error(f"Error preparing document {path} for indexing: {e}")

    if new_documents_to_add:
        logger.info(f"Adding {len(new_documents_to_add)} new pages to the database...")
        embedder = get_embeddings()
        vector_store = PGVector(collection_name=collection_name, connection=env.DB_URL, embeddings=embedder)
        sql_store = SQLStore(db_url=env.DB_URL, namespace=f"{collection_name}_parents")
        store = EncoderBackedStore(sql_store, key_encoder=lambda key: key, value_serializer=value_serializer, value_deserializer=value_deserializer)
        parent_splitter = RecursiveCharacterTextSplitter(chunk_size=env.CHUNK_SIZE_P, chunk_overlap=env.CHUNK_OVERLAP_P, separators=["\n#", "\n##", "\n\n\n"])
        child_splitter = RecursiveCharacterTextSplitter(chunk_size=env.CHUNK_SIZE_C, chunk_overlap=env.CHUNK_OVERLAP_C, separators=["\n\n", "\n###", "\n"])
        logger.info(
            f"Splitters initialized. \
(Parent Settings: size={env.CHUNK_SIZE_P}, overlap={env.CHUNK_OVERLAP_P}, \
Child Settings: size={env.CHUNK_SIZE_C}, overlap={env.CHUNK_OVERLAP_C})"
        )

        retriever = ParentDocumentRetriever(
            vectorstore=vector_store,
            docstore=store,
            child_splitter=child_splitter,
            parent_splitter=parent_splitter,
        )
        retriever.add_documents(new_documents_to_add, ids=None, add_to_docstore=True)
        logger.info("New documents added successfully.")

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

    logger.info(f"Ingestion Sync Complete. {len(new_documents_to_add)} new pages indexed. Total chunks in DB: {total_chunks}")
    return total_chunks + len(hashes_to_rm)


if __name__ == "__main__":
    process_and_index_documents()
