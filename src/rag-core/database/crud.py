from typing import Dict, List

from sqlalchemy.orm import Session

from core import security

from . import models
from schemas import user_schemas


# --- User Crud ---
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: user_schemas.UserCreate, encrypted_api_key: bytes | None):
    hashed_password = security.get_password_hash(user.password)
    encrypted_key = security.encrypt_data(user.groq_api_key)
    db_user = models.User(
        email=user.email, hashed_password=hashed_password, encrypted_api_key=encrypted_key, llm_model=user.llm_model, llm_side_model=user.llm_side_model
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user or not security.verify_password(password, user.hashed_password):
        return None
    return user


def update_user(db: Session, user: models.User, user_update: user_schemas.UserUpdate):
    if user_update.groq_api_key is not None:
        user.encrypted_api_key = security.encrypt_data(user_update.groq_api_key)
    if user_update.llm_model is not None:
        user.llm_model = user_update.llm_model
    if user_update.llm_side_model is not None:
        user.llm_side_model = user_update.llm_side_model

    db.commit()
    db.refresh(user)
    return user


# --- History Crud ---
def get_history_for_user(db: Session, user_id: str) -> List[Dict[str, str]]:
    """
    Retrieve a user's history.
    """
    conversation = db.query(models.Conversation).filter(models.Conversation.user_id == user_id).first()
    if not conversation:
        return []
    return sorted(conversation.messages, key=lambda msg: msg.created_at)


def add_message_to_history(db: Session, user_id: str, role: str, content: str) -> models.Message:
    """
    Add a new message to the user's history.
    """
    conversation = db.query(models.Conversation).filter(models.Conversation.user_id == user_id).first()
    if not conversation:
        conversation = models.Conversation(user_id=user_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    db_message = models.Message(conversation_id=conversation.id, role=role, content=content)
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


def delete_history_for_user(db: Session, user_id: str) -> int:
    """
    Deletes every messages from a user.
    returns the number of deleted messages.
    """
    conversations = db.query(models.Conversation).filter(models.Conversation.user_id == user_id).all()
    if not conversations:
        return 0

    conversation_ids = [conv.id for conv in conversations]
    num_deleted = db.query(models.Message).filter(models.Message.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)

    db.commit()
    return num_deleted
