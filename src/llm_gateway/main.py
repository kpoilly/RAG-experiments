import json
import logging
import os
from typing import List

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from groq import Groq
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- Pydantic models ---
class Message(BaseModel):
    role: str
    content: str


class LLMRequest(BaseModel):
    messages: List[Message]
    model: str


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


@app.post("/chat")
async def chat(request: LLMRequest):
    """
    Receive final prompt (context + rag + prompt) and call the llm.
    """

    def groq_streaming_generator(messages, model):
        try:
            chat_completion = client.chat.completions.create(messages=messages, model=model, temperature=0.0, stream=True)

            for chunk in chat_completion:
                content = chunk.choices[0].delta.content
                if content:
                    data = {"text": content, "model": model, "status": "streaming"}
                    yield json.dumps(data) + "\n"
        except Exception as e:
            logger.error(f"Error during Groq streaming: {e}")
            yield json.dumps({"text": f"error: {str(e)}", "model": model, "status": "error"}) + "\n"

    messages = [msg.model_dump() for msg in request.messages]
    return StreamingResponse(content=groq_streaming_generator(messages, request.model), media_type="application/x-ndjson")


@app.post("/chat/completions")
async def chat_openai(request: LLMRequest):
    """
    Chat endpoint compatible with OpenAI API for MultiQueryRetriever (Streaming off).
    """
    try:
        messages = [msg.model_dump() for msg in request.messages]
        chat_completion = client.chat.completions.create(messages=messages, model=request.model, temperature=0.0, stream=False)
        full_response_content = chat_completion.choices[0].message.content
        return JSONResponse(
            content={
                "id": chat_completion.id,
                "object": "chat.completion",
                "created": chat_completion.created,
                "model": chat_completion.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": full_response_content,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": chat_completion.usage.dict(),
            }
        )
    except Exception as e:
        logger.error(f"Error during Groq non-streaming call: {e}")
        raise HTTPException(status_code=500, detail=str(e))
