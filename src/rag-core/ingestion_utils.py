import logging
from typing import Dict, Optional, Set

import boto3
import psycopg
from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_core.embeddings import Embeddings

from config import DB_URL, MODELS_CONFIG
from config import settings as env
from utils import calculate_file_hash_from_stream

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
        )
        self.bucket = env.S3_BUCKET_NAME

    def ensure_bucket_exists(self) -> None:
        """Checks if bucket exists, creates it if not."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except self.client.exceptions.ClientError:
            logger.warning(f"Bucket '{self.bucket}' not found. Creating...")
            self.client.create_bucket(Bucket=self.bucket)

    def get_file_hashes(self) -> Dict[str, str]:
        """
        Scans S3 bucket and calculates hashes for all files via stream.
        Returns: {file_hash: s3_key}
        """
        hash_map = {}
        try:
            response = self.client.list_objects_v2(Bucket=self.bucket)
            for obj in response.get("Contents", []):
                key = obj["Key"]
                resp = self.client.get_object(Bucket=self.bucket, Key=key)
                file_hash = calculate_file_hash_from_stream(resp["Body"])
                hash_map[file_hash] = key
            return hash_map
        except Exception as e:
            logger.error(f"S3 Listing failed: {e}")
            return {}

    def download_file(self, key: str, dest_path: str) -> None:
        self.client.download_file(self.bucket, key, dest_path)


class VectorDBRepository:
    """
    Abstraction layer for PGVector & DocStore SQL operations.
    Handles transactions to ensure Parent and Child chunks remain synced.
    """

    def __init__(self):
        self.db_url = DB_URL.replace("+psycopg", "")
        self.collection = env.COLLECTION_NAME
        self.docstore_table = "langchain_key_value_stores"

    def _get_conn(self):
        return psycopg.connect(self.db_url, autocommit=False)

    def ensure_schema(self) -> None:
        """Creates vector extension and kv-store table if missing."""
        try:
            with self._get_conn() as conn, conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.docstore_table} (
                        namespace VARCHAR, key VARCHAR, value BYTEA,
                        PRIMARY KEY (namespace, key)
                    );
                """
                )
                conn.commit()
        except psycopg.Error as e:
            logger.error(f"DB Init failed: {e}")
            raise

    def get_existing_hashes(self) -> Set[str]:
        """Returns hashes of documents currently in the vector store."""
        query = """
            SELECT DISTINCT cmetadata ->> 'document_hash' FROM langchain_pg_embedding
            WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s);
        """
        try:
            with self._get_conn() as conn, conn.cursor() as cur:
                cur.execute(query, (self.collection,))
                return {row[0] for row in cur.fetchall() if row[0]}
        except psycopg.errors.UndefinedTable:
            return set()
        except psycopg.Error as e:
            logger.error(f"Error fetching hashes: {e}")
            return set()

    def delete_documents(self, hashes: Set[str]) -> None:
        """
        Atomic deletion of documents (both Parents and Children) based on hash.
        """
        if not hashes:
            return
        hash_list = list(hashes)

        # Find internal IDs -> Delete Children -> Delete Parents
        q_find_ids = """
            SELECT DISTINCT cmetadata ->> 'doc_id' FROM langchain_pg_embedding
            WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s)
            AND cmetadata ->> 'document_hash' = ANY(%s);
        """
        q_del_vecs = """
            DELETE FROM langchain_pg_embedding
            WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s)
            AND cmetadata ->> 'doc_id' = ANY(%s);
        """
        q_del_store = f"DELETE FROM {self.docstore_table} WHERE namespace = %s AND key = ANY(%s);"

        try:
            with self._get_conn() as conn, conn.cursor() as cur:
                cur.execute(q_find_ids, (self.collection, hash_list))
                parent_ids = [row[0] for row in cur.fetchall()]

                if parent_ids:
                    cur.execute(q_del_vecs, (self.collection, parent_ids))
                    cur.execute(q_del_store, (f"{self.collection}_parents", parent_ids))
                    logger.info(f"Deleted {len(parent_ids)} documents (Parents & Children).")
                conn.commit()
        except psycopg.Error as e:
            logger.error(f"Delete transaction failed: {e}")
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
