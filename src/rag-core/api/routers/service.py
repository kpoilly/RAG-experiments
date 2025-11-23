from fastapi import APIRouter, Depends

from core.config import settings as env
from database import models
from schemas.service_schemas import RAGConfigResponse

from .. import deps

router = APIRouter(
    tags=["Service Info"],
)


@router.get("/config", response_model=RAGConfigResponse)
async def get_rag_configuration(current_user: models.User = Depends(deps.get_current_user)):
    """
    Returns the current configuration of the RAG pipeline,
    such as model names and chunking settings.
    """
    return RAGConfigResponse(
        llm_model=env.LLM_MODEL,
        llm_side_model=env.LLM_SIDE_MODEL,
        embedding_model=env.EMBEDDING_MODEL,
        reranker_model=env.RERANKER_MODEL,
        chunk_size_p=env.CHUNK_SIZE_P,
        chunk_overlap_p=env.CHUNK_OVERLAP_P,
        chunk_size_c=env.CHUNK_SIZE_C,
        chunk_overlap_c=env.CHUNK_OVERLAP_C,
    )
