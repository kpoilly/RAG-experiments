import json
import time
import logging

import requests

from typing import List, Dict


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Config ---
RAG_CORE_URL="http://rag-core:8001/chat"
INGESTION_URL="http://rag-core:8001/ingest"

chat_history: List[Dict[str, str]] = []


def run_ingestion():
	"""
	Run the ingestion process.
	"""
	logger.info("Running ingestion...")

	for attempt in range(5):
		try:
			response = requests.post(INGESTION_URL)
			response.raise_for_status()
			logger.info("Ingestion successful.")
			return
		
		except requests.exceptions.ConnectionError:
			logger.error(f"Connection to RAG Core failed. (Try {attempt+1}/5)")
			time.sleep(3)
		except requests.exceptions.HTTPError as e:
			logger.error(f"Ingestion failed (HTTP {e.response.status_code}): {e.response.text}")
			return
		except Exception as e:
			logger.error(f"Ingestion failed: {e}")
			return
		
def run_chatbot_cli():
	"""
	Run the chatbot CLI.
	"""
	logger.info("Running chatbot CLI...")
	global chat_history

	run_ingestion()
	
	print("\n" + "\033[33m=\033[0m"*50)
	print("🤖 \033[33mChatbot RAG\033[0m 🤖")
	print("\033[33mWrite '\033[31mexit\033[33m' to quit.\033[0m")
	print("\033[33m=\033[0m"*50 + "\n")

	while True:
		try:
			user_input = input("\033[32mYou\033[0m: ")

			if user_input.lower() == "exit":
				print("\033[33mGoodbye!\033[0m")
				break
			if not user_input.strip():
				continue

			chat_history.append({"role": "user", "content": user_input})
			request_payload = {
				"query": user_input,
				"history": chat_history
			}
			with requests.post(RAG_CORE_URL, json=request_payload, stream=True, timeout=120) as response:
				response.raise_for_status()

				full_response = ""
				print("\n\033[31mMichel\033[0m: ", end="", flush=True)
				for line in response.iter_lines():
					if line:
						try:
							chunk = json.loads(line.decode('utf-8'))
							print(chunk["content"], end="", flush=True)
							full_response += chunk["content"]
						except json.JSONDecodeError:
							logger.warning(f"Failed to decode JSON chunk: {line.decode('utf-8')}")
							continue
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
