import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_classic.storage import EncoderBackedStore
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_community.storage import SQLStore
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI
from langchain_postgres.vectorstores import PGVector

from config import settings as env
from ingestion import get_embeddings
from models import ExpandedQueries, LLMRequest
from utils import count_tokens, format_history_for_prompt, truncate_history, value_deserializer, value_serializer

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
_QUERY_EXPANSION_CHAIN: Optional[RunnableSequence] = None


def init_components():
    """
    Initialize heavy components (Embedder, Reranker, LLM).
    """
    global _RERANKER, _LLM_QUERY_GEN
    logger.info("Initializing Embedder, Reranker and LLM...")

    embedder = get_embeddings()

    if _RERANKER is None:
        logger.info("Initializing reranker model...")
        _RERANKER = HuggingFaceCrossEncoder(model_name=env.RERANKER_MODEL, model_kwargs={"device": embedder._client.device, "trust_remote_code": True})
        logger.info("Reranker model loaded.")

    if _LLM_QUERY_GEN is None:
        logger.info("Initializing LLM query generator...")
        get_llm_query_gen()
        get_query_expansion_chain()
        logger.info("LLM query generator initialized.")

    logger.info("Embedder, Reranker and LLM chain initialized.")


async def build_retriever():
    """
    Build or refresh the ParentDocumentRetriever.
    """
    global _PDR_RETRIEVER
    logger.info("Building retriever...")

    embedder = get_embeddings()
    vector_store = PGVector(collection_name=env.COLLECTION_NAME, connection=env.DB_URL, embeddings=embedder, async_mode=True)
    doc_store = SQLStore(db_url=env.DB_URL, namespace=f"{env.COLLECTION_NAME}_parents", async_mode=True)
    store = EncoderBackedStore(doc_store, key_encoder=lambda key: key, value_serializer=value_serializer, value_deserializer=value_deserializer)

    _PDR_RETRIEVER = ParentDocumentRetriever(vectorstore=vector_store, docstore=store, child_splitter=RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50))
    logger.info("Parent Document Retriever is ready.")


async def get_retriever(refresh: bool = False) -> Tuple[Optional[ParentDocumentRetriever], Optional[HuggingFaceCrossEncoder]]:
    """
    Get the ParentDocumentRetriever and Reranker, initializing them if necessary.

    Args:
        refresh: Whether to refresh/rebuild the retriever.

    Returns:
        A tuple containing the ParentDocumentRetriever and the Reranker.
    """
    global _PDR_RETRIEVER, _RERANKER

    if _PDR_RETRIEVER is None:
        await build_retriever()

    return _PDR_RETRIEVER, _RERANKER


def get_llm_query_gen() -> Optional[ChatOpenAI]:
    """
    Gets the non-streaming LLM instance for internal tasks like query generation.
    """
    global _LLM_QUERY_GEN
    if _LLM_QUERY_GEN is None:
        _LLM_QUERY_GEN = ChatOpenAI(model_name=env.LLM_MODEL, openai_api_base=env.LLM_GATEWAY_URL, openai_api_key="not needed", temperature=0.0, streaming=False)
    return _LLM_QUERY_GEN


def get_query_expansion_chain() -> Optional[RunnableSequence]:
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

        _QUERY_EXPANSION_CHAIN = prompt | llm | output_parser
        logger.info("Query expansion chain initialized.")
    return _QUERY_EXPANSION_CHAIN


# --- RAG flow ---
async def expand_query(query: str, history: List[Dict[str, str]]) -> List[str]:
    """
    Expands the original query into multiple related queries using a language model.

    Args:
        query: The user's original query.
        history: The chat history.

    Returns:
        A list of queries, with the original query always as the first element.
        Returns [query] if expansion fails.
    """
    query_expansion_chain = get_query_expansion_chain()
    if query_expansion_chain is None:
        logger.error("Cannot retrieve query expansion chain. Using original query.")
        return [query]

    try:
        history_str = format_history_for_prompt(history)
        gen_exp_queries = await query_expansion_chain.ainvoke({"question": query, "chat_history": history_str})
        expanded_queries = gen_exp_queries.queries if hasattr(gen_exp_queries, "queries") else []
        logger.info(f"Generated {len(expanded_queries)} expanded queries: {expanded_queries}")
        return [query] + expanded_queries
    except Exception as e:
        logger.warning(f"Query expansion failed: {e}. Using original query.")
        return [query]


