import logging

import httpx
from fastapi import APIRouter, HTTPException

from core.config import settings as env
from schemas.service_schemas import ModelInfo, ModelListResponse, RAGConfigResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


router = APIRouter(
    tags=["Service Info"],
)


@router.get("/config", response_model=RAGConfigResponse)
async def get_rag_configuration():
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


@router.get("/models", response_model=ModelListResponse)
async def get_available_models():
    """
    Fetches the list of available LLM models from the LLM Gateway.
    It intelligently parses different response formats from LiteLLM.
    """
    try:
        url = f"{env.LLM_GATEWAY_URL}/model/info"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        available_models = []
        if "data" in data and isinstance(data["data"], list):
            logger.info(f"Received: {data}")
            for model_obj in data["data"]:
                model_name = model_obj.get("model_name")
                if model_name and "/" not in model_name:
                    available_models.append(ModelInfo(model_name=model_name, model_id=model_name))

        if not available_models:
            logger.warning("Could not parse a list of models from the LLM Gateway response.")
        return ModelListResponse(models=available_models)

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to LLM Gateway at {url}: {e}")
        raise HTTPException(status_code=502, detail="Could not connect to the LLM Gateway.")
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching models: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while fetching model list.")
