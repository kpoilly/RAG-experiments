import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
from fastembed.rerank.cross_encoder import TextCrossEncoder
from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_core.runnables import RunnableSequence

from core.config import settings as env
from core.models import LLMRequest
from utils.utils import count_tokens, format_history_for_prompt, truncate_history

logger = logging.getLogger(__name__)

# --- Init Prompts ---
with open("/app/prompts/system.json", "r") as f:
    SYSTEM_PROMPTS = json.load(f)
if isinstance(SYSTEM_PROMPTS["instructions"], list):
    SYSTEM_PROMPTS["instructions"] = "\n".join(SYSTEM_PROMPTS["instructions"])


async def expand_query(query: str, history: List[Dict[str, str]], query_expansion_chain: Optional[RunnableSequence]) -> List[str]:
    """
    Expands the original query into multiple related queries using a language model.

    Args:
        query: The user's original query.
        history: The chat history.
        query_expansion_chain: The LangChain RunnableSequence for query expansion.

    Returns:
        A list of queries, with the original query always as the first element.
        Returns [query] if expansion fails.
    """
    if query_expansion_chain is None:
        logger.error("Cannot retrieve query expansion chain. Using original query.")
        return [query]

    try:
        history_str = format_history_for_prompt(history)
        gen_exp_queries = await query_expansion_chain.ainvoke({"question": query, "chat_history": history_str[:4000]})
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


def rerank_documents(query: str, docs: List, reranker: Optional[TextCrossEncoder] = None, threshold: float = env.RERANKER_THRESHOLD) -> List:
    """
    Reranks a list of documents based on relevance to the query.

    Args:
        query: The user's query.
        docs: The list of documents to rerank.
        reranker: The reranker model instance.
        threshold: The score threshold for keeping documents.

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
    docs_content = [doc.page_content for doc in docs_to_rerank]

    try:
        scores = list(reranker.rerank(query=query, documents=docs_content))
        logging.info(f"Reranker scores: {scores}")
        doc_scores_pairs = list(zip(docs_to_rerank, scores))
        sorted_pairs = sorted(doc_scores_pairs, key=lambda x: x[1], reverse=True)

        final_docs = []
        for doc, score in sorted_pairs:
            if score > threshold:
                doc.metadata["rerank_score"] = score
                final_docs.append(doc)

        if final_docs:
            logger.info(f"{len(final_docs)} documents passed the reranker threshold of {threshold}.")
        elif sorted_pairs:
            best_doc, best_score = sorted_pairs[0]
            logger.warning(f"No documents met the threshold of {threshold}. Falling back to the single best document with score {best_score:.4f}.")
            best_doc.metadata["rerank_score"] = best_score
            final_docs = [best_doc]
        else:
            final_docs = []

        return final_docs
    except Exception as e:
        logger.warning(f"Reranking failed: {e}. Falling back to original documents.")
        return docs_to_rerank


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


def build_prompt_with_context(query: str, context: str, history: List[Dict[str, str]], strict_rule: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Build the final prompt to send to the LLM, including RAG context and history.

    Args:
        query: user's query.
        context: Chunks of documents retrieved.
        history: chat history.
        strict_rule: The strict rule string to append to the prompt.

    Returns:
        A Tuple with the system instruction and the list of final messages.
    """

    template = SYSTEM_PROMPTS["instructions"]
    system_instruction = template.format(context=context, strict_rule=strict_rule)
    messages = [{"role": "system", "content": system_instruction}]
    messages.extend(history)
    messages.append({"role": "user", "content": query})

    return system_instruction, messages


def build_final_prompt(query: str, history: List[Dict[str, str]], docs: List, strict: bool) -> Tuple[List[Dict[str, Any]], int, List[Dict[str, Any]]]:
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
        - The source chunks for frontend.
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
    context_for_llm = []
    source_chunks_for_frontend = []
    current_context_tokens = 0

    for i, doc in enumerate(docs):
        doc_tokens = count_tokens(doc.page_content)
        if current_context_tokens + doc_tokens > CONTEXT_BUDGET:
            logger.info("Reached RAG context token budget during prompt construction.")
            break

        current_context_tokens += doc_tokens
        # Numeroted context for llm
        context_chunk = f"[{i+1}] Content: {doc.page_content} (Source: {doc.metadata.get('source', 'N/A')} [Page {doc.metadata.get('page', 'N/A')}])"
        context_for_llm.append(context_chunk)

        # Sources map for frontend
        source_chunks_for_frontend.append(
            {"index": i + 1, "content": doc.page_content, "source": doc.metadata.get("source", "N/A"), "page": doc.metadata.get("page", "N/A")}
        )

    final_context_str = "\n\n".join(context_for_llm)
    if not final_context_str:
        logger.warning("No relevant documents were added to the final context.")

    # Assemble final prompt
    system_instructions, messages = build_prompt_with_context(query, final_context_str, final_history, strict_rule)
    total_tokens = query_tokens + history_tokens + count_tokens(system_instructions)
    logger.info(
        f"Final prompt assembled. Tokens - Total: {total_tokens}, Query: {query_tokens}, " f"History: {history_tokens}, Instructions: {count_tokens(system_instructions)}"
    )

    return messages, total_tokens, source_chunks_for_frontend


async def stream_llm_response(messages: List[Dict[str, Any]], token_count: int, temp: Optional[float] = None) -> AsyncGenerator[str, None]:
    """
    Constructs the final prompt, calls the LLM, and streams the response.

    Args:
        messages: The list of messages to send to the LLM.
        token_count: The total token count for logging.
        temp: The temperature for the LLM.

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
