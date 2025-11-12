import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

LITELLM_PROXY_URL = os.getenv("LITELLM_PROXY_URL")
app = FastAPI(title="LLM Gateway Facade")


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
async def chat(request: Request):
    """
    Act as a proxy to LiteLLM proxy service.
    """

    client = httpx.AsyncClient()
    url = f"{LITELLM_PROXY_URL}/chat/completions"

    request_body = await request.json()

    async def stream_proxy():
        async with client.stream("POST", url, json=request_body) as proxy_response:
            proxy_response.raise_for_status()
            async for chunk in proxy_response.aiter_bytes():
                yield chunk

    return StreamingResponse(stream_proxy(), media_type="text/event-stream")
