<p align="center">
   <img src="https://github.com/user-attachments/assets/744672e4-9716-4d91-8ac3-a00abe5a4cb2" width="300" height="300">
</p>

# 📚 Document-Grounded Conversational Assistant (RAG)

This project provides a **production-ready, multi-tenant platform** for deploying Document-Grounded Conversational Assistants. Built on a robust **RAG** (Retrieval-Augmented Generation) architecture, the system allows multiple users to securely manage their own private document collections and interact with a context-aware AI through a modern web interface.


---

## 💡 Key Features & Architecture

The goal of this system is to be architected as a secure, robust, scalable, and observable pipeline designed for modern, cloud-native workloads.


1.  **Cloud-Agnostic Object Storage:** Document storage is fully decoupled from the application logic.The system uses a **MinIO** server for local development, which emulates the **S3 API**. This ensures that the application is "Cloud-Ready" and can be deployed seamlessly to AWS S3, Google Cloud Storage, Azure Blob Storage, etc.

2.  **Provider-Agnostic LLM Gateway:** Powered by **LiteLLM Proxy**, providing a unified OpenAI-compatible interface for 100+ providers, load balancing, fallback, and Redis caching.

3.  **Smart & Dynamic Ingestion:** Event-driven indexing that automatically processes only new, modified, or deleted files from the bucket.

4.  **High-Performance Vectorization (FastEmbed):**
    * **No Heavy Dependencies:** Replaces PyTorch with **FastEmbed** (ONNX Runtime) for lightweight, CPU-friendly containers.
    * **Quantized Models:** Uses optimized, quantized models for faster inference and lower RAM usage.
    * **Parent Document Retriever (PDR):** Combines broad context (Parent chunks in PostgreSQL) with precise retrieval (Child chunks in PGVector).

5.  **Advanced Retrieval Pipeline:**
    * **Query Expansion:** Augments user questions into multiple sub-queries.
    * **Re-Ranking:** Uses a **Cross-Encoder** (via FastEmbed) to re-rank retrieved documents, filtering out noise based on relevance scores.

6.  **Continuous Evaluation Pipeline (Ragas):**
    * **Automated Assessment:** An integrated scheduler runs evaluation batches using **Ragas**.
    * **Custom Testset Generator:** A custom implementation generates synthetic ground-truth pairs (Question/Answer/Context) tailored to your documents, bypassing the limitations of standard generators.
    * **Metrics:** Tracks Faithfulness, Answer Relevance, and Context Precision over time.

1.  **Secure Multi-Tenancy:**
    *   **User Authentication:** A complete authentication system (Register, Login) is built-in, using **JWT** for securing API endpoints.
    *   **Data Isolation:** Each user's data is strictly segregated. Documents are stored in user-specific paths in the S3 bucket, and vector data is indexed in separate PostgreSQL collections.

8.  **Optimized for CI/CD:** **Docker** multi-stage builds and **uv** package management ensure ultra-fast builds and reproducible environments.

9. **Deep Observability:** The system is deeply instrumented for end-to-end observability, combining metric-based monitoring with detailed tracing:
    *   **LangSmith:** For tracing, debugging, and evaluating the RAG pipeline. It provides end-to-end visibility into every step of the chain (retrieval, reranking, generation) and tools for running evaluations on key metrics like faithfulness and answer relevance.
    *   **Prometheus & Grafana:** For real-time metrics, dashboards, and alerting.
    *   **Roadmap:** Future dashboards will provide deep insights into the RAG pipeline (evaluations, performance), the LLM Gateway (token usage, costs, errors), and API metrics (latency, request rates).


---

## 🛠️ Tech Stack

| Category | Tools/Libraries | Primary Role |
| :--- | :--- | :--- |
| **User Interface** | React, TypeScript, Tailwind CSS | Modern, responsive, and scalable web application for chat and real-time document management. |
| **Authentication**| JWT, Passlib, Cryptography | Secure user registration, login, and session management. |
| **LLM Orchestration** | LiteLLM Proxy | Central hub for LLM routing, fallback, caching, and rate limiting. |
| **Embedding & Rerank**| FastEmbed (ONNX) | Lightweight, quantized inference. |
| **Reverse Proxy** | Nginx | Secure entry point, rate limiting, and future SSL/TLS termination. |
| **API Services** | FastAPI | High-performance backend for RAG logic and LLM gateway facade. |
| **Object Storage** | MinIO (S3 API) | Cloud-agnostic storage for raw documents. |
| **Vector Database** | PostgreSQL + PGVector | Multi-tenant storage, indexing, and vector search. |
| **RAG Framework** | LangChain | Orchestration of the RAG workflow (PDR, chains, etc.). |
| **Observability** | Prometheus, Grafana, LangSmith | (In progress) Monitoring, tracing, and evaluation of the entire stack. |
| **Dependency Mgmt.** | `uv`, `pyproject.toml` | High-speed, modern Python package management. |
| *(...and others)* | Docker, Redis, Ragas, Boto3... | |