async def retrieve_and_deduplicate_documents(retriever: ParentDocumentRetriever, queries: List[str]) -> List:
    """
    Retrieves documents for multiple queries in parallel and removes duplicates.

    Args:
        retriever: The document retriever instance.
        queries: A list of queries to retrieve documents for.

    Returns:
        A list of unique documents.
    """
    tasks = [retriever.ainvoke(q) for q in queries]
    nested_docs = await asyncio.gather(*tasks)

    flat_list = [doc for sublist in nested_docs for doc in sublist]

    seen_contents = set()
    unique_docs = []
    for doc in flat_list:
        if doc.page_content not in seen_contents:
            seen_contents.add(doc.page_content)
            unique_docs.append(doc)

    logger.info(f"Retrieved {len(unique_docs)} unique document chunks.")
    return unique_docs


def rerank_documents(query: str, docs: List, reranker: Optional[HuggingFaceCrossEncoder] = None, threshold: float = env.RERANKER_THRESHOLD) -> List:
    """
    Reranks a list of documents based on relevance to the query.

    Args:
        query: The user's query.
        docs: The list of documents to rerank.
        reranker: The reranker model instance.

    Returns:
        The sorted and filtered list of documents. Returns original docs if reranker is unavailable.
    """
    if not reranker or not docs:
        return docs
    if threshold is None:
        threshold = env.RERANKER_THRESHOLD

    MAX_DOCS_TO_RERANK = 15
    docs_to_rerank = docs[:MAX_DOCS_TO_RERANK]
    if len(docs) > MAX_DOCS_TO_RERANK:
        logger.info(f"Limiting to top {MAX_DOCS_TO_RERANK} documents for reranking.")

    logger.info(f"Reranking documents... (Threshold: {threshold})")
    pairs = [(query, doc.page_content) for doc in docs_to_rerank]
    scores = reranker.score(pairs)

    reranked_results = sorted(zip(docs_to_rerank, scores), key=lambda x: x[1], reverse=True)
    filtered_results = [result for result in reranked_results if result[1] > threshold]

    if filtered_results:
        final_docs = [doc for doc, score in filtered_results]
        logger.info(f"{len(final_docs)} documents passed the reranker threshold of {threshold}.")
    elif reranked_results:
        final_docs = [reranked_results[0][0]]
        logger.warning(f"No documents met the threshold of {threshold}. " f"Falling back to the single best document with score {reranked_results[0][1]:.4f}.")
    else:
        final_docs = []

    return final_docs


