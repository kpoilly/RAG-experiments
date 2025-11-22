import asyncio
import logging

import boto3
import psycopg
from prometheus_client import Gauge, Histogram

from core.config import settings as env

logger = logging.getLogger("Metrics")

# Define Metrics
RAG_S3_DOCUMENTS_TOTAL = Gauge("rag_s3_documents_total", "Total number of documents in S3 bucket")
RAG_INDEXED_CHUNKS_TOTAL = Gauge("rag_indexed_chunks_total", "Total number of vector chunks in the database")
RAG_RETRIEVAL_LATENCY = Histogram("rag_retrieval_latency_seconds", "Latency of the retrieval process")
RAG_RETRIEVED_DOCS = Histogram("rag_retrieved_docs_count", "Number of documents retrieved per query", buckets=[0, 1, 3, 5, 10, 20, 50])


async def update_metrics():
    """
    Background task to update RAG metrics periodically.
    """
    while True:
        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=env.S3_ENDPOINT_URL,
                aws_access_key_id=env.S3_ACCESS_KEY_ID,
                aws_secret_access_key=env.S3_SECRET_ACCESS_KEY,
            )

            s3_count = 0
            paginator = s3.get_paginator("list_objects_v2")
            try:
                for page in paginator.paginate(Bucket=env.S3_BUCKET_NAME):
                    if "Contents" in page:
                        s3_count += len(page["Contents"])
                RAG_S3_DOCUMENTS_TOTAL.set(s3_count)
            except s3.exceptions.NoSuchBucket:
                logger.warning(f"Bucket {env.S3_BUCKET_NAME} not found.")
                RAG_S3_DOCUMENTS_TOTAL.set(0)
            except Exception as e:
                logger.error(f"Error counting S3 documents: {e}")
            try:
                db_url = env.DB_URL.replace("+psycopg", "")
                with psycopg.connect(db_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT to_regclass('public.langchain_pg_embedding');")
                        if cur.fetchone()[0]:
                            cur.execute("SELECT COUNT(*) FROM langchain_pg_embedding;")
                            db_count = cur.fetchone()[0]
                            RAG_INDEXED_CHUNKS_TOTAL.set(db_count)
                        else:
                            RAG_INDEXED_CHUNKS_TOTAL.set(0)
            except Exception as e:
                logger.error(f"Error counting DB chunks: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in metrics update loop: {e}")
        await asyncio.sleep(60)