---

## 🚀 Quick Start

Choose the method that fits your needs.

### ⚡ Option 1: The "Easy Way"
*Best for testing the project immediately without complex configuration.*

This project comes pre-configured to use **Groq** (specifically Llama 3 models) because it offers **free, ultra-fast inference**.

1.  **Get a Free API Key:**
    * Go to [Groq Cloud Console](https://console.groq.com/keys).
    * Create an account if you don't have one.
    * Generate a new API Key.

2.  **Configure the Environment:**
    * Create a `.env` file in the project root.
    * Add the following line, pasting your key:
        ```env
        GROQ_API_KEY=gsk_...
        ```
    *   *That's it! The system will automatically generate all other required security keys for you.*

3.  **Run:**
    ```bash
    make
    ```
    * That's it! The system handles security keys generation, database creation, and UI startup automatically.
    * Access the UI at: `http://localhost` or with `make ui`.
    * You will be greeted with a login page. Go to the "Register" tab and create your first user account, then Log in with your credentials.
    * You can now upload documents and interact with your private conversational assistant.


---

### 🔧 Option 2: Advanced Configuration (Dev)
*For developers who want to switch providers (OpenAI, Anthropic), tune RAG parameters, or change embedding models.*

#### 1. Provider Configuration
The **LiteLLM Proxy** (`deployments/litellm/litellm_config.yaml`) manages providers. You can add OpenAI, Azure, or Anthropic models there.
If you change the provider, update the corresponding API Key in `.env` (e.g., `OPENAI_API_KEY`).

#### 2. Environment Variables Reference
The service's behavior is controlled by the following environment variables. They must be defined in an .env file at the project root.

#### Provider-Specific API Keys
You **must** provide the API key for the LLM provider you intend to use. The LiteLLM Proxy will automatically detect them.

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
| **LLM_SIDE_MODEL** | `groq/meta-llama/llama-3.1-8b-instant` | Name or alias of a cheaper/caster model used for internal tasks: Query Expansion, Evaluation generation, and Data extraction. |
| **LLM_TEMPERATURE** | `0.3` | Generation temperature for the LLM. |
| **LLM_MAX_CONTEXT_TOKENS** | `30000` | **(Optional Fallback)** The system **automatically detects** the context window from the LLM Gateway at startup. This value is only used if the automatic detection fails. |
| **LLM_STRICT_RAG** | `False` | Determines whether the model can use its internal knowledge. | If **`True`**, the system instruction **forces** the model to respond ONLY with the provided context. If it cannot find the answer, it must explicitly state so (Strict RAG mode). If **`False`** (Relaxed RAG mode), the model is allowed to use its general knowledge when the context is insufficient. **WARNING**: Setting this to `False` may lead to answers that are not 100% faithful to the document and potentially increase the risk of **hallucinations**. |
| **EMBEDDING_MODEL** | `optimal` | **Choice of the embedding model used for vectorization:**<br>You can provide either a **preset alias** OR a **specific model name** supported by FastEmbed.<br><br>**1. Presets (Recommended):**<br>• **`fast`**: Ultra-fast, low RAM (Dim: 384). Ideal for weak CPUs. (Uses `e5-small`).<br>• **`optimal`**: Best balance Speed/Quality (Dim: 768). **Default**. (Uses `e5-base`).<br>• **`quality`**: Maximum precision (Dim: 1024). Slower. (Uses `e5-large`).<br><br>**2. Custom / Native:**<br>Any model name from the [FastEmbed supported list](https://qdrant.github.io/fastembed/examples/Supported_Models/#supported-text-embedding-models)<br><br>**Note:** Ensure to clean the database volume after switching models (data will be lost but the dimension is different so it's necessary). |
| **RERANKER_MODEL** | `jinaai/jina-reranker-v2-base-multilingual` | Name of the **Cross-Encoder** model used to re-rank documents. <br>**Important:** Must be supported by **FastEmbed**. <br>Recommended: `jinaai/jina-reranker-v2-base-multilingual` or `BAAI/bge-reranker-base`.<br>[See FastEmbed supported models list](https://qdrant.github.io/fastembed/examples/Supported_Models/#supported-rerank-cross-encoder-models). |
| **RERANKER_THRESHOLD** | `0.0` | **Relevance Cutoff:**<br>Documents with a score below this are discarded. <br>**Note:** Cross-Encoders output raw logits (not always 0-1). Start with `0` or negative values depending on the model. |
| **CHUNK_SIZE_P** | `1500` | **Parent Chunk Size:** Number of characters for the large chunks stored in the DocStore. Provides the full context to the LLM. |
| **CHUNK_OVERLAP_P** | `200` | **Parent Overlap:** Number of overlapping characters between parent chunks to maintain context continuity. |
| **CHUNK_SIZE_C** | `300` | **Child Chunk Size:** Number of characters for the small chunks embedded in PGVector. Ensures high-precision semantic search. |
| **CHUNK_OVERLAP_C** | `50` | **Child Overlap:** Overlap for child chunks. |
| **EVAL_TESTSET_SIZE** | `10` | Number of synthetic QA pairs to generate for the periodic Ragas evaluation runner. |
| **MINIO_ROOT_USER** | `minioadmin` | Admin username for the MinIO server. |
| **MINIO_ROOT_PASSWORD** | `minioadmin` | Admin password for the MinIO server. |
| **S3_ENDPOINT_URL** | `http://minio:9000` | S3 API endpoint. For local dev, this points to the MinIO container. |
| **S3_ACCESS_KEY_ID**| `minioadmin` | Access key for the S3 client (`boto3`). **Must match `MINIO_ROOT_USER`**. |
| **S3_SECRET_ACCESS_KEY** | `minioadmin` | Secret key for the S3 client (`boto3`). **Must match `MINIO_ROOT_PASSWORD`**. |
| **S3_BUCKET_NAME** | `rag-documents` | The name of the S3 bucket to store documents. |
| **DB_HOST** | `postgres` | Hostname of the PostgreSQL service (as defined in `docker-compose.yml`). | Database connection. |
| **DB_PORT** | `5432` | Listening port of the PostgreSQL service. | Database connection. |
| **DB_USER** | `rag_user` | Username for connecting to the PostgreSQL database. | Database access. |
| **DB_PASSWORD** | `rag_password` | Password for connecting to the PostgreSQL database. | Database access. |
| **DB_NAME** | `rag_db` | Name of the database to use within the PostgreSQL instance. | Specifies the target database. |
| **SERVICE_ACCOUNT_EMAIL** | `service@service.account` | Email to create the service user. | Used when a service needs credentials (eg. Evals). |
| **SERVICE_ACCOUNT_PASSWORD** | `service_password` | Password to create the service usef. | Used when a service needs credentials (eg. Evals). |



---

## 📂 Document Management

You can manage your knowledge base (PDF, DOCX, MD) in three ways:

1.  **Via the UI (Recommended):** Use the upload and remove features in the web interface.
2.  **Via API (Automation):**
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
3.  **Via MinIO Console:** Access `http://localhost/minio` (`make minio`) (User/Pass: `minioadmin`).
    * *Note:* If you upload via MinIO, run `make ingest` to trigger indexing manually.


---

## 📊 Observability & Evaluation

The project includes a complete monitoring stack:

1.  **Ragas Evaluation Runner:**
    * Runs in the background to evaluate the RAG pipeline (or by using `make eval`).
    * Generates a synthetic testset from your documents using the `LLM_SIDE_MODEL`.
    * Computes metrics: *Faithfulness*, *Answer Relevance*, *Context Precision*, *Context Recall* and *Answer Correctness*.

2.  **Interfaces:**
    * **Web App:** `make ui` or `http://localhost`
    * **MinIO:** `make minio` or `http://localhost/minio`
    * **Prometheus:** `make prometheus` or `http://localhost/prometheus`
    * **Grafana:** `make grafana` or `http://localhost/grafana`
    * **PGAdmin:** `make pgadmin` or `http://localhost/pgadmin`


---

## 🕹️ Commands (Makefile)

| Command | Description |
| :--- | :--- |
| `make` | **Start everything.** Builds containers and starts the stack. |
| `make down` | Stop all containers. |
| `make ingest` | Force synchronization between S3 and the Vector DB. |
| `make ui` | Open the Web UI in browser. |
| `make cli` | Run the command-line interface version of the chat *(outdated, need a security and docs management update)*. |
| `make clean-data` | **Reset Data.** Removes volumes (DB & S3). **Use this when changing embedding models.** |


---

### Preview Screenshots

<img width="1908" height="898" alt="image" src="https://github.com/user-attachments/assets/8b1c48f8-7481-418f-ad10-ceb1dbdaf1e1" />

<img width="1915" height="908" alt="image" src="https://github.com/user-attachments/assets/8d4f5d15-e2ee-47a1-af0f-613671491040" />

<img width="2198" height="1166" alt="image" src="https://github.com/user-attachments/assets/0ed09652-0a6f-464c-a266-210288f98e86" />

<img width="2206" height="1178" alt="image" src="https://github.com/user-attachments/assets/1fb0b467-96e1-41ef-82bb-c36152918678" />

