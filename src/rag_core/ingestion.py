from ast import mod
import os
import torch
import glob
import logging

from typing import Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from chromadb import HttpClient, Settings


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Config ---
CHROMA_HOST = os.environ.get("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", 8000))

COLLECTION_NAME = "rag_documents_collection"
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", 200))


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

def process_and_index_documents(data_dir: str = "app/src/data") -> int:
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
	
	try:
		documents = []
		for file in files:
			logger.info(f"Processing {file}")
			loader = PyPDFLoader(file)
			documents.extend(loader.load())
		
		text_splitter = RecursiveCharacterTextSplitter(
			chunk_size=CHUNK_SIZE,
			chunk_overlap=CHUNK_OVERLAP,
			separators=["\n\n", "\n", " ", ""]
		)
		chunks = text_splitter.split_documents(documents)
		logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks")

		Chroma.from_documents(
			documents=chunks,
			embedding=get_embeddings(),
			collection_name=COLLECTION_NAME,
			client=client,
			collection_metadata={"hnsw:space": "cosine"}
		)

		logger.info(f"Indexing over. Indexed {len(chunks)} chunks.")
		return len(chunks)
	
	except Exception as e:
		logger.error(f"Error indexing documents: {e}")
		return 0

if __name__ == "__main__":
	process_and_index_documents()
