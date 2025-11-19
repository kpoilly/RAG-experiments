import logging

from fastapi import FastAPI, BackgroundTasks, status
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import start_http_server

from evaluate import run_evaluation_task


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG Evaluation Runner")
Instrumentator().instrument(app).expose(app)

@app.on_event("startup")
def startup_event():
    start_http_server(8005)
    logger.info("Prometheus metrics server started on port 8005.")

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/evaluate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_evaluation(background_tasks: BackgroundTasks):
    """
    Triggers a RAG evaluation run in the background.
    """
    logger.info("Received request to trigger evaluation. Adding to background tasks.")
    background_tasks.add_task(run_evaluation_task)
    return {"message": "Evaluation run has been scheduled in the background."}
