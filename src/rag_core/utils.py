import asyncio
import json
import logging
from typing import Any, Dict, List

import httpx
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
