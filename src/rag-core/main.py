import asyncio
import logging

from fastapi import FastAPI, HTTPException, status
from prometheus_fastapi_instrumentator import Instrumentator

from api.routers import auth, chat, documents, history, service
from database.database import create_db_and_tables
from metrics import update_metrics
from rag.retriever import init_components
from utils.utils import create_service_user

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- init ---
app = FastAPI(title="RAG Core Service")
Instrumentator().instrument(app).expose(app)
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
        create_service_user()

        await asyncio.to_thread(init_components)
        app.state.rad_ready = True
        asyncio.create_task(update_metrics())

        logger.info("Application startup complete. Ready to serve requests.")
    except Exception as e:
        logger.error(f"FATAL: RAG initialization failed during startup: {e}", exc_info=True)


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(history.router)
app.include_router(service.router)


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
