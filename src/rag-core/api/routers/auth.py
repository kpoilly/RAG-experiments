import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from core import security
from core.config import settings as env
from database import crud, models
from schemas import security_schemas, user_schemas

from .. import deps

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/register", response_model=user_schemas.User)
def register_user(user: user_schemas.UserCreate, db: Session = Depends(deps.get_db)):
    """
    Handles user registration.
    Creates a new user in the database with a hashed password.
    """
    logger.info(f"Registering new user: {user.email}...")
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        )
    encrypted_key = security.encrypt_data(user.groq_api_key) if user.groq_api_key else None
    return crud.create_user(db=db, user=user, encrypted_api_key=encrypted_key)


@router.post("/token", response_model=security_schemas.Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(deps.get_db)):
    """
    Handles user login.
    Verifies credentials and returns a JWT access token.
    """
    logger.info(f"Logging in user: {form_data.username}...")
    user = crud.authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=env.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=user_schemas.User)
async def read_users_me(current_user: Annotated[models.User, Depends(deps.get_current_user)]):
    """
    Fetches the current logged-in user's information.
    A protected endpoint to verify token validity.
    """
    return current_user


@router.put("/users/me", response_model=user_schemas.User)
async def update_user_me(user_update: user_schemas.UserUpdate, current_user: models.User = Depends(deps.get_current_user), db: Session = Depends(deps.get_db)):
    """
    Allows a user to update their own API keys and model preferences.
    """
    return crud.update_user(db=db, user=current_user, user_update=user_update)
