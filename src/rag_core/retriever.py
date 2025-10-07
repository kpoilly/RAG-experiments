import os
import json
import httpx
import logging

from typing import List, Dict, Any, Tuple, Optional, AsyncGenerator
from pydantic import BaseModel

from langchain_community.vectorstores import Chroma
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from ingestion import get_chroma_client, get_embeddings, COLLECTION_NAME


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Config ---
LLM_MODEL=os.environ.get("LLM_MODEL", "llama-3.1-8b-instant")
LLM_GATEWAY_URL = os.environ.get("LLM_GATEWAY_URL", "http://llm-gateway:8002/chat")
MAX_CONTEXT_TOKENS = int(os.environ.get("MAX_CONTEXT_TOKENS", 4000))
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 1000))
LLM_STRICT_RAG = os.environ.get("LLM_STRICT_RAG", True).lower() == "true"



# --- Pydantic models ---
class Message(BaseModel):
	role: str
	content: str

class LLMRequest(BaseModel):
	messages: List[Message]
	model: str


def initialize_retrievers() -> Optional[EnsembleRetriever]:
	"""
	Initialize the retrievers (Dense and Sparse) and combine them with RRF.
	"""
	client = get_chroma_client()
	if not client:
		logger.error("Error connecting to ChromaDB")
		return None
	
	logger.info("Initializing retrievers...")
	try:
		vectorstore = Chroma(
			collection_name=COLLECTION_NAME,
			client=client,
			embedding_function=get_embeddings()
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

		all_documents = vectorstore._collection.get(
			ids=vectorstore._collection.get()['ids'],
			include=["documents", "metadatas"]
		)
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
		return ensemble_retriever
	
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

def build_prompt_with_context(query: str, context: List[str], history: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, Any]]]:
	"""
	Build the final prompt to send to the LLM, including RAG context and history.

	Args:
		query: user's query.
		context: Chunks of documents retrieved.
		history: chat history.

	Returns:
		A Tuple with the system instruction and the list of final messages.
	"""

	context_text = "\n\n".join(context)
	if LLM_STRICT_RAG:
		strict_rule = ("If the answer is not found in the CONTEXT, you must explicitly state: 'Sorry, I cannot answer this question as the information is not available in my reference documents.'")
	else:
		strict_rule = ("If the answer is not found in the CONTEXT, you must answer using your own knowledge but by basing yourself on and favoring the answers found in the CONTEXT.")
	system_instruction = (
		"You are an expert RAG (Retrieval-Augmented Generation) assistant, specializing in document analysis. Your objective is to provide factual, accurate, and concise answers mainly based on the reference documents provided below.\n\n"
		"--- REFERENCE CONTEXT ---\n"
		f"{context_text}\n"
		"--- END OF REFERENCE CONTEXT ---\n"
		"Rules:\n"
		"1. If the answer is fully contained within the CONTEXT, answer comprehensively using the CONTEXT.\n"
		f"2. {strict_rule}\n"
	)
	messages = [
		{"role": "system", "content": system_instruction},	
	]
	for message in history:
		messages.append(message)
	messages.append({"role": "user", "content": query})
	return system_instruction, messages

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
		# return {"response": "System Error: Error connecting to ChromaDB.", "source_chunks": []}
		yield json.dumps({"type": "error", "content": "System Error: Error connecting to ChromaDB."}) + '\n'
	
	retrieved_docs: List[Document] = retriever.get_relevant_documents(query)
	logger.info(f"Retrieved {len(retrieved_docs)} documents.")

	max_chunks = MAX_CONTEXT_TOKENS // CHUNK_SIZE
	context_texts = []
	source_metadatas = []
	
	for doc in retrieved_docs:
		if len(context_texts) < max_chunks:
			source_metadatas.append(doc.metadata.get("source", "N/A"))
			context_texts.append(doc.page_content.replace('\udcc3', ' ').replace('\xa0', ' ').strip())
		else:
			break
	if not context_texts:
		logger.warning("No relevant documents found.")
	unique_metadatas = []
	for metadata in source_metadatas:
		if metadata not in unique_metadatas:
			unique_metadatas.append(metadata)

	system_instruction, messages = build_prompt_with_context(query, context_texts, history)
	full_response = ""
	try:
		request_data = LLMRequest(
			messages=messages,
			model=LLM_MODEL
		)
		# async with httpx.AsyncClient(timeout=60.0) as client:
		# 	response = await client.post(LLM_GATEWAY_URL, json=request_data.model_dump())
		# 	response.raise_for_status()
		# 	llm_response = response.json()
		# 	final_response = llm_response.get("response", "Error: No response from LLM.")
		# 	logger.info("RAG flow completed.")
		# 	return {"response": final_response, "source_chunks": unique_metadatas}
		async with httpx.AsyncClient(timeout=120.0) as client:
			async with client.stream("POST", LLM_GATEWAY_URL, json=request_data.model_dump()) as response:
				response.raise_for_status()
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
		# return {"response": "Error: Request failed.", "source_chunks": []}
	except Exception as e:
		logger.error(f"An unexpected error occurred: {e}")
		yield json.dumps({"type": "error", "content": str(e)}) + '\n'
		# return {"response": "Error: An unexpected error occurred.", "source_chunks": []}