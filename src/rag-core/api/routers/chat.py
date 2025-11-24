import json
import logging
import re

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api import deps
from core.models import GenerationRequest
from database import crud, models
from rag.retriever import orchestrate_rag_flow

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("")
async def generate(request: GenerationRequest, current_user: models.User = Depends(deps.get_current_user), db: Session = Depends(deps.get_db)):
    try:
        user_id = str(current_user.id)
        logger.info(f"New chat request received from {user_id}.")
        user = crud.get_user_by_id(db, user_id=user_id)
        if not user.encrypted_api_key or not user.encrypted_side_api_key:
            logger.error("API key not found for user.")
            return StreamingResponse(content=json.dumps({"type": "error", "content": "API key not found."}), media_type="application/jsonlines", status_code=401)
        formated_query = re.sub(r"(\b[ldjstnmc]|qu)'", r"\1 ", request.query.lower())
        response_generator = orchestrate_rag_flow(formated_query, user_id, db, request.temperature, request.strict_rag, request.rerank_threshold)
        return StreamingResponse(content=response_generator, media_type="text/event-stream")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return StreamingResponse(content=json.dumps({"type": "error", "content": str(e)}), media_type="application/jsonlines", status_code=500)
