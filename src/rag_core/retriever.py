import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
import tiktoken
import psycopg2
from langchain.chains import LLMChain
from langchain.retrievers import EnsembleRetriever
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from config import settings as env
from ingestion import get_embeddings, get_pg_vector_store
from models import LLMRequest
from utils import async_retry_post, format_history_for_prompt

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- Init & Component Getters ---
with open("/app/prompts/system.json", "r") as f:
    SYSTEM_PROMPTS = json.load(f)
with open("/app/prompts/query_expansion.json", "r") as f:
    QUERY_EXP_PROMPTS = json.load(f)


def initialize_retrievers() -> Tuple[Optional[EnsembleRetriever], Optional[HuggingFaceCrossEncoder]]:
    """
    Initialize the retrievers (Dense and Sparse) and combine them with RRF.
    """
    logger.info("Initializing retrievers...")
    try:
        embedding_function = get_embeddings()
        if not embedding_function:
            logger.error("Error loading embeddings model")
            return None

        logger.info("Initializing cross-encoder reranker...")
        reranker = HuggingFaceCrossEncoder(model_name=env.RERANKER_MODEL, model_kwargs={"device": embedding_function.model_kwargs.get("device", "cpu")})
        logger.info(f"Cross-Encoder Reranker model ({env.RERANKER_MODEL}) initialized.")

        vectorstore = get_pg_vector_store()
        dense_retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 8})

        all_documents = []
        try:
            conn = psycopg2.connect(env.DB_URL_PSYCOG2)
            cur = conn.cursor()

            cur.execute(f"SELECT COUNT(*) FROM {env.TABLE_NAME};")
            doc_count = cur.fetchone()[0]

            if doc_count == 0:
                logger.warning("No documents found in the database, skipping sparse retriever.")
                cur.close()
                conn.close()
                return EnsembleRetriever(retrievers=[dense_retriever], weights=[1.0], c=100), reranker

            cur.execute(f"SELECT page_content, metadata FROM {env.TABLE_NAME};")
            all_documents_data = cur.fetchall()
            all_documents = [Document(page_content=row[0], metadata=row[1]) for row in all_documents_data]

            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error fetching documents for sparse retriever: {e}")
            return EnsembleRetriever(retrievers=[dense_retriever], weights=[1.0], c=100), reranker

        sparse_retriever = BM25Retriever.from_documents(documents=all_documents, k=8)
        ensemble_retriever = EnsembleRetriever(retrievers=[dense_retriever, sparse_retriever], weights=[0.5, 0.5], c=100)
        logger.info("Hybrid RRF EnsembleRetriever initialized.")
        return ensemble_retriever, reranker

    except Exception as e:
        logger.error(f"Error initializing retrievers: {e}")
        return None


_EMSEMBLE_RETRIEVER: Optional[EnsembleRetriever] = None
_RERANKER: Optional[HuggingFaceCrossEncoder] = None
_LLM_QUERY_GEN: Optional[ChatOpenAI] = None
_QUERY_EXPANSION_CHAIN: Optional[LLMChain] = None


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


def get_llm_query_gen() -> Optional[ChatOpenAI]:
    """
    Gets the non-streaming LLM instance for internal tasks like query generation.
    """
    global _LLM_QUERY_GEN
    if _LLM_QUERY_GEN is None:
        logger.info("Initializing LLM query generator...")
        _LLM_QUERY_GEN = ChatOpenAI(
            model_name=env.LLM_MODEL, openai_api_base=env.LLM_GATEWAY_URL.replace("/chat", ""), openai_api_key="not needed", temperature=0.0, streaming=False
        )
        logger.info("LLM query generator initialized.")
    return _LLM_QUERY_GEN


