FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml /app/pyproject.toml
COPY prompts/ /app/prompts/
COPY ingestion.py /app/ingestion.py
COPY retriever.py /app/retriever.py
COPY utils.py /app/utils.py
COPY models.py /app/models.py
COPY config.py /app/config.py
COPY main.py /app/main.py

RUN pip install --no-cache-dir markdown==3.10
RUN apt-get update && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]