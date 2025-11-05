import glob
import hashlib
import logging
import os
from typing import Optional

import torch
from chromadb import HttpClient, Settings
from chromadb.api.models.Collection import Collection
from langchain_experimental.text_splitter import SemanticChunker
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings

from config import settings as env

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- Chroma set up ---
_chroma_client: Optional[HttpClient] = None


def get_chroma_client() -> Optional[HttpClient]:
    """
    Get the Chroma client.
    """
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client

    try:
        _chroma_client = HttpClient(host=env.CHROMA_HOST, port=env.CHROMA_PORT, settings=Settings(allow_reset=True))
        _chroma_client.heartbeat()
        logger.info(f"Connected to ChromaDB at {env.CHROMA_HOST}:{env.CHROMA_PORT}")
    except Exception as e:
        logger.error(f"Error connecting to ChromaDB: {e}")
        _chroma_client = None
    return _chroma_client


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


def get_or_create_collection(client: HttpClient, collection_name: str) -> Collection:
    """
    Get or create a Chroma collection.
    """
    try:
        collection = client.get_collection(collection_name)
        logger.info(f"Collection {collection_name} loaded successfully.")
        return collection
    except Exception:
        logger.info(f"Collection {collection_name} does not exist. Creating...")
        collection = client.create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
        logger.info(f"Collection {collection_name} created successfully.")
        return collection


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
    Loads PDF documents, chunks and index them in ChromaDB using a batch approach.

    Args:
        data_dir: path to the data directory.
    Returns:
        total number of indexed documents.
    """
    BATCH_SIZE = 512
    logger.info(f"Starting ingestion from {data_dir}...")

    files = glob.glob(os.path.join(data_dir, "*.pdf"))
    if not files:
        logger.error(f"No PDF files found in {data_dir}")
        return 0

    client = get_chroma_client()
    if not client:
        logger.error("Error connecting to ChromaDB")
        return 0

    collection = get_or_create_collection(client, env.COLLECTION_NAME)

    existing_hashes = {meta.get("document_hash") for meta in collection.get(include=["metadatas"])["metadatas"] if meta and meta.get("document_hash")}
    current_hashes = {calculate_file_hash(path): path for path in files}
    current_hashes = {hash: path for hash, path in current_hashes.items() if hash}

    hashes_to_rm = existing_hashes.difference(set(current_hashes.keys()))
    if hashes_to_rm:
        ids_to_rm = []
        metadatas = collection.get(include=["metadatas"])["metadatas"]
        for i, meta in enumerate(metadatas):
            if meta.get("document_hash") in hashes_to_rm:
                ids_to_rm.append(collection.get(include=[])['ids"'][i])
        for hash in hashes_to_rm:
            collection.delete(where={"document_hash": hash})
            logger.info(f"Deleted document chunk with hash {hash} from ChromaDB.")

    new_chunk_ids = []
    new_chunk_contents = []
    new_chunk_metadatas = []
    
    embedder = get_embeddings()
    text_splitter = SemanticChunker(
        embedder,
        breakpoint_threshold_type="percentile")

    for doc_hash, path in current_hashes.items():
        if doc_hash not in existing_hashes:
            try:
                logger.info(f"Preparing new/modified document for batch indexing: {os.path.basename(path)}")
                loader = PyPDFLoader(path)
                documents = loader.load()
                chunks = text_splitter.split_documents(documents)

                for i, chunk in enumerate(chunks):
                    new_chunk_ids.append(create_chunk_id(doc_hash, i))

                    meta = chunk.metadata
                    meta["document_hash"] = doc_hash
                    meta["source"] = os.path.basename(path)
                    new_chunk_metadatas.append(meta)
                    new_chunk_contents.append(chunk.page_content)

            except Exception as e:
                logger.error(f"Error preparing document {path} for indexing: {e}")
                return 0

        if len(new_chunk_ids) >= BATCH_SIZE:
            logger.info(f"Adding a batch of {len(new_chunk_ids)} new chunks to the collection.")
            collection.add(documents=new_chunk_contents, metadatas=new_chunk_metadatas, ids=new_chunk_ids)
            new_chunk_ids.clear()
            new_chunk_contents.clear()
            new_chunk_metadatas.clear()

    if new_chunk_contents:
        logger.info(f"Adding {len(new_chunk_contents)} new chunks to the collection in one batch.")
        try:
            collection.add(documents=new_chunk_contents, metadatas=new_chunk_metadatas, ids=new_chunk_ids)
        except Exception as e:
            logger.error(f"Error adding new chunks to the collection: {e}")
            return 0

    logger.info(f"Ingestion Sync Complete. {len(new_chunk_contents)} new chunks indexed. Total chunks in DB: {collection.count()}")
    return collection.count()


if __name__ == "__main__":
    process_and_index_documents()
