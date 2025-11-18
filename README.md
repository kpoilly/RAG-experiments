# 📚 Document-Grounded Conversational Assistant (RAG)

Conversational Assistant experiment. This system uses the **RAG** (Retrieval-Augmented Generation) architecture to provide accurate, contextual responses based on your private corpus of documents (PDFs, Docxs, MDs).

---

## 💡 Key Features & Architecture

The goal of this system is to be architected as a robust, scalable, and observable pipeline designed for modern, cloud-native workloads.

***Note on Smart & Dynamic Ingestion:*** *The document indexing process runs **automatically when the RAG service starts**. It can also be triggered at any time via the Streamlit UI or the API endpoint (`/ingest`). This allows you to update your reference documents in real-time by adding or removing them from the `data/` folder or the UI. The assistant will benefit from the new knowledge without any service interruption.*


1.  **Cloud-Agnostic Object Storage:** Document storage is fully decoupled from the application logic. The system uses a **MinIO** server for local development, which emulates the **S3 API**. This ensures that the application is "Cloud-Ready" and can be seamlessly deployed to any major cloud provider (AWS S3, Google Cloud Storage, Azure Blob Storage, Cloudflare R2...) by simply changing environment variables.

2.  **Provider-Agnostic LLM Gateway:** At the core is a sophisticated LLM Gateway powered by the **LiteLLM Proxy**. This proxy manages all interactions with large language models, providing:
    *   **Unified API:** An OpenAI-compatible interface for over 100+ LLM providers (Groq, OpenAI, Anthropic, etc.).
    *   **Load Balancing & Fallback:** Automatically routes requests and retries with fallback models if a primary provider fails or is rate-limited.
    *   **Caching:** Integrates with **Redis** for semantic caching, reducing latency and API costs on repeated queries.

3.  **Smart & Dynamic Ingestion:** The document indexing process is fully automated and event-driven. It runs **automatically at startup** and can be triggered on-demand via the UI or API. The system intelligently compares the documents in the S3 bucket with its index, processing only new, modified, or deleted files.

4.  **Optimized indexing with Parent Document Retriever (PDR):** Documents are processed using an advanced chunking strategy for optimal retrieval quality:
    *   **Parent Chunks:** Documents are split into larger chunks to capture rich context, stored in a **PostgreSQL `docstore` table**.
    *   **Child Chunks:** Each parent is split into smaller, precise chunks. Their **embeddings** are indexed in **PostgreSQL with PGVector** for efficient similarity search.

5.  **Advanced Retrieval Pipeline:**
    *   **Query Expansion:** The user's question is augmented by an LLM into multiple sub-queries to broaden the search scope.
    *   **Multi-Query Retrieval:** The **Parent Document Retriever** finds relevant child chunks for all queries via vector search and fetches their corresponding parent chunks.
    *   **Re-Ranking & Filtering:** A **Cross-Encoder** model re-ranks the retrieved parent documents for maximum relevance, filtering out those below a configurable threshold.

6.  **Augmented Generation:** The final, highly-relevant context is sent through the gateway to the selected LLM to generate a factual, streaming response.

7. **Secure & Scalable Serving:** All services are exposed through **Nginx** acting as a reverse proxy. This provides a single, secure entry point, enabling rate limiting, load balancing, and future implementation of HTTPS.

8. **Optimized for Performance & CI/CD:** The entire stack is containerized using **Docker** with **multi-stage builds**. This strategy ensures:
    *   **Fast CI/CD**: A dedicated `linter` stage allows for ultra-fast code quality checks (e.g., on GitHub Actions) without installing heavy dependencies like PyTorch.
    *   **Rapid Development**: Layer caching is optimized for quick rebuilds when only source code changes.
    *   **Efficient Dependency Management**: The project uses uv and pyproject.toml for best-in-class performance during dependency installation.

9. **Deep Observability:** The system is deeply instrumented for end-to-end observability, combining metric-based monitoring with detailed tracing:
    *   **LangSmith:** For tracing, debugging, and evaluating the RAG pipeline. It provides end-to-end visibility into every step of the chain (retrieval, reranking, generation) and tools for running evaluations on key metrics like faithfulness and answer relevance.
    *   **Prometheus & Grafana:** For real-time metrics, dashboards, and alerting.
    *   **Roadmap:** Future dashboards will provide deep insights into the RAG pipeline (evaluations, performance), the LLM Gateway (token usage, costs, errors), and API metrics (latency, request rates).

