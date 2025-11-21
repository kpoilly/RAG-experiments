import asyncio
import logging

import httpx
from fastapi import FastAPI, HTTPException, status

from api.routers import auth, chat, documents, history
from core.config import settings as env
from database.database import create_db_and_tables
from rag.retriever import init_components

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- init ---
app = FastAPI(title="RAG Core Service")
app.state.rad_ready = False
app.state.startup_error = None


@app.on_event("startup")
async def startup_event():
    """
    On startup, get model info, run ingestion and initialize the retrieval components.
    """
    logger.info("Application starting up...")
    try:
        logger.info("Initializing database and creating tables if they don't exist...")
        create_db_and_tables()
        logger.info("Database tables are ready.")
        model_info_url = f"{env.LLM_GATEWAY_URL}/model/info"
        async with httpx.AsyncClient() as client:
            response = await client.get(model_info_url)
            response.raise_for_status()
            all_models_info = response.json()

            models_list = all_models_info.get("data", [])
            model_config = next(
                (
                    model
                    for model in models_list
                    if (
                        model.get("model_name") == env.LLM_MODEL
                        or model.get("litellm_params", {}).get("model") == env.LLM_MODEL
                        or model.get("model_info", {}).get("key") == env.LLM_MODEL
                    )
                ),
                None,
            )

            context_window = None
            if model_config:
                context_window = model_config.get("model_info", {}).get("max_input_tokens")
            if context_window is None:
                logger.warning(f"Context window info not found for model {env.LLM_MODEL}. Using default value: {env.LLM_MAX_CONTEXT_TOKENS}.")
            else:
                env.LLM_MAX_CONTEXT_TOKENS = context_window
                logger.info(f"Successfully retrieved and set context window for {env.LLM_MODEL}: {env.LLM_MAX_CONTEXT_TOKENS} tokens.")
            logger.info(f"Context window for {env.LLM_MODEL}: {env.LLM_MAX_CONTEXT_TOKENS} tokens")

        await asyncio.to_thread(init_components)
        app.state.rad_ready = True
        logger.info("Application startup complete. Ready to serve requests.")
    except Exception as e:
        logger.error(f"FATAL: RAG initialization failed during startup: {e}", exc_info=True)


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(history.router)


# --- Endpoints ---
@app.get("/health")
async def health():
    """
    Health check.
    """
    if not app.state.rad_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"status": "error", "reason": "RAG components are not ready yet.", "error": app.state.startup_error}
        )
    return {"status": "ok"}
