import json
import logging
import os
import time
from typing import Dict, List, Optional

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- Config ---
API_URL = os.getenv("API_URL", "http://nginx/api")
CHAT_URL = f"{API_URL}/chat"
HEALTH_URL = f"{API_URL}/health"

STARTUP_TIMEOUT = 180

chat_history: List[Dict[str, str]] = []


# --- CLI ---
def wait_rag():
    start_time = time.time()
    while time.time() - start_time < STARTUP_TIMEOUT:
        try:
            response = requests.get(HEALTH_URL)
            if response.status_code == 200:
                logger.info("RAG is ready.")
                return True
            else:
                status_detail = response.json().get("detail", {})
                logger.info(f"Service not ready yet (Status: {status_detail.get('status')}). Retrying...")
        except requests.exceptions.ConnectionError:
            logger.info("RAG Service not ready yet. Retrying...")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
        time.sleep(20)
    logger.error("Timeout reached. RAG Core service did not start up in time.")
    return False


def _parse_sse(line: str) -> Optional[str]:
    """
    Parses a single line of a Server-Sent Event (SSE) stream and returns the content.
    Returns None if the line is not valid data.
    """
    if not line.startswith("data:"):
        return None

    json_str = line[5:].lstrip()

    if not json_str or json_str == "[DONE]":
        return None

    try:
        data = json.loads(json_str)
        delta = data.get("choices", [{}])[0].get("delta", {})
        content = delta.get("content")
        return content
    except json.JSONDecodeError:
        logger.warning(f"Failed to decode JSON chunk in SSE stream: {json_str}")
        return None


def run_chatbot_cli():
    """
    Run the chatbot CLI.
    """
    if not wait_rag():
        print("\n\033[31mCould not connect to the RAG service after multiple attempts. Please check the service logs and try again.\033[0m")
        return

    logger.info("Running chatbot CLI...")
    global chat_history

    print("\n" + "\033[33m=\033[0m" * 50)
    print("🤖 \033[33mChatbot RAG\033[0m 🤖")
    print("\033[33mWrite '\033[31mexit\033[33m' to quit.\033[0m")
    print("\033[33m=\033[0m" * 50 + "\n")

    while True:
        try:
            user_input = input("\033[32mYou\033[0m: ")

            if user_input.lower() == "exit":
                print("\033[33mGoodbye!\033[0m")
                break
            if not user_input.strip():
                continue

            chat_history.append({"role": "user", "content": user_input})
            request_payload = {"query": user_input, "history": chat_history}
            with requests.post(CHAT_URL, json=request_payload, stream=True, timeout=120) as response:
                response.raise_for_status()

                full_response = ""
                print("\n\033[31mMichel\033[0m: ", end="", flush=True)

                buffer = ""
                for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                    if chunk:
                        buffer += chunk

                        while "\n\n" in buffer:
                            message, buffer = buffer.split("\n\n", 1)
                            content = _parse_sse(message)
                            if content:
                                full_response += content
                                print(content, end="", flush=True)

                final_content = _parse_sse(buffer.strip())
                if final_content:
                    full_response += final_content
                    print(final_content, end="", flush=True)

                print("\n")
                if full_response:
                    chat_history.append({"role": "assistant", "content": full_response})

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            if chat_history and chat_history[-1]["role"] == "user":
                chat_history.pop()
        except KeyboardInterrupt:
            print("\033[33mGoodbye!\033[0m")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    run_chatbot_cli()
