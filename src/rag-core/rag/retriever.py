import json
import logging
from typing import AsyncGenerator, Optional

from fastembed.rerank.cross_encoder import TextCrossEncoder
from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_classic.storage import EncoderBackedStore
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.storage import SQLStore
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI
from langchain_postgres.vectorstores import PGVector
from sqlalchemy.orm import Session

from core import security
from core.config import settings as env
from core.models import ExpandedQueries
from database import crud
from metrics import RAG_RETRIEVAL_LATENCY, RAG_RETRIEVED_DOCS
from utils.utils import get_context_window, value_deserializer, value_serializer

from . import retriever_utils
from .ingestion import get_embeddings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- Init & Component Getters ---
QUERY_EXP_PROMPTS = retriever_utils.load_prompts("prompts/query_expansion.yaml")


_RERANKER: Optional[TextCrossEncoder] = None


def init_components():
    """
    Initialize heavy components (Embedder, Reranker, LLM).
    """
    global _RERANKER
    logger.info("Initializing Embedder, Reranker and LLM...")

    get_embeddings()

    if _RERANKER is None:
        logger.info(f"Initializing reranker model... ({env.RERANKER_MODEL})")
        _RERANKER = TextCrossEncoder(model_name=env.RERANKER_MODEL)
        logger.info("Reranker model loaded.")

    logger.info("Embedder, Reranker and LLM chain initialized.")


def get_reranker() -> Optional[TextCrossEncoder]:
    return _RERANKER


async def get_retriever_for_user(user_id: str) -> ParentDocumentRetriever:
    """
    Build or refresh the ParentDocumentRetriever.
    """
    logger.info(f"Building Parent Document Retriever for user {user_id}...")
    user_id = user_id.replace("-", "")
    collection_name = f"user_{user_id}_collection"
    namespace = f"user_{user_id}_parents"

    embedder = get_embeddings()
    vector_store = PGVector(collection_name=collection_name, connection=env.DB_URL, embeddings=embedder, async_mode=True)
    doc_store = SQLStore(db_url=env.DB_URL, namespace=namespace, async_mode=True)
    await doc_store.acreate_schema()
    # await vector_store.acreate_vector_extension() # Managed init script
    await vector_store.acreate_collection()
    await vector_store.acreate_tables_if_not_exists()
    store = EncoderBackedStore(doc_store, key_encoder=lambda key: key, value_serializer=value_serializer, value_deserializer=value_deserializer)

    child_splitter = RecursiveCharacterTextSplitter(chunk_size=env.CHUNK_SIZE_C, chunk_overlap=env.CHUNK_OVERLAP_C, separators=["\n\n", "\n", " "])
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=env.CHUNK_SIZE_P, chunk_overlap=env.CHUNK_OVERLAP_P, separators=["\n#", "\n##", "\n\n\n"])
    retriever = ParentDocumentRetriever(vectorstore=vector_store, docstore=store, child_splitter=child_splitter, parent_splitter=parent_splitter)
    logger.info("Parent Document Retriever is ready.")
    return retriever


def get_llm_query_gen(model: str, api_key: str) -> Optional[ChatOpenAI]:
    """
    Gets the non-streaming LLM instance for internal tasks like query generation.
    """
    return ChatOpenAI(model_name=model, openai_api_base=env.LLM_GATEWAY_URL, openai_api_key=api_key, temperature=0.0, streaming=False)


def get_query_expansion_chain(model: str, api_key: str) -> Optional[RunnableSequence]:
    """
    Get the query expansion chain.
    """
    llm = get_llm_query_gen(model, api_key)
    if not llm:
        logger.error("Cannot initialize query expansion chain without LLM.")
        return None

    output_parser = PydanticOutputParser(pydantic_object=ExpandedQueries)
    prompt = PromptTemplate(
        template=QUERY_EXP_PROMPTS["instructions"],
        input_variables=["question", "chat_history"],
        partial_variables={"format_instructions": output_parser.get_format_instructions()},
    )

    return prompt | llm | output_parser


# --- RAG flow ---


async def orchestrate_rag_flow(
    query: str, user_id: str, db: Session, temp: float = 0.2, strict_mode: bool = True, rerank_threshold: float = 0.0
) -> AsyncGenerator[str, None]:
    """
    Executes the entire RAG flow by orchestrating calls to specialized functions.

    Args:
        query: The user's query.
        history: The chat history.

    Yields:
        A stream of JSON strings containing the LLM's answer or an error.
    """
    user = crud.get_user_by_id(db, user_id=user_id)
    user_api_key = security.decrypt_data(user.encrypted_api_key if user.encrypted_api_key else None)
    user_side_api_key = security.decrypt_data(user.encrypted_side_api_key if user.encrypted_side_api_key else None)
    user_llm_model = user.llm_model
    user_llm_side_model = user.llm_side_model
    window_size = await get_context_window(user.llm_model)

    logger.info(f"Starting RAG flow for query: {query[:50]}... (strict mode: {strict_mode}))")

    crud.add_message_to_history(db, user_id=user_id, role="user", content=query)
    db_history = crud.get_history_for_user(db, user_id=user_id)
    history = [{"role": msg.role, "content": msg.content} for msg in db_history]

    retriever = await get_retriever_for_user(user_id)
    if retriever is None:
        logger.error("Cannot retrieve retriever.")
        yield json.dumps({"type": "error", "content": "System Error: Retriever not available."}) + "\n"
        return
    reranker = get_reranker()
    query_expansion_chain = get_query_expansion_chain(model=user_llm_side_model, api_key=user_side_api_key)

    with RAG_RETRIEVAL_LATENCY.time():
        expanded_queries = await retriever_utils.expand_query(query, history, query_expansion_chain)
        retrieved_docs = await retriever_utils.retrieve_and_deduplicate_documents(retriever, expanded_queries)
        final_docs = retriever_utils.rerank_documents(query, retrieved_docs, reranker, rerank_threshold)

    RAG_RETRIEVED_DOCS.observe(len(final_docs))

    messages, token_count, source_chunks = retriever_utils.build_final_prompt(query, history, final_docs, strict_mode, window_size)

    # We do this because evaluation-runner needs the context texts and metadatas
    sources_payload = {"type": "sources", "data": source_chunks}
    yield f"data: {json.dumps(sources_payload)}\n\n"

    full_assistant_response = ""
    async for chunk in retriever_utils.stream_llm_response(messages, token_count, temp, model=user_llm_model, api_key=user_api_key):
        try:
            # logger.info(f"Chunk: {chunk}")
            if chunk.startswith("data:"):
                data_str = chunk[5:].strip()
                if data_str and data_str != "[DONE]":
                    data = json.loads(data_str)
                    content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if content:
                        full_assistant_response += content
        except json.JSONDecodeError:
            pass
        yield chunk

    if full_assistant_response:
        crud.add_message_to_history(db, user_id=user_id, role="assistant", content=full_assistant_response, sources=source_chunks)
    logger.info("RAG flow finished.")
