import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

import tiktoken
from langchain_classic.load import dumps, loads
from langchain_core.embeddings import Embeddings
from fastembed import TextEmbedding

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CustomFastEmbedEmbeddings(Embeddings):
    """
    Langchain-friendly Custom Wrapper for FastEmbed.
    Allow us to give arguments such as providers ou threads to the Embedder.
    """
    def __init__(self, model_name: str, max_length: int = 512, providers: Optional[List[str]] = None):
        logger.info(f"Initializing Custom FastEmbed: {model_name} (Providers: {providers})")
        self.model = TextEmbedding(
            model_name=model_name,
            max_length=max_length,
            providers=providers
        )
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return list(self.model.embed(texts))
    def embed_query(self, text: str) -> List[float]:
        return list(self.model.embed([text]))[0]


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

# --- Tokens count and optimisations --
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
