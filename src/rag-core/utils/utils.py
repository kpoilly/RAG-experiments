import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, List

import httpx
import tiktoken
from langchain_classic.load import dumps, loads

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


MAX_RETRIES = 3


async def async_retry_post(client: httpx.AsyncClient, url: str, payload: Dict[str, Any], max_retries: int = MAX_RETRIES) -> httpx.Response:
    """
    Try to send and HTTP POST Request with Retry and Exponential Backoff.

    Args:
        url: URL from the service to call.
        payload: content of the JSON request to send.
        max_retries: Maximal number of tries.

    Returns:
        httpx.Response if request is successful.

    Raises:
        httpx.HTTPStatusError: if every try fails or if fatal error.
    """

    last_exception = None
    for attempt in range(max_retries):
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            last_exception = e
            if 400 <= e.response.status_code < 500:
                logger.error(f"Client error calling {url}: Status {e.response.status_code}. No more retries.")
                raise e

            delay = 0.5 * (2**attempt)
            logger.warning(f"HTTP request to {url} failed with status {e.response.status_code}. " f"Retrying in {delay:.2f}s (Attempt {attempt + 1}/{max_retries}).")
            await asyncio.sleep(delay)

        except httpx.RequestError as e:
            last_exception = e
            delay = 0.5 * (2**attempt)
            logger.warning(f"Network error calling {url}: {e.__class__.__name__}. " f"Retrying in {delay:.2f}s (Attempt {attempt + 1}/{max_retries}).")
            await asyncio.sleep(delay)

    logger.error(f"HTTP request to {url} failed permanently after {max_retries} attempts.")
    raise httpx.RequestError(f"Failed to communicate with {url} after multiple retries.") from last_exception


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


# --- Haching and files ID ---
def calculate_file_hash(file_path: str) -> str:
    """
    Calculate the hash of a file for stable ID.
    """
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as file:
            while True:
                chunk = file.read(4096)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Failed to hash file {file_path}: {e}")
        return ""


def calculate_file_hash_from_stream(file_stream) -> str:
    """Calculate the hash of a file from a stream for stable ID."""
    hasher = hashlib.sha256()
    while True:
        chunk = file_stream.read(4096)
        if not chunk:
            break
        hasher.update(chunk)
    return hasher.hexdigest()


def create_chunk_id(doc_hash: str, chunk_index: int) -> str:
    """Create a stable ID for a chunk."""
    return f"{doc_hash}_{chunk_index}"
