import os
import json
import httpx
import asyncio
import logging

from typing import List, Dict, Any, Tuple, Optional, AsyncGenerator
from pydantic import BaseModel

from langchain_community.vectorstores import Chroma
from langchain.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from langchain.retrievers.document_compressors.cross_encoder_rerank import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder


from ingestion import get_chroma_client, get_embeddings, COLLECTION_NAME


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Config ---
LLM_MODEL=os.environ.get("LLM_MODEL", "llama-3.1-8b-instant")
LLM_GATEWAY_URL = os.environ.get("LLM_GATEWAY_URL", "http://llm-gateway:8002/chat")
MAX_CONTEXT_TOKENS = int(os.environ.get("MAX_CONTEXT_TOKENS", 4000))
LLM_STRICT_RAG = os.environ.get("LLM_STRICT_RAG", True).lower() == "true"

CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 1000))
RERANKER_MODEL = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RERANKER_THRESHOLD = float(os.environ.get("RERANKER_THRESHOLD", 0.6))

MAX_RETRIES = 3


# --- Pydantic models ---
class Message(BaseModel):
	role: str
	content: str

class LLMRequest(BaseModel):
	messages: List[Message]
	model: str


def initialize_retrievers() -> Optional[ContextualCompressionRetriever]:
	"""
	Initialize the retrievers (Dense and Sparse) and combine them with RRF.
	"""
	client = get_chroma_client()
	if not client:
		logger.error("Error connecting to ChromaDB")
		return None
	
	logger.info("Initializing retrievers...")
	try:
		embedding_function = get_embeddings()
		if not embedding_function:
			logger.error("Error loading embeddings model")
			return None
		
		vectorstore = Chroma(
			collection_name=COLLECTION_NAME,
			client=client,
			embedding_function=embedding_function
		)

		dense_retriever = vectorstore.as_retriever(
			search_type="similarity",
			search_kwargs={"k": 10}
		)

		if vectorstore._collection.count() == 0:
			logger.warning("No indexed documents, skipping sparse retriever.")
			return EnsembleRetriever(
				retrievers=[dense_retriever],
				weights=[1.0],
				c=100
			)

		all_documents = client.get_collection(COLLECTION_NAME).get(include=['documents', 'metadatas'])
		docs = [Document(page_content=doc, metadata=meta) for doc, meta in zip(all_documents["documents"], all_documents["metadatas"])]

		sparse_retriever = BM25Retriever.from_documents(
			documents=docs,
			k=10
		)

		ensemble_retriever = EnsembleRetriever(
			retrievers=[dense_retriever, sparse_retriever],
			weights=[0.5, 0.5],
			c=100
		)
		logger.info("Hybrid RRF EnsembleRetriever initialized.")

		reranker = HuggingFaceCrossEncoder(
			model_name=RERANKER_MODEL,
			model_kwargs={'device': get_embeddings().model_kwargs.get('device', 'cpu')}
			)
		compressor = CrossEncoderReranker(
			model=reranker,
			top_n=10
		)
		compression_retriever = ContextualCompressionRetriever(
			base_compressor=compressor,
			base_retriever=ensemble_retriever
		)
		
		logger.info(f"Hybrid RRF wrapped with Cross-Encoder Reranker ({RERANKER_MODEL}).")
		return compression_retriever
	
	except Exception as e:
		logger.error(f"Error initializing retrievers: {e}")
		return None
	
_EMSEMBLE_RETRIEVER: Optional[EnsembleRetriever] = None
def get_ensemble_retriever() -> Optional[EnsembleRetriever]:
	"""
	Get the ensemble retriever.
	"""
	global _EMSEMBLE_RETRIEVER
	if _EMSEMBLE_RETRIEVER is None:
		_EMSEMBLE_RETRIEVER = initialize_retrievers()
	return _EMSEMBLE_RETRIEVER

def build_prompt_with_context(query: str, context: List[str], metadatas: List[Dict[str, str]], history: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, Any]]]:
	"""
	Build the final prompt to send to the LLM, including RAG context and history.

	Args:
		query: user's query.
		context: Chunks of documents retrieved.
		history: chat history.

	Returns:
		A Tuple with the system instruction and the list of final messages.
	"""

	context_map = []
	for i, (text_chunk) in enumerate(context):
		metadata = metadatas[i] if i < len(metadatas) else {"source": "N/A", "page": "N/A"}
		context_map.append(f"Content: {text_chunk} (Source: {metadata['source']} [Page {metadata['page']}])")
	context = "\n\n".join(context_map)

	if LLM_STRICT_RAG:
		strict_rule = ("If the answer is not found in the CONTEXT, you must explicitly state: 'Sorry, I cannot answer this question as the information is not available in my reference documents.'")
	else:
		strict_rule = ("If the answer is not found in the CONTEXT, you must answer using your own knowledge but by basing yourself on and favoring the answers found in the CONTEXT.")
	
	system_instruction = (
		"You are Michel, an expert RAG (Retrieval-Augmented Generation) assistant, specializing in document analysis. Your objective is to provide factual, accurate, and concise answers mainly based on the reference documents provided below.\n\n"
		"--- REFERENCE CONTEXT ---\n"
		f"{context}\n"
		"--- END OF REFERENCE CONTEXT ---\n"
		"Rules:\n"
		"1. If the answer is fully contained within the CONTEXT, answer comprehensively using the CONTEXT.\n"
		"2. When referencing a fact, insert the citation EXACTLY as follows: (Source: FILENAME [Page NUMBER]) immediately after the sentence or paragraph.\n"
		f"3. {strict_rule}\n"
	)
	messages = [
		{"role": "system", "content": system_instruction},	
	]
	for message in history:
		messages.append(message)
	messages.append({"role": "user", "content": query})
	return system_instruction, messages

