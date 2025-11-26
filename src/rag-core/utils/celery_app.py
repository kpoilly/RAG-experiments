from celery import Celery

from core.config import settings as env

redis_url = f"redis://{env.REDIS_HOST}:{env.REDIS_PORT}/0"


celery = Celery("rag_tasks", broker=redis_url, backend=redis_url, include=["rag.tasks"])

celery.conf.update(
    task_track_started=True,
)
