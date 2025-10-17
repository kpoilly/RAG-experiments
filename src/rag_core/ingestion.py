import os
import torch
import glob
import hashlib
import logging

from typing import Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings

from chromadb import HttpClient, Settings
from chromadb.api.models.Collection import Collection


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Config ---
CHROMA_HOST = os.environ.get("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", 8000))
COLLECTION_NAME = "rag_documents_collection"

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", 200))


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
		_chroma_client = HttpClient(
			host=CHROMA_HOST,
			port=CHROMA_PORT,
			settings=Settings(allow_reset=True)
		)
		_chroma_client.heartbeat()
		logger.info(f"Connected to ChromaDB at {CHROMA_HOST}:{CHROMA_PORT}")
	except Exception as e:
		logger.error(f"Error connecting to ChromaDB: {e}")
		_chroma_client = None
	return _chroma_client

def get_embeddings():
	"""
	Load the embeddings model.
	"""
	device = "cuda" if torch.cuda.is_available() else "cpu"
	logger.info(f"Using device: {device}")
	return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL, model_kwargs={"device": device})

def get_or_create_collection(client: HttpClient, collection_name: str, embedding_function: HuggingFaceEmbeddings) -> Collection:
	"""
	Get or create a Chroma collection.
	"""
	try:
		collection = client.get_collection(collection_name)
		logger.info(f"Collection {collection_name} loaded successfully.")
		return collection
	except Exception:
		logger.info(f"Collection {collection_name} does not exist. Creating...")
		collection = client.create_collection(
			name=collection_name,
			metadata={"hnsw:space": "cosine"}
		)
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
	Loads PDF documents, chunks and index them in ChromaDB

	Args:
		data_dir: path to the data directory.
	Returns:
		total number of indexed documents.
	"""
	logger.info(f"Starting ingestion from {data_dir}...")

	files = glob.glob(os.path.join(data_dir, "*.pdf"))
	if not files:
		logger.error(f"No PDF files found in {data_dir}")
		return 0
	
	client = get_chroma_client()
	if not client:
		logger.error("Error connecting to ChromaDB")
		return 0
	
	embedding_function = get_embeddings()
	if not embedding_function:
		logger.error("Error loading embeddings model")
		return 0
	
	collection = get_or_create_collection(client, COLLECTION_NAME, embedding_function)
	existing_hashes = {
		meta.get('document_hash') for meta in collection.get()['metadatas'] if meta.get('document_hash')
	}

	current_hashes = {}
	for path in files:
		file_hash = calculate_file_hash(path)
		if file_hash:
			current_hashes[file_hash] = path
	
	hashes_to_rm = existing_hashes.difference(set(current_hashes.keys()))
	if hashes_to_rm:
		ids_to_rm = []
		metadatas = collection.get(include=['metadatas'])['metadatas']
		for i, meta in enumerate(metadatas):
			if meta.get('document_hash') in hashes_to_rm:
				ids_to_rm.append(collection.get(include=[])['ids"'][i])
		for hash in hashes_to_rm:
			collection.delete(where={'document_hash': hash})
			logger.info(f"Deleted document chunk with hash {hash} from ChromaDB.")
	
	new_chunks_count = 0
	for doc_hash, path in current_hashes.items():
		if doc_hash not in existing_hashes:
			try:
				logger.info(f"Indexing new/modified document: {os.path.basename(path)}")
				loader = PyPDFLoader(path)
				documents = loader.load()

				text_splitter = RecursiveCharacterTextSplitter(
				chunk_size=CHUNK_SIZE,
				chunk_overlap=CHUNK_OVERLAP,
				separators=["\n\n", "\n", " ", ""],
				)
				chunks = text_splitter.split_documents(documents)

				chunk_ids = []
				chunk_contents = []
				chunk_metadatas = []
				for i, chunk in enumerate(chunks):
					chunk_ids.append(create_chunk_id(doc_hash, i))
					meta = chunk.metadata
					meta["document_hash"] = doc_hash
					meta["source"] = os.path.basename(path)
					chunk_metadatas.append(meta)
					chunk_contents.append(chunk.page_content)
				
				collection.add(
					documents=chunk_contents,
					metadatas=chunk_metadatas,
					ids=chunk_ids
				)
				new_chunks_count += len(chunks)
			
			except Exception as e:
				logger.error(f"Error indexing documents: {e}")
				return 0
	
	logger.info(f"Ingestion Sync Complete. {new_chunks_count} new chunks indexed.")
	return collection.count()


if __name__ == "__main__":
	process_and_index_documents()
