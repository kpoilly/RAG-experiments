FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY prompts/ /app/prompts/
COPY ingestion.py /app/ingestion.py
COPY retriever.py /app/retriever.py
COPY utils.py /app/utils.py
COPY models.py /app/models.py
COPY config.py /app/config.py
COPY main.py /app/main.py

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]