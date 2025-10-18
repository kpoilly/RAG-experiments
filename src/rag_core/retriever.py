import os
import json
import re
import httpx
import logging
import tiktoken

from typing import List, Dict, Any, Tuple, Optional, AsyncGenerator

from sentence_transformers.util import cos_sim
from langchain_community.vectorstores import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain.retrievers import EnsembleRetriever
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.chains import LLMChain
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import CommaSeparatedListOutputParser
from langchain_openai import ChatOpenAI

from models import LLMRequest
from utils import async_retry_post
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
RERANKER_THRESHOLD = float(os.environ.get("RERANKER_THRESHOLD", 0.4))


# --- Init ---
with open("/app/prompts/system.json", "r") as f:
	SYSTEM_PROMPTS = json.load(f)
with open("/app/prompts/multi_query.json", "r") as f:
	MULTI_QUERY_PROMPTS = json.load(f)

def initialize_retrievers() -> Tuple[Optional[EnsembleRetriever], Optional[HuggingFaceCrossEncoder]]:
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
		logger.info("Initializing cross-encoder reranker...")
		reranker = HuggingFaceCrossEncoder(
			model_name=RERANKER_MODEL,
			model_kwargs={'device': embedding_function.model_kwargs.get('device', 'cpu')}
			)
		logger.info(f"Cross-Encoder Reranker model ({RERANKER_MODEL}) initialized.")
		return ensemble_retriever, reranker
	
	except Exception as e:
		logger.error(f"Error initializing retrievers: {e}")
		return None
	
_EMSEMBLE_RETRIEVER: Optional[EnsembleRetriever] = None
_RERANKER: Optional[HuggingFaceCrossEncoder] = None
def get_ensemble_retriever(refresh: bool = False) -> Optional[EnsembleRetriever]:
	"""
	Get the ensemble retriever.
	"""
	logger.info("Getting ensemble retriever...")
	global _EMSEMBLE_RETRIEVER, _RERANKER
	if _EMSEMBLE_RETRIEVER is None or refresh:
		_EMSEMBLE_RETRIEVER, _RERANKER = initialize_retrievers()
	logger.info("Ensemble retriever retrieved.")
	return _EMSEMBLE_RETRIEVER, _RERANKER

_LLM_QUERY_GEN: Optional[ChatOpenAI] = None
def get_llm_query_gen() -> Optional[ChatOpenAI]:
	"""
	Get the LLM query generator.
	"""
	global _LLM_QUERY_GEN
	if _LLM_QUERY_GEN is None:
		logger.info("Initializing LLM query generator...")
		llm = ChatOpenAI(
			model_name=LLM_MODEL,
			openai_api_base=LLM_GATEWAY_URL.replace("/chat", ""),
			openai_api_key="not needed",
			temperature=0.0,
			streaming=False
		)
		query_prompt = PromptTemplate(
			input_variables=["question"],
			template=MULTI_QUERY_PROMPTS["instructions"]
		)
		output_parser = CommaSeparatedListOutputParser()
		_LLM_QUERY_GEN = LLMChain(llm=llm, prompt=query_prompt, output_parser=output_parser)
		logger.info("LLM query generator initialized.")
	return _LLM_QUERY_GEN


# --- RAG flow ---
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

	template = SYSTEM_PROMPTS["instructions"]
	system_instruction = template.format(
		context=context,
		strict_rule=SYSTEM_PROMPTS["strict_rule_true"] if LLM_STRICT_RAG else SYSTEM_PROMPTS["strict_rule_false"]
	)
	messages = [
		{"role": "system", "content": system_instruction}
	]
	for message in history:
		messages.append(message)
	messages.append({"role": "user", "content": query})
	return system_instruction, messages

def filter_docs_to_rerank(docs: List[Document], query: str, MAX_DOCS_TO_RERANK: int):
	logger.info(f"Pre-ranking {len(docs)} documents with Bi-Encoder to select top {MAX_DOCS_TO_RERANK}...")

	embedder = get_embeddings()
	query_embedding = embedder.embed_query(query)
	doc_embeddings = embedder.embed_documents([doc.page_content for doc in docs])
	similarities = cos_sim(query_embedding, doc_embeddings).flatten()

	sorted_docs = sorted(list(zip(docs, similarities.tolist())), key=lambda x: x[1], reverse=True)
	docs_to_rerank = [doc for doc, score in sorted_docs[:MAX_DOCS_TO_RERANK]]
	logger.info(f"Top {len(docs_to_rerank)} documents selected for final re-ranking.")
	return docs_to_rerank

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

	retriever, reranker = get_ensemble_retriever()
	if retriever is None:
		logger.error("Cannot retrieve retriever.")
		yield json.dumps({"type": "error", "content": "System Error: Error connecting to ChromaDB."}) + '\n'
	
	llm = get_llm_query_gen()
	multi_query_retriever = MultiQueryRetriever(
		retriever=retriever,
		llm_chain=llm
	)
	retrieved_docs: List[Document] = multi_query_retriever.invoke(query)
	logger.info(f"Retrieved {len(retrieved_docs)} chunks of documents.")

	MAX_DOCS_TO_RERANK = 15
	if len(retrieved_docs) > MAX_DOCS_TO_RERANK:
		retrieved_docs = filter_docs_to_rerank(retrieved_docs, query, MAX_DOCS_TO_RERANK)

	if reranker is not None and retrieved_docs:
		pairs = [(query, doc.page_content) for doc in retrieved_docs]
		scores = reranker.score(pairs)
		for doc, score in zip(retrieved_docs, scores):
			doc.metadata["relevance_score"] = score

		reranked_docs = sorted(
			retrieved_docs,
			key=lambda x: x.metadata.get('relevance_score', 0.0),
			reverse=True
		)
		filtered_docs = [doc for doc in reranked_docs if doc.metadata['relevance_score'] > RERANKER_THRESHOLD]
		final_docs = []

		if filtered_docs:
			final_docs = filtered_docs
			logger.info(f"{len(final_docs)} documents remaining after reranking and thresholding.")
		elif reranked_docs:
			final_docs = [reranked_docs[0]]
			logger.warning(
				f"No documents met the threshold of {RERANKER_THRESHOLD}. "
				f"Falling back to the single best document with score {reranked_docs[0].metadata['relevance_score']:.4f}."
        	)
	retrieved_docs = final_docs

	tokenizer = tiktoken.get_encoding("cl100k_base")
	context_texts = []
	source_metadatas = []
	current_tokens = 0
	
	for doc in retrieved_docs:
		doc_tokens = len(tokenizer.encode(doc.page_content))
		if current_tokens + doc_tokens <= MAX_CONTEXT_TOKENS:
			current_tokens += doc_tokens
			source_metadatas.append({"source": doc.metadata.get("source", "N/A"), "page": doc.metadata.get("page", "N/A")})
			context_texts.append(doc.page_content.replace('\udcc3', ' ').replace('\xa0', ' ').strip())
		else:
			logger.info("Reached max context tokens. Stopping context assembly.")
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