---

## 🛠️ Tech Stack

| Category | Tools/Libraries | Primary Role |
| :--- | :--- | :--- |
| **User Interface** | Streamlit | Interactive UI for chat and real-time document management. |
| **LLM Orchestration** | LiteLLM Proxy | Central hub for LLM routing, fallback, caching, and rate limiting. |
| **Reverse Proxy** | Nginx | Secure entry point, rate limiting, and future SSL/TLS termination. |
| **API Services** | FastAPI | High-performance backend for RAG logic and LLM gateway facade. |
| **Object Storage** | MinIO (S3 API) | Cloud-agnostic storage for raw documents. |
| **Vector Database** | PostgreSQL + PGVector | Storage, indexing, and vector search for child chunks. |
| **Reranking & Filtering**| BAAI/bge-reranker-v2-m3 (Cross-Encoder) | Refines search results by calculating a precise relevance score for each document. |
| **Caching** | Redis | Caches LLM responses to reduce latency and cost. |
| **RAG Framework** | LangChain | Orchestration of the RAG workflow (PDR, chains, etc.). |
| **Cloud SDK** | Boto3 | Standard Python SDK for interacting with S3-compatible APIs. |
| **Observability** | Prometheus, Grafana, LangSmith | (In progress) Monitoring, tracing, and evaluation of the entire stack. |
| **Containerization** | Docker, Docker Compose | Container orchestration and reproducible environments. |
| **Dependency Mgmt.** | `uv`, `pyproject.toml` | High-speed, modern Python package management. |
| *(...and others)* | | |

---

## 🚀 Quick Start

### 1. Environment Variables Configuration

The service's behavior is controlled by the following environment variables. They must be defined in an `.env` file at the project root.

#### Provider-Specific API Keys
You must provide the API key for the LLM provider you intend to use. The LiteLLM Proxy will automatically detect them.

| Variable | Example | Description |
| :--- | :--- | :--- |
| **GROQ_API_KEY** | `gsk_...` | API key for the Groq platform. |
| **OPENAI_API_KEY** | `sk-...` | API key for the OpenAI platform. |
| **ANTHROPIC_API_KEY** | `sk-ant-...` | API key for the Anthropic platform. |
| *(and others...)* | | See LiteLLM documentation for more. |

#### Main Application Configuration
These variables control the behavior of the RAG pipeline and database connections.

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| **LLM_MODEL** | `groq/meta-llama/llama-4-scout-17b-16e-instruct` | Name of the LLM model to call via the gateway, or its **alias** as defined in `litellm_config.yaml`. |
| **LLM_TEMPERATURE** | `0.3` | Generation temperature for the LLM. |
| **LLM_MAX_CONTEXT_TOKENS** | `30000` | **(Optional Fallback)** The system **automatically detects** the context window from the LLM Gateway at startup. This value is only used if the automatic detection fails. |
| **LLM_STRICT_RAG** | `False` | Determines whether the model can use its internal knowledge. | If **`True`**, the system instruction **forces** the model to respond ONLY with the provided context. If it cannot find the answer, it must explicitly state so (Strict RAG mode). If **`False`** (Relaxed RAG mode), the model is allowed to use its general knowledge when the context is insufficient. **WARNING**: Setting this to `False` may lead to answers that are not 100% faithful to the document and potentially increase the risk of **hallucinations**. |
| **EMBEDDING_MODEL** | `intfloat/multilingual-e5-small` | Name of the model used to generate vector embeddings for indexing and querying documents. | Defines the embedding function used by the vector database (ChromaDB) for dense search. |
| **RERANKER_MODEL** | `BAAI/bge-reranker-v2-m3` | Name of the **Cross-Encoder** model used to re-rank documents and calculate a precise relevance score. | Refines the list of documents retrieved before sending them to the LLM. |
| **RERANKER_THRESHOLD** | `0.4` | Minimum relevance score (float between 0.0 and 1.0) required for a document to be included in the final context. | Filters out documents considered irrelevant by the reranker. A higher value leads to stricter, more relevant context, but risks omitting potentially useful information. |
| **S3_ENDPOINT_URL** | `http://minio:9000` | S3 API endpoint. For local dev, this points to the MinIO container. |
| **S3_BUCKET_NAME** | `rag-documents` | The name of the S3 bucket to store documents. |
| **MINIO_ROOT_USER** | `minioadmin` | Admin username for the MinIO server. |
| **MINIO_ROOT_PASSWORD** | `minioadmin` | Admin password for the MinIO server. |
| **S3_ACCESS_KEY_ID**| `minioadmin` | Access key for the S3 client (`boto3`). **Must match `MINIO_ROOT_USER`**. |
| **S3_SECRET_ACCESS_KEY** | `minioadmin` | Secret key for the S3 client (`boto3`). **Must match `MINIO_ROOT_PASSWORD`**. |
| **DB_HOST** | `postgres` | Hostname of the PostgreSQL service (as defined in `docker-compose.yml`). | Database connection. |
| **DB_PORT** | `5432` | Listening port of the PostgreSQL service. | Database connection. |
| **DB_USER** | `user` | Username for connecting to the PostgreSQL database. | Database access. |
| **DB_PASSWORD** | `password` | Password for connecting to the PostgreSQL database. | Database access. |
| **DB_NAME** | `rag_db` | Name of the database to use within the PostgreSQL instance. | Specifies the target database. |
| **COLLECTION_NAME** | `rag_documents` | Name of the logical "collection" within PGVector. This isolates the project's documents. | Filters searches to only include documents from this project. |

