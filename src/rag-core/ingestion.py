import logging
import os
import tempfile
from typing import Optional

import boto3
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
from utils import calculate_file_hash_from_stream, value_deserializer, value_serializer

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


def get_s3_client():
    """
    Create a boto3 client for Minio/S3
    """
    return boto3.client("s3", endpoint_url=env.S3_ENDPOINT_URL, aws_access_key_id=env.S3_ACCESS_KEY_ID, aws_secret_access_key=env.S3_SECRET_ACCESS_KEY)


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


# --- Ingestion ---
def process_and_index_documents(data_dir: str = "/app/src/data") -> int:
    """
    Loads PDF documents, chunks and index them in PGVector using a batch approach.

    Args:
        data_dir: path to the data directory.
    Returns:
        total number of indexed documents.
    """
    logger.info(f"Starting ingestion from S3 bucket: {env.S3_BUCKET_NAME}...")
    initialize_database()

    s3_client = get_s3_client()
    collection_name = env.COLLECTION_NAME

    try:
        s3_client.head_bucket(Bucket=env.S3_BUCKET_NAME)
        logger.info(f"Bucket {env.S3_BUCKET_NAME} exists.")
    except s3_client.exceptions.ClientError:
        logger.error(f"Bucket {env.S3_BUCKET_NAME} does not exist.")
        s3_client.create_bucket(Bucket=env.S3_BUCKET_NAME)

    current_hashes = {}
    try:
        response = s3_client.list_objects_v2(Bucket=env.S3_BUCKET_NAME)
        for obj in response.get("Contents", []):
            file_obj = s3_client.get_object(Bucket=env.S3_BUCKET_NAME, Key=obj["Key"])
            file_stream = file_obj["Body"]
            current_hashes[calculate_file_hash_from_stream(file_stream)] = obj["Key"]
    except Exception as e:
        logger.error(f"Failed to list or hash objects in S3 bucket: {e}")
        return 0

    existing_hashes = set()
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
                hashes_to_add = set(current_hashes.keys()) - existing_hashes

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
    if hashes_to_add:
        logger.info(f"Found {len(hashes_to_add)} new documents to add.")
        loader_map = {
            ".pdf": PyPDFLoader,
            ".docx": UnstructuredWordDocumentLoader,
            ".md": UnstructuredMarkdownLoader,
        }
        allowed_extensions = set(loader_map.keys())

        with tempfile.TemporaryDirectory() as temp_dir:
            for doc_hash in hashes_to_add:
                file_key = current_hashes[doc_hash]
                # Filetype validation
                file_ext = os.path.splitext(file_key)[1].lower()
                if file_ext not in allowed_extensions:
                    logger.warning(f"Unsupported file type for '{file_key}' in S3 bucket, skipping.")
                    continue
                local_file_path = os.path.join(temp_dir, file_key.replace("/", "_"))

                try:
                    logger.info(f"Downloading new/modified document for indexing: {file_key}...")
                    s3_client.download_file(env.S3_BUCKET_NAME, file_key, local_file_path)
                    loader_class = loader_map[file_ext]
                    loader = loader_class(local_file_path)

                    loaded_pages = loader.load()
                    for page in loaded_pages:
                        page.metadata["document_hash"] = doc_hash
                    new_documents_to_add.extend(loaded_pages)

                except Exception as e:
                    logger.error(f"Error processing document {file_key}: {e}")

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
    return total_chunks


if __name__ == "__main__":
    process_and_index_documents()