def build_context_from_docs(docs: List, context_budget: int) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Build the context string and metadata from documents within a token budget.
    """
    context_texts = []
    source_metadatas = []
    current_context_tokens = 0

    for doc in docs:
        doc_tokens = count_tokens(doc.page_content)
        if current_context_tokens + doc_tokens > context_budget:
            logger.info("Reached RAG context token budget. Stopping context assembly.")
            break

        current_context_tokens += doc_tokens
        context_texts.append(doc.page_content.replace("\udcc3", " ").replace("\xa0", " ").strip())
        source_metadatas.append({"source": doc.metadata.get("source", "N/A"), "page": doc.metadata.get("page", "N/A")})

    unique_metadatas = [dict(t) for t in {tuple(d.items()) for d in source_metadatas}]
    return context_texts, unique_metadatas


def build_prompt_with_context(
    query: str, context: List[str], metadatas: List[Dict[str, str]], history: List[Dict[str, str]], strict_rule: str
) -> Tuple[str, List[Dict[str, Any]]]:
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
    system_instruction = template.format(context=context, strict_rule=strict_rule)
    messages = [{"role": "system", "content": system_instruction}]
    messages.extend(history)
    messages.append({"role": "user", "content": query})

    return system_instruction, messages


def build_final_prompt(query: str, history: List[Dict[str, str]], docs: List, strict: bool) -> Tuple[List[Dict[str, Any]], int]:
    """
    Assembles the final prompt for the LLM, managing token budgets for context and history.

    Args:
        query: The user's query.
        history: The chat history.
        docs: The retrieved and reranked documents.
        strict: The strict RAG mode flag.

    Returns:
        A tuple containing:
        - The final list of messages for the LLM API.
        - The total number of tokens in the final prompt.
    """
    # Defining budgets
    RESPONSE_BUDGET = int(env.LLM_MAX_CONTEXT_TOKENS * 0.1)
    CONTEXT_BUDGET = int(env.LLM_MAX_CONTEXT_TOKENS * 0.6)
    SAFETY_MARGIN = 0.95

    # Calculating token counts
    query_tokens = count_tokens(query)
    strict_rule = SYSTEM_PROMPTS["strict_rule_true"] if strict else SYSTEM_PROMPTS["strict_rule_false"]
    prompt_template = SYSTEM_PROMPTS["instructions"]
    prompt_template_tokens = count_tokens(prompt_template + strict_rule)

    # Truncate history if necessary to fit budget
    history_budget = (env.LLM_MAX_CONTEXT_TOKENS * SAFETY_MARGIN) - (query_tokens + prompt_template_tokens + CONTEXT_BUDGET + RESPONSE_BUDGET)
    final_history = truncate_history(history, history_budget)
    history_tokens = sum(count_tokens(message.get("content", "")) for message in final_history)

    # Build context from documents
    context_texts, unique_metadatas = build_context_from_docs(docs, CONTEXT_BUDGET)
    context_tokens = sum(count_tokens(text) for text in context_texts)
    if not context_texts:
        logger.warning("No relevant documents were added to the final context.")

    # Assemble final prompt
    system_instructions, messages = build_prompt_with_context(query, context_texts, unique_metadatas, final_history, strict_rule)
    total_tokens = query_tokens + history_tokens + context_tokens + prompt_template_tokens
    logger.info(
        f"Final prompt assembled. Tokens - Total: {total_tokens}, Query: {query_tokens}, "
        f"History: {history_tokens}, Context: {context_tokens}, Template: {prompt_template_tokens}"
    )

    return messages, total_tokens


async def stream_llm_response(messages: List[Dict[str, Any]], token_count: int, temp: Optional[float] = None) -> AsyncGenerator[str, None]:
    """
    Constructs the final prompt, calls the LLM, and streams the response.

    Args:
        query: The user's query.
        history: The chat history.
        context_texts: The assembled context from documents.
        unique_metadatas: The metadata of the context documents.
        token_count: The total token count for logging.

    Yields:
        JSON strings representing chunks of the LLM's response or an error.
    """
    temp = temp if temp is not None else env.LLM_TEMPERATURE
    logger.info(f"Invoking LLM... (model: {env.LLM_MODEL}, temp: {temp}, tokens: {token_count})")

    try:
        request_data = LLMRequest(messages=messages, model=env.LLM_MODEL, temperature=temp, stream=True)
        request_payload = request_data.model_dump(exclude_none=True)
        gateway_url = env.LLM_GATEWAY_URL + "/chat/completions"
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", gateway_url, json=request_payload) as response:
                response.raise_for_status()
                async for text_chunk in response.aiter_text():
                    yield text_chunk
        logger.info("LLM stream completed.")

    except httpx.RequestError as e:
        logger.error(f"Request failed: {e}")
        yield json.dumps({"type": "error", "content": str(e)}) + "\n"
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        yield json.dumps({"type": "error", "content": str(e)}) + "\n"


async def orchestrate_rag_flow(
    query: str, history: List[Dict[str, str]], temp: float = env.LLM_TEMPERATURE, strict: bool = env.LLM_STRICT_RAG, rerank_threshold: float = env.RERANKER_THRESHOLD
) -> AsyncGenerator[str, None]:
    """
    Executes the entire RAG flow by orchestrating calls to specialized functions.

    Args:
        query: The user's query.
        history: The chat history.

    Yields:
        A stream of JSON strings containing the LLM's answer or an error.
    """
    strict_mode = strict if strict is not None else env.LLM_STRICT_RAG
    logger.info(f"Starting RAG flow for query: {query[:50]}... (strict mode: {strict_mode}))")

    retriever, reranker = await get_retriever()
    if retriever is None:
        logger.error("Cannot retrieve retriever.")
        yield json.dumps({"type": "error", "content": "System Error: Retriever not available."}) + "\n"
        return

    expanded_queries = await expand_query(query, history)
    retrieved_docs = await retrieve_and_deduplicate_documents(retriever, expanded_queries)
    final_docs = rerank_documents(query, retrieved_docs, reranker, rerank_threshold)

    messages, token_count = build_final_prompt(query, history, final_docs, strict_mode)

    async for chunk in stream_llm_response(messages, token_count, temp):
        yield chunk

    logger.info("RAG flow finished.")
