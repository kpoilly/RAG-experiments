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
	
	print("\n" + "="*50)
	print("🤖 Chatbot RAG 🤖")
	print("Write 'exit' to quit.")
	print("="*50 + "\n")

	while True:
		try:
			user_input = input("You: ")

			if user_input.lower() == "exit":
				print("Goodbye!")
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
				print("\nMichel: ", end="", flush=True)
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

			# response = requests.post(RAG_CORE_URL, json=request_payload, timeout=60)
			# response.raise_for_status()
			# data = response.json()
			# rag_reponse = data.get("response", "Error: No response from LLM.")

			# print(f"\nMichel: {rag_reponse}\n")
			# chat_history.append({"role": "assistant", "content": rag_reponse})

		except requests.exceptions.RequestException as e:
			logger.error(f"Request failed: {e}")
			if chat_history and chat_history[-1]["role"] == "user":
				chat_history.pop()
		except KeyboardInterrupt:
			print("\nGoodbye!")
			break
		except Exception as e:
			logger.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
	run_chatbot_cli()
