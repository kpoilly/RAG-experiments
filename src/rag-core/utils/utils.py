import json
import logging
from typing import Any, Dict, List

import tiktoken
from langchain_classic.load import dumps, loads

from core.config import settings as env
from database import crud
from database.database import SessionLocal
from schemas import user_schemas

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def format_history_for_prompt(history: List[Dict[str, str]]) -> str:
    """
    format history in a simple string for a better understanding by the llm.
    """

    if not history:
        return "No history yet."
    formatted_messages = [
        f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" for msg in history if isinstance(msg, dict) and msg.get("role") and msg.get("content")
    ]
    return "\n".join(formatted_messages)


def value_serializer(value: Any) -> bytes:
    return json.dumps(dumps(value)).encode("utf-8")


def value_deserializer(data: bytes) -> Any:
    return loads(json.loads(data.decode("utf-8")))


# --- Token count and optimizations ---
try:
    tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception:
    tokenizer = tiktoken.encoding_for_model("gpt-4")


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text.
    """
    return len(tokenizer.encode(text))


def truncate_history(history: List[Dict[str, str]], max_tokens: int) -> List[Dict[str, str]]:
    """
    Truncate history to stay within the context window.
    """
    if sum(count_tokens(message.get("content", "")) for message in history) <= max_tokens:
        return history

    current_tokens = 0
    truncated_history = []

    for message in reversed(history):
        message_tokens = count_tokens(message.get("content", ""))
        if (current_tokens + message_tokens) <= max_tokens:
            truncated_history.insert(0, message)
            current_tokens += message_tokens
        else:
            break

    return truncated_history


def create_service_user():
    logger.info("Bootstrapping service account for evaluation...")

    if not env.SERVICE_ACCOUNT_EMAIL or not env.SERVICE_ACCOUNT_PASSWORD:
        logger.warning("No service credentials provided. Skipping service user creation (some services might not work properly).")
        return

    db = SessionLocal()
    try:
        service_user = crud.get_user_by_email(db, email=env.SERVICE_ACCOUNT_EMAIL)

        if not service_user:
            logger.info(f"Service user '{env.SERVICE_ACCOUNT_EMAIL}' not found. Creating it...")

            user_create_schema = user_schemas.UserCreate(email=env.SERVICE_ACCOUNT_EMAIL, password=env.SERVICE_ACCOUNT_PASSWORD)
            crud.create_user(db, user=user_create_schema)
            logger.info(f"Service user '{env.SERVICE_ACCOUNT_EMAIL}' created successfully.")
        else:
            logger.info(f"Service user '{env.SERVICE_ACCOUNT_EMAIL}' already exists.")
    finally:
        db.close()
