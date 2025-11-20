from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from core.config import settings as env
from database import models, crud
from database.database import SessionLocal
from rag.ingestion_utils import S3Repository


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_s3_repo():
    return S3Repository()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, env.JWT_SECRET_KEY, algorithms=[env.JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user
