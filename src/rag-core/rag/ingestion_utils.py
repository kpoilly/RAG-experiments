import logging
from typing import Dict, List, Optional

import boto3
import psycopg
from botocore.config import Config
from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_core.embeddings import Embeddings

from core.config import MODELS_CONFIG
from core.config import settings as env

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Ingestion")


def configure_embedding_model(user_choice: str):
    """ """
    user_choice = user_choice.lower().strip()
    if user_choice not in MODELS_CONFIG:
        logger.info(f"Model '{user_choice}' not an alias.")
        return user_choice

    config = MODELS_CONFIG[user_choice]
    logger.info(f"Model config: '{user_choice}' -> {config['name']} (Dim: {config['dim']})")

    TextEmbedding.add_custom_model(
        model=config["name"], pooling=PoolingType.MEAN, normalization=True, dim=config["dim"], sources=ModelSource(hf=config["source"]), model_file=config["filename"]
    )
    return config["name"]


_EMBEDDER: Optional[Embeddings] = None


def get_embeddings() -> Embeddings:
    """Lazy singleton to load the embedding model only once."""
    global _EMBEDDER
    if _EMBEDDER is None:
        emb_model = configure_embedding_model(env.EMBEDDING_MODEL)
        logger.info(f"Initializing embeddings model ({emb_model})...")
        _EMBEDDER = FastEmbedEmbeddings(model_name=emb_model)
    return _EMBEDDER


class S3Repository:
    """Abstration layer for S3 operations."""

    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=env.S3_ENDPOINT_URL,
            aws_access_key_id=env.S3_ACCESS_KEY_ID,
            aws_secret_access_key=env.S3_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self.bucket = env.S3_BUCKET_NAME

    def ensure_bucket_exists(self) -> None:
        """Checks if bucket exists, creates it if not."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except self.client.exceptions.ClientError:
            logger.warning(f"Bucket '{self.bucket}' not found. Creating...")
            self.client.create_bucket(Bucket=self.bucket)

    def get_user_files(self, user_id: str) -> Dict[str, str]:
        """
        Scans a user-specific 'folder' (prefix) in the S3 bucket.
        Returns: {filename: etag}
        """
        self.ensure_bucket_exists()
        s3_files = {}
        prefix = f"{user_id}/"
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)
            for page in pages:
                for obj in page.get("Contents", []):
                    file_key = obj["Key"][len(prefix) :]
                    if file_key:
                        s3_files[file_key] = obj["ETag"].strip('"')
            return s3_files
        except Exception as e:
            logger.error(f"S3 Listing for user {user_id} failed: {e}")
            return {}

    def download_file(self, user_id: str, key: str, dest_path: str) -> None:
        full_key = f"{user_id}/{key}"
        self.client.download_file(self.bucket, full_key, dest_path)

    def upload_file(self, user_id: str, file_stream, filename: str):
        full_key = f"{user_id}/{filename}"
        self.client.upload_fileobj(file_stream, self.bucket, full_key)

    def delete_file(self, user_id: str, filename: str):
        full_key = f"{user_id}/{filename}"
        self.client.delete_object(Bucket=self.bucket, Key=full_key)


class VectorDBRepository:
    """
    Abstraction layer for PGVector & DocStore SQL operations.
    Handles transactions to ensure Parent and Child chunks remain synced.
    """

    def __init__(self, user_id: str):
        if not user_id:
            raise ValueError("user_id cannot be empty")
        self.user_id = user_id
        self.db_url = env.DB_URL.replace("+psycopg", "")
        self.collection = f"user_{user_id.replace("-", "")}_collection"
        self.docstore_namespace = f"user_{user_id.replace("-", "")}_parents"

    def _get_conn(self):
        return psycopg.connect(self.db_url, autocommit=False)

    def ensure_schema(self) -> None:
        """Creates vector extension and kv-store table if missing."""
        try:
            with self._get_conn() as conn, conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.docstore_namespace} (
                        namespace VARCHAR, key VARCHAR, value BYTEA,
                        PRIMARY KEY (namespace, key)
                    );
                """
                )
                conn.commit()
        except psycopg.Error as e:
            logger.error(f"DB Init failed: {e}")
            raise

    def get_existing_files(self) -> Dict[str, str]:
        """
        Gets a map of {filename: hash} for files currently indexed FOR THIS USER.
        """
        indexed_files = {}
        try:
            with self._get_conn() as conn, conn.cursor() as cur:
                query = """
                SELECT DISTINCT cmetadata ->> 'source' as file_source, cmetadata ->> 'file_hash' as file_hash
                FROM langchain_pg_embedding
                WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s);
                """
                cur.execute(query, (self.collection,))
                for row in cur.fetchall():
                    if row[0] and row[1]:
                        indexed_files[row[0]] = row[1]
        except psycopg.errors.UndefinedTable:
            logger.warning(f"Embedding table for collection '{self.collection}' does not exist yet.")
        return indexed_files

    def delete_documents_by_source(self, source_keys: List[str]) -> None:
        """
        Atomic deletion of documents (Parents and Children) based on their source filename.
        """
        if not source_keys:
            return

        q_find_ids = """
            SELECT DISTINCT cmetadata ->> 'doc_id' FROM langchain_pg_embedding
            WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s)
            AND cmetadata ->> 'source' = ANY(%s);
        """

        q_del_vecs = """
            DELETE FROM langchain_pg_embedding
            WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s)
            AND cmetadata ->> 'doc_id' = ANY(%s);
        """

        q_del_store = """
            DELETE FROM langchain_key_value_stores
            WHERE namespace = %s AND key = ANY(%s);
        """

        try:
            with self._get_conn() as conn, conn.cursor() as cur:
                cur.execute(q_find_ids, (self.collection, source_keys))
                parent_ids = [row[0] for row in cur.fetchall()]
                if parent_ids:
                    cur.execute(q_del_vecs, (self.collection, parent_ids))
                    cur.execute(q_del_store, (self.docstore_namespace, parent_ids))
                    logger.info(f"Deleted {len(parent_ids)} documents (Parents & Children) associated with {len(source_keys)} source files.")
                conn.commit()
        except psycopg.Error as e:
            logger.error(f"Delete transaction failed: {e}")
            conn.rollback()
            raise

    def count_chunks(self) -> int:
        """Returns total count of vector chunks."""
        q = "SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s);"
        try:
            with self._get_conn() as conn, conn.cursor() as cur:
                cur.execute(q, (self.collection,))
                res = cur.fetchone()
                return res[0] if res else 0
        except (psycopg.errors.UndefinedTable, psycopg.Error):
            return 0
