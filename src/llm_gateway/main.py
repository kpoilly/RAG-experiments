import os
import json
import logging

from pydantic import BaseModel
from typing import List

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from groq import Groq


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Pydantic models ---
class Message(BaseModel):
	role: str
	content: str

class LLMRequest(BaseModel):
	messages: List[Message]
	model: str

class LLMResponse(BaseModel):
	response: str
	model: str
	status: str


# --- init ---
app = FastAPI(title="LLM Gateway")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
	raise EnvironmentError("GROQ_API_KEY not set")

try:
	client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
	raise RuntimeError(f"Error initializing Groq client: {e}")


# --- Endpoints ---
@app.get("/health")
async def health():
	"""
	Health check.
	"""
	return {"status": "ok"}

@app.post("/chat", response_model=LLMResponse)
async def chat(request: LLMRequest):
	"""
	Receive final prompt (context + rag + prompt) and call the llm.
	"""

	# messages = [msg.model_dump() for msg in request.messages]
	# try:
	# 	chat_completion = client.chat.completions.create(
	# 		messages=messages,
	# 		model=request.model,
	# 		temperature=0.0)
	# 	response = chat_completion.choices[0].message.content
	# 	logger.info(f"LLM call done. Total Time: {chat_completion.usage.total_time} Total Tokens: {chat_completion.usage.total_tokens}.")
	# 	return LLMResponse(response=response, model=request.model, status='success')
	# except Exception as e:
	# 	raise HTTPException(status_code=500, detail=str(e))

	def groq_streaming_generator(messages, model):
		try:
			chat_completion = client.chat.completions.create(
				messages=messages,
				model=model,
				temperature=0.0,
				stream=True
			)

			for chunk in chat_completion:
				content = chunk.choices[0].delta.content
				if content:
					data = {"text": content, "model": model, "status": "streaming"}
					yield json.dumps(data) + "\n"
		except Exception as e:
			logger.error(f"Error during Groq streaming: {e}")
			yield json.dumps({"text": f"error: {str(e)}", "model": model, "status": "error"}) + "\n"
		
	messages = [msg.model_dump() for msg in request.messages]
	return StreamingResponse(
		content=groq_streaming_generator(messages, request.model),
		media_type="application/x-ndjson"
	)