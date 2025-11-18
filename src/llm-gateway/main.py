import os

import httpx
from fastapi import FastAPI, Request, HTTPException
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

@app.get("/model/info")
async def model_info():
    """
    Proxy to LiteLLM's /model/info endpoint.
    """
    url = f"{LITELLM_PROXY_URL}/model/info"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Failed to connect to LiteLLM proxy: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
