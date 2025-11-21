import uuid

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: EmailStr | None = None


# --- User Schemas ---

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    groq_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_side_model: Optional[str] = None


class UserUpdate(BaseModel):
    groq_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_side_model: Optional[str] = None


class User(BaseModel):
    id: uuid.UUID
    email: EmailStr
    llm_model: Optional[str] = None
    llm_side_model: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- Message Schemas ---

class MessageBase(BaseModel):
    role: str
    content: str


class Message(MessageBase):
    id: uuid.UUID
    conversation_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
        