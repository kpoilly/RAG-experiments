from sqlalchemy.orm import Session

from core import security
from . import models, schemas


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(
    db: Session, 
    user: schemas.UserCreate, 
    encrypted_groq_api_key: bytes | None
):
    hashed_password = security.get_password_hash(user.password)
    encrypted_key = security.encrypt_data(user.groq_api_key)
    db_user = models.User(
        email=user.email, 
        hashed_password=hashed_password,
        encrypted_groq_api_key=encrypted_key,
        llm_model=user.llm_model,
        llm_side_model=user.llm_side_model
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


def update_user(db: Session, user: models.User, user_update: schemas.UserUpdate):
    if user_update.groq_api_key is not None:
        user.encrypted_groq_api_key = security.encrypt_data(user_update.groq_api_key)
    if user_update.llm_model is not None:
        user.llm_model = user_update.llm_model
    if user_update.llm_side_model is not None:
        user.llm_side_model = user_update.llm_side_model
    
    db.commit()
    db.refresh(user)
    return user
