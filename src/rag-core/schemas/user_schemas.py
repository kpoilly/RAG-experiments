import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    api_key: Optional[str] = None
    llm_model: Optional[str] = None
    side_api_key: Optional[str] = None
    llm_side_model: Optional[str] = None


class User(BaseModel):
    id: uuid.UUID
    email: EmailStr
    llm_model: Optional[str] = None
    llm_side_model: Optional[str] = None
    masked_api_key: Optional[str] = None
    masked_side_api_key: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
