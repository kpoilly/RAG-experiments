from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from .. import deps
from database import crud
from database.schemas import Message
from database import models

router = APIRouter(
    prefix="/history",
    tags=["Chat History"],
)

@router.get("", response_model=List[Message])
async def get_user_history(
    current_user: models.User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Fetches the entire chat history for the authenticated user."""
    return crud.get_history_for_user(db, user_id=str(current_user.id))
