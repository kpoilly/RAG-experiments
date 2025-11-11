import json
import logging
from typing import List, Optional

import litellm
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
litellm.set_verbose = False


# --- Pydantic models ---
class Message(BaseModel):
    role: str
    content: str


class LLMRequest(BaseModel):
    messages: List[Message]
    model: str
    stream: Optional[bool] = False


# --- init ---
app = FastAPI(title="LLM Gateway")


# --- Endpoints ---
@app.get("/health")
async def health():
    """
    Health check.
    """
    return {"status": "ok"}


@app.post("/chat/completions")
async def chat(request: LLMRequest):
    """
    Chat endpoint for streaming and non-streaming responses.
    """
    messages = [msg.model_dump() for msg in request.messages]
    try:
        response_stream = await litellm.acompletion(model=request.model, messages=messages, temperature=0.0, stream=request.stream)

        if request.stream:

            async def streaming_generator():
                try:
                    async for chunk in response_stream:
                        if chunk.choices[0].delta.content is not None:
                            yield f"data: {json.dumps(chunk.model_dump())}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    logger.error(f"Error during LiteLLM stream iteration: {e}")

            return StreamingResponse(streaming_generator(), media_type="text/event-stream")

        else:
            return JSONResponse(content=response_stream.model_dump())

    except Exception as e:
        logger.error(f"LiteLLM call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