Define your API key and parameters in a **`.env`** file at the **project root**.

### 2. LiteLLM Proxy Configuration

All LLM provider settings, including aliases, rate limits, and fallback strategies, are configured in one central file:

`deployments/litellm/litellm_config.yaml`

You **must** define the models you want to use in the `model_list` section of this file. Using aliases (like `groq-llama-instant`) is the recommended practice.

### 3. Adding Source Documents

All documents are managed in the S3-compatible storage layer (MinIO). You can manage your knowledge base in three ways:

1.  **Via the UI (Recommended for interactive use):**
    *   Use the upload and remove features in the Streamlit web interface (`make ui`).
    *   The knowledge base is updated automatically in a single, atomic API call for each operation.

2.  **Via the API with `curl` (Recommended for scripting & automation):**
    *   You can directly use the REST API to manage documents from your terminal. This is the ideal method for automation scripts.
    *   **To upload a document:**
        ```bash
        # Replace with the actual path to your local file
        curl -X POST -F "file=@/path/to/your/document.pdf" http://localhost/api/documents
        ```
    *   **To list all documents:**
        ```bash
        curl -X GET http://localhost/api/documents
        ```
    *   **To delete a document:**
        ```bash
        # Replace with the name of the file in the bucket
        curl -X DELETE http://localhost/api/documents/document.pdf
        ```

3.  **Via the MinIO Console (For bulk operations or direct access):**
    *   Access the MinIO console at `http://localhost/minio` (`make minio`).
    *   Log in with your credentials (e.g., `minioadmin`/`minioadmin`).
    *   Create the bucket (e.g., `rag-documents`) if it doesn't exist.
    *   Upload or delete files directly in the console.
    *   **Important:** After making changes directly in the MinIO console, you **must** manually trigger a re-synchronization of the index by calling the ingest endpoint:
        ```bash
        make ingest
        ```

### 4. Running the Service

This project uses a `Makefile` for easy command execution.

1. **Launch the project:**

```bash
make
```
This single command builds and starts all services (RAG Core, LiteLLM Proxy, Streamlit UI, etc.) and runs the initial document ingestion.

2.  **Access the Interfaces:**
    *   **Web App:** `make ui` (or `http://localhost`)
    *   **MinIO Console:** `make minio` (or `http://localhost/minio`)
    *   **Grafana:** `make grafana` (or `http://localhost/grafana`)
    *   **Prometheus:** `make prometheus` (or `http://localhost/prometheus`)
    *   **PGAdmin:** `make pgadmin` (or `http://localhost/pgadmin`)

3.   **Using the CLI:**
      *   You can also use the **CLI interface** directly in your terminal with `make cli`.

4.  **Stopping the Service:**
    ```bash
    make down
    ```

### Preview Screenshots

<img width="1908" height="898" alt="image" src="https://github.com/user-attachments/assets/8b1c48f8-7481-418f-ad10-ceb1dbdaf1e1" />

<img width="1915" height="908" alt="image" src="https://github.com/user-attachments/assets/8d4f5d15-e2ee-47a1-af0f-613671491040" />

<img width="2198" height="1166" alt="image" src="https://github.com/user-attachments/assets/0ed09652-0a6f-464c-a266-210288f98e86" />
