import logging
from typing import List

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from database import crud, models
from database.schemas import Message

from .. import deps

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/history",
    tags=["Chat History"],
)


@router.get("", response_model=List[Message])
async def get_user_history(current_user: models.User = Depends(deps.get_current_user), db: Session = Depends(deps.get_db)):
    """Fetches the entire chat history for the authenticated user."""
    return crud.get_history_for_user(db, user_id=str(current_user.id))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_user_history(current_user: models.User = Depends(deps.get_current_user), db: Session = Depends(deps.get_db)):
    """
    Deletes the entire chat history for the authenticated user.
    """
    user_id = str(current_user.id)
    logger.info(f"Received request to clear history for user {user_id}.")

    num_deleted = crud.delete_history_for_user(db, user_id=user_id)

    logger.info(f"Cleared {num_deleted} messages for user {user_id}.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
