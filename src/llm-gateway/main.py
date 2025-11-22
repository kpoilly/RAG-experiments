import logging
import os

import httpx
import tiktoken
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

LITELLM_PROXY_URL = os.getenv("LITELLM_PROXY_URL", "http://litellm-proxy:8003")

# --- init ---
app = FastAPI(title="LLM Gateway")
Instrumentator().instrument(app).expose(app)

# Custom Metrics
LLM_REQUESTS_TOTAL = Counter("llm_requests_total", "Total number of LLM requests", ["model"])
LLM_TOKENS_ESTIMATED_TOTAL = Counter("llm_tokens_estimated_total", "Estimated total number of tokens", ["model", "type"])
LLM_MODEL_CONTEXT_WINDOW = Gauge("llm_model_context_window", "Context window size of the model", ["model"])
LLM_MODEL_RPM = Gauge("llm_model_rpm", "Requests per minute limit of the model", ["model"])
LLM_MODEL_TPM = Gauge("llm_model_tpm", "Tokens per minute limit of the model", ["model"])


@app.on_event("startup")
async def startup_event():
    """
    Fetch model info from LiteLLM and populate metrics.
    """
    logger.info("Fetching model info from LiteLLM...")
    url = f"{LITELLM_PROXY_URL}/model/info"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                for model in data.get("data", []):
                    model_info = model.get("model_info", {})
                    if model_info:
                        LLM_MODEL_CONTEXT_WINDOW.labels(model=model_info.get("key", "unknown")).set(model_info.get("max_input_tokens"))
                    model_params = model.get("litellm_params", {})
                    if model_params:
                        LLM_MODEL_RPM.labels(model=model_params.get("model", "unknown")).set(model_params.get("rpm"))
                        LLM_MODEL_TPM.labels(model=model_params.get("model", "unknown")).set(model_params.get("tpm"))

                logger.info("Model info metrics populated.")
        except Exception as e:
            logger.error(f"Failed to fetch model info: {e}")


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

    url = f"{LITELLM_PROXY_URL}/chat/completions"

    request_body = await request.json()
    model = request_body.get("model", "unknown")
    LLM_REQUESTS_TOTAL.labels(model=model).inc()

    try:
        messages = request_body.get("messages", [])
        text = "".join([m.get("content", "") for m in messages])
        enc = tiktoken.get_encoding("cl100k_base")
        token_count = len(enc.encode(text))
        LLM_TOKENS_ESTIMATED_TOTAL.labels(model=model, type="input").inc(token_count)
    except Exception as e:
        logger.warning(f"Failed to count tokens: {e}")

    async def stream_proxy():
        async with httpx.AsyncClient() as client:
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
