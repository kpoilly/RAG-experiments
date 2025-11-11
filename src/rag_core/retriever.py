import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
import tiktoken
from langchain.chains import LLMChain
from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import EncoderBackedStore
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_community.storage import SQLStore
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_postgres.vectorstores import PGVector

from config import settings as env
from ingestion import get_embeddings
from models import ExpandedQueries, LLMRequest
from utils import async_retry_post, format_history_for_prompt, value_deserializer, value_serializer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- Init & Component Getters ---
with open("/app/prompts/system.json", "r") as f:
    SYSTEM_PROMPTS = json.load(f)
with open("/app/prompts/query_expansion.json", "r") as f:
    QUERY_EXP_PROMPTS = json.load(f)


_PDR_RETRIEVER: Optional[ParentDocumentRetriever] = None
_RERANKER: Optional[HuggingFaceCrossEncoder] = None
_LLM_QUERY_GEN: Optional[ChatOpenAI] = None
_QUERY_EXPANSION_CHAIN: Optional[LLMChain] = None


async def get_retriever(refresh: bool = False) -> Tuple[Optional[ParentDocumentRetriever], Optional[HuggingFaceCrossEncoder]]:
    global _PDR_RETRIEVER, _RERANKER

    if _PDR_RETRIEVER is not None and not refresh:
        return _PDR_RETRIEVER, _RERANKER

    logger.info(f"Initializing retriever... (refresh={refresh})")
    embedder = get_embeddings()
    vector_store = PGVector(collection_name=env.COLLECTION_NAME, connection=env.DB_URL, embeddings=embedder, async_mode=True)
    doc_store = SQLStore(db_url=env.DB_URL, namespace=f"{env.COLLECTION_NAME}_parents", async_mode=True)
    store = EncoderBackedStore(doc_store, key_encoder=lambda key: key, value_serializer=value_serializer, value_deserializer=value_deserializer)

    _PDR_RETRIEVER = ParentDocumentRetriever(vectorstore=vector_store, docstore=store, child_splitter=RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50))

    logger.info("Loading reranker model...")
    _RERANKER = HuggingFaceCrossEncoder(model_name=env.RERANKER_MODEL, model_kwargs={"device": embedder.client.device, "trust_remote_code": True})
    logger.info("Reranker model loaded.")

    logger.info("Parent Document Retriever initialized.")
    return _PDR_RETRIEVER, _RERANKER


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

        output_parser = PydanticOutputParser(pydantic_object=ExpandedQueries)
        prompt = PromptTemplate(
            template=QUERY_EXP_PROMPTS["instructions"],
            input_variables=["question", "chat_history"],
            partial_variables={"format_instructions": output_parser.get_format_instructions()},
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

    retriever, reranker = await get_retriever()
    if retriever is None:
        logger.error("Cannot retrieve retriever.")
        yield json.dumps({"type": "error", "content": "System Error: Error connecting to DB."}) + "\n"
        return

    # --- Contextual Query Expansion ---
    query_expansion_chain = get_query_expansion_chain()
    if query_expansion_chain is None:
        logger.error("Cannot retrieve query expansion chain. Using original query.")
        all_retrieved_docs = await retriever.ainvoke(query)

    else:
        history_str = format_history_for_prompt(history)
        gen_exp_queries = await query_expansion_chain.ainvoke({"question": query, "chat_history": history_str})

        expanded_queries = gen_exp_queries["text"].queries if "text" in gen_exp_queries and hasattr(gen_exp_queries["text"], "queries") else []
        expanded_queries.insert(0, query)
        logger.info(f"Generated {len(expanded_queries)} expanded queries for retrieval : {expanded_queries}")

        # --- Parallel Multi-Query Retrieval ---
        tasks = [retriever.ainvoke(q) for q in expanded_queries]
        all_retrieved_docs = await asyncio.gather(*tasks)

    flat_list = [doc for sublist in all_retrieved_docs for doc in sublist]
    seen_contents = set()
    unique_docs = []
    for doc in flat_list:
        if doc.page_content not in seen_contents:
            seen_contents.add(doc.page_content)
            unique_docs.append(doc)
    retrieved_docs = unique_docs
    logger.info(f"Retrieved {len(retrieved_docs)} chunks of documents.")

    # --- Reranking ---
    MAX_DOCS_TO_RERANK = 15
    if len(retrieved_docs) > MAX_DOCS_TO_RERANK:
        retrieved_docs = retrieved_docs[:MAX_DOCS_TO_RERANK]
        logger.info(f"Limiting to top {MAX_DOCS_TO_RERANK} documents for reranking.")

    if reranker is not None and retrieved_docs:
        logger.info("Reranking documents...")
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

    _, messages = build_prompt_with_context(query, context_texts, unique_metadatas, history)
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