def get_query_expansion_chain() -> Optional[LLMChain]:
    """
    Get the query expansion chain.
    """
    global _QUERY_EXPANSION_CHAIN
    if _QUERY_EXPANSION_CHAIN is None:
        logger.info("Initializing query expansion chain...")
        llm = get_llm_query_gen()
        if not llm:
            logger.error("Cannot initialize query expansion chain without LLM.")
            return None

        output_parser = JsonOutputParser()
        prompt = PromptTemplate(
            template=QUERY_EXP_PROMPTS["instructions"],
            input_variables=["question", "chat_history"],
            partial_variables={"format_instructions": QUERY_EXP_PROMPTS["format_instructions"]},
        )

        _QUERY_EXPANSION_CHAIN = LLMChain(llm=llm, prompt=prompt, output_parser=output_parser)
        logger.info("Query expansion chain initialized.")
    return _QUERY_EXPANSION_CHAIN


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
    system_instruction = template.format(context=context, strict_rule=SYSTEM_PROMPTS["strict_rule_true"] if env.LLM_STRICT_RAG else SYSTEM_PROMPTS["strict_rule_false"])
    messages = [{"role": "system", "content": system_instruction}]
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

    retriever, reranker = get_ensemble_retriever()
    if retriever is None:
        logger.error("Cannot retrieve retriever.")
        yield json.dumps({"type": "error", "content": "System Error: Error connecting to DB."}) + "\n"

    # --- Contextual Query Expansion ---
    query_expansion_chain = get_query_expansion_chain()
    if query_expansion_chain is None:
        logger.error("Cannot retrieve query expansion chain. Using original query.")
        all_retrieved_docs = await retriever.ainvoke(query)

    else:
        history_str = format_history_for_prompt(history)
        gen_exp_queries = await query_expansion_chain.ainvoke({"question": query, "chat_history": history_str})

        expanded_queries = gen_exp_queries.get("text", {}).get("queries", [])
        expanded_queries.insert(0, query)
        logger.info(f"Generated {len(expanded_queries)} expanded queries for retrieval : {expanded_queries}")

        # --- Parallel Multi-Query Retrieval ---
        tasks = [retriever.ainvoke(q) for q in expanded_queries]
        all_retrieved_docs = await asyncio.gather(*tasks)

    filt_unique_docs = {doc.page_content: doc for docs in all_retrieved_docs for doc in docs}
    retrieved_docs = list(filt_unique_docs.values())
    logger.info(f"Retrieved {len(retrieved_docs)} chunks of documents.")

    # --- Reranking ---
    MAX_DOCS_TO_RERANK = 15
    if len(retrieved_docs) > MAX_DOCS_TO_RERANK:
        retrieved_docs = retrieved_docs[:MAX_DOCS_TO_RERANK]
        logger.info(f"Limiting to top {MAX_DOCS_TO_RERANK} documents for reranking.")

    if reranker is not None and retrieved_docs:
        pairs = [(query, doc.page_content) for doc in retrieved_docs]
        scores = reranker.score(pairs)
        for doc, score in zip(retrieved_docs, scores):
            doc.metadata["relevance_score"] = score

        reranked_docs = sorted(retrieved_docs, key=lambda x: x.metadata.get("relevance_score", 0.0), reverse=True)
        filtered_docs = [doc for doc in reranked_docs if doc.metadata["relevance_score"] > env.RERANKER_THRESHOLD]
        final_docs = []

        if filtered_docs:
            final_docs = filtered_docs
            logger.info(f"{len(final_docs)} documents remaining after reranking and thresholding.")
        elif reranked_docs:
            final_docs = [reranked_docs[0]]
            logger.warning(
                f"No documents met the threshold of {env.RERANKER_THRESHOLD}. "
                f"Falling back to the single best document with score {reranked_docs[0].metadata['relevance_score']:.4f}."
            )
        retrieved_docs = final_docs

    # --- Context Assembly ---
    tokenizer = tiktoken.get_encoding("cl100k_base")
    context_texts = []
    source_metadatas = []
    current_tokens = 0

    for message in history:
        message_tokens = len(tokenizer.encode(message.get("content", "")))
        current_tokens += message_tokens
    current_tokens += len(tokenizer.encode(query))
    current_tokens += len(
        tokenizer.encode(
            SYSTEM_PROMPTS["instructions"]
            .replace("{context}", "")
            .replace("{strict_rule}", SYSTEM_PROMPTS["strict_rule_true"] if env.LLM_STRICT_RAG else SYSTEM_PROMPTS["strict_rule_false"])
        )
    )

    for doc in retrieved_docs:
        doc_tokens = len(tokenizer.encode(doc.page_content))
        if current_tokens + doc_tokens <= env.MAX_CONTEXT_TOKENS:
            current_tokens += doc_tokens
            source_metadatas.append({"source": doc.metadata.get("source", "N/A"), "page": doc.metadata.get("page", "N/A")})
            context_texts.append(doc.page_content.replace("\udcc3", " ").replace("\xa0", " ").strip())
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
    logging.info(f"Final prompt constructed ({current_tokens} tokens). Invoking LLM...")
    full_response = ""
    try:
        request_data = LLMRequest(messages=messages, model=env.LLM_MODEL)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await async_retry_post(client, env.LLM_GATEWAY_URL, request_data.model_dump())
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
        yield json.dumps({"type": "error", "content": str(e)}) + "\n"
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        yield json.dumps({"type": "error", "content": str(e)}) + "\n"
