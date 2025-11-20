import uuid

from typing import Optional
from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: EmailStr | None = None


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

    class Config:
        from_attributes = True