async def async_retry_post(
		url: str,
		payload: Dict[str, Any],
		max_retries: int = MAX_RETRIES
) -> httpx.Response:
	"""
	Try to send and HTTP POST Request with Retry and Exponential Backoff.
	
	Args:
		url: URL from the service to call.
		payload: content of the JSON request to send.
		max_retries: Maximal number of tries.

	Returns:
		httpx.Response if request is successful.
	
	Raises:
		httpx.HTTPStatusError: if every try fails or if fatal error.
	"""

	async with httpx.AsyncClient(timeout=120.0) as client:
		for attempt in range(max_retries):
			try:
				response = await client.post(url, json=payload)
				response.raise_for_status()
				return response
			
			except httpx.RequestError as e:
				if 400 <= e.response.status_code < 500:
					logger.error(f"Fatal client error (Status {e.response.status_code})")
					raise e
				delay = 0.5 * (2 ** attempt)
				logger.warning(
					f"HTTP request failed (Status {e.response.status_code} or Timeout). "
                    f"Retrying in {delay:.2f}s (Attempt {attempt + 1}/{max_retries})."
				)
				await asyncio.sleep(delay)
		
			except httpx.RequestError as e:
				delay = 0.5 * (2 ** attempt)
				logger.warning(
					f"HTTP request failed (Status {e.response.status_code} or Timeout). "
                    f"Retrying in {delay:.2f}s (Attempt {attempt + 1}/{max_retries})."
				)
				await asyncio.sleep(delay)
			
		logger.error(f"HTTP request permanently failed after {max_retries} attempts.")
		raise httpx.RequestError("Failed to communicate with LLM Gateway after multiple retries.")

async def orchestrate_rag_flow(query: str, history: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
	"""
	Execute the whole RAG flow: Retrieval, Context Building and LLm call.
	
	Args:
		query: user's query.
		history: chat history.

	Returns:
		A dict containing LLM's answer and the retrieval's metadata.
	"""
	logger.info(f"Starting RAG flow for query: {query[:50]}...")

	retriever = get_ensemble_retriever()
	if retriever is None:
		logger.error("Cannot retrieve retriever.")
		yield json.dumps({"type": "error", "content": "System Error: Error connecting to ChromaDB."}) + '\n'
	
	retrieved_docs: List[Document] = retriever.invoke(query)
	logger.info(f"Retrieved {len(retrieved_docs)} chunks of documents.")
	# filtered_docs = []
	# for doc in retrieved_docs:
	# 	if doc.metadata.get('relevance_score') >= RERANKER_THRESHOLD:
	# 		filtered_docs.append(doc)
	# logger.info(f"Filtered docs: {len(filtered_docs)} / {len(retrieved_docs)} remaining after thresholding.")
	# retrieved_docs = filtered_docs

	max_chunks = MAX_CONTEXT_TOKENS // CHUNK_SIZE
	context_texts = []
	source_metadatas = []
	
	for doc in retrieved_docs:
		if len(context_texts) < max_chunks:
			source_metadatas.append({"source": doc.metadata.get("source", "N/A"), "page": doc.metadata.get("page", "N/A")})
			context_texts.append(doc.page_content.replace('\udcc3', ' ').replace('\xa0', ' ').strip())
		else:
			break
	if not context_texts:
		logger.warning("No relevant documents found.")
	unique_metadatas = []
	for metadata in source_metadatas:
		if metadata not in unique_metadatas:
			unique_metadatas.append(metadata)

	system_instruction, messages = build_prompt_with_context(query, context_texts, unique_metadatas, history)
	full_response = ""
	try:
		request_data = LLMRequest(
			messages=messages,
			model=LLM_MODEL
		)
		async with httpx.AsyncClient(timeout=120.0) as client:
			response = await async_retry_post(LLM_GATEWAY_URL, request_data.model_dump())
			async for chunk in response.aiter_lines():
				if chunk:
					try:
						data = json.loads(chunk)
						text_chunk = data.get("text", "")
						if text_chunk:
							full_response += text_chunk
							text_chunk_data = json.dumps({"type": "text", "content": text_chunk}) + "\n"
							yield text_chunk_data
					except json.JSONDecodeError:
						continue
		logger.info("RAG flow completed.")

	except httpx.RequestError as e:
		logger.error(f"Request failed: {e}")
		yield json.dumps({"type": "error", "content": str(e)}) + '\n'
	except Exception as e:
		logger.error(f"An unexpected error occurred: {e}")
		yield json.dumps({"type": "error", "content": str(e)}) + '\n'