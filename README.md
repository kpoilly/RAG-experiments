# 📚 Document-Grounded Conversational Assistant (RAG)

Conversational Assistant experiment. This system uses the **RAG** (Retrieval-Augmented Generation) architecture to provide accurate, contextual responses based on your private corpus of documents (PDFs).

---

## 💡 Overview of Functioning (Advanced RAG)

***Note on Smart & Dynamic Ingestion:*** *The document indexing process runs **automatically when the RAG service starts**. It can also be triggered at any time via the Streamlit UI or an API endpoint (`/ingest`). This allows you to update your reference documents in real-time by adding or removing them from the `data/` folder or the UI. The assistant will benefit from the new knowledge without any service interruption.*

The core of the system is enhancing information retrieval for the LLM.

1.  **Provider-Agnostic LLM Gateway:** At the core is a sophisticated LLM Gateway powered by the **LiteLLM Proxy**. This proxy manages all interactions with large language models, providing:
    *   **Unified API:** An OpenAI-compatible interface for over 100+ LLM providers.
    *   **Load Balancing & Fallback:** Automatically routes requests and retries with fallback models if a primary provider fails or is rate-limited.
    *   **Caching:** Integrates with **Redis** for semantic caching, reducing latency and API costs.

2.  **Smart & Dynamic Ingestion:** The document indexing process is fully automated. It can be triggered via the Streamlit UI or by placing files in the `data/` folder and running `make ingest`. The system intelligently detects added, modified, or deleted files to update only what is necessary.

3.  **Indexing with Parent Document Retriever (PDR):** Documents are processed using an advanced chunking strategy for optimal retrieval quality:
    *   **Parent Chunks:** Documents are split into larger chunks to capture rich context, stored in a **PostgreSQL `docstore` table**.
    *   **Child Chunks:** Each parent is split into smaller, precise chunks. Their **embeddings** are indexed in **PostgreSQL with PGVector**.

4.  **Advanced Retrieval Pipeline:**
    *   **Query Expansion:** The user's question is expanded by an LLM to create multiple search queries.
    *   **Retrieval:** The **Parent Document Retriever** finds relevant child chunks via vector search and fetches their corresponding parent chunks.
    *   **Re-Ranking & Filtering:** A **Cross-Encoder** model re-ranks the retrieved parent documents for maximum relevance, filtering out those below a configurable threshold.

5.  **Augmented Generation:** The final, highly-relevant context is sent through the gateway to the selected LLM to generate a factual, streaming response.

---

## 🛠️ Key Technologies and Tools

| Category | Tools/Libraries | Primary Role |
| :--- | :--- | :--- |

| **User Interface** | Streamlit | Provides an interactive web UI for chat and document management. |
| **LLM Orchestration** | LiteLLM Proxy | Central hub for LLM routing, fallback, caching, and rate limiting. |
| **LLM & Inference** | Any LiteLLM Provider (e.g., Groq, OpenAI, Anthropic, etc.) | Ultra-fast response generation and reasoning. |
| **API Gateway** | FastAPI | A lightweight facade in front of the LiteLLM Proxy for custom logic (security, billing, etc.). |
| **Document Storage** | PostgreSQL | Robust, transactional storage for parent chunks (DocStore). |
| **Vector Database** | PostgreSQL + PGVector | Storage, indexing, and vector search for child chunks. |
| **Embeddings** | Multilingual models (e.g., E5) | Creation of vector representations (supports hybrid seaarch). |
| **Chunking Strategies** | `RecursiveCharacterTextSplitter` | Creates predictable parent and child chunks for PDR. |
| **Reranking & Filtering**| BAAI/bge-reranker-v2-m3 (Cross-Encoder) | Refines search results by calculating a precise relevance score for each document. |
| **Caching** | Redis | Caches LLM responses to reduce latency and cost. |
| **RAG Framework** | LangChain | Orchestration of the RAG workflow (PDR, chains, etc.). |
| **Parsing** | PyPDF, Unstructured | Extraction of text from various file formats (.pdf, .docx, .md). |
| **Observability** | LangSmith | Tracing, debugging, and evaluating the RAG pipeline. |

---

## 🚀 Quick Start

### 1. Environment Variables Configuration

The service's behavior is controlled by the following environment variables. They must be defined in your `.env` file or when launching the application.

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
| **LLM_MODEL** | `groq/llama-3.1-8b-instant` | Name of the LLM model to call via the gateway, or its **alias** as defined in `litellm_config.yaml`. |
| **LLM_TEMPERATURE** | `0.3` | Temperature setting for the generated answer. |
| **LLM_MAX_CONTEXT_TOKENS** | `30000` | Maximum context size (in tokens) that the LLM can accept. **Important**: This value is used to determine the maximum number of document chunks (`CHUNK_SIZE`) to include in the prompt. | Limits the amount of document content sent to the LLM to prevent context overflow. |
| **LLM_STRICT_RAG** | `False` | Determines whether the model can use its internal knowledge. | If **`True`**, the system instruction **forces** the model to respond ONLY with the provided context. If it cannot find the answer, it must explicitly state so (Strict RAG mode). If **`False`** (Relaxed RAG mode), the model is allowed to use its general knowledge when the context is insufficient. **WARNING**: Setting this to `False` may lead to answers that are not 100% faithful to the document and potentially increase the risk of **hallucinations**. |
| **EMBEDDING_MODEL** | `intfloat/multilingual-e5-small` | Name of the model used to generate vector embeddings for indexing and querying documents. | Defines the embedding function used by the vector database (ChromaDB) for dense search. |
| **RERANKER_MODEL** | `BAAI/bge-reranker-v2-m3` | Name of the **Cross-Encoder** model used to re-rank documents and calculate a precise relevance score. | Refines the list of documents retrieved before sending them to the LLM. |
| **RERANKER_THRESHOLD** | `0.4` | Minimum relevance score (float between 0.0 and 1.0) required for a document to be included in the final context. | Filters out documents considered irrelevant by the reranker. A higher value leads to stricter, more relevant context, but risks omitting potentially useful information. |
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

You have two ways to add documents:

1.  **Manually:** Place your **PDF, DOCX, or MD files** in the `data/` directory and run `make ingest`.
2.  **Via the UI:** Use the upload feature in the Streamlit interface once the application is running.

### 4. Running the Service

Use the provided Makefile commands to set up the environment, process documents, and start the chat application.

1. **Launch the project:**

```bash
make
```
This single command builds and starts all services (RAG Core, LiteLLM Proxy, Streamlit UI, etc.), runs the initial document ingestion, and automatically opens the web interface in your browser at `http://localhost:8501`.

2.  **Using the Interface:**
    *   The main page provides a **chat interface** to interact with the assistant.
    *   The **"Document Management"** panel on the right allows you to **upload** new files or **remove** existing ones. Uploading or removing documents will automatically trigger a re-ingestion process to update the assistant's knowledge base.
    *   You can reopen the interface at any time with `make ui`

3.   **Using the CLI:**
      *   You can also use the **CLI interface** directly in your terminal.
      *   Open a new chat with the CLI by using `make cli` 

5.  **Stopping the Service:**
    ```bash
    make down
    ```

### Preview Screenshots

<img width="1908" height="898" alt="image" src="https://github.com/user-attachments/assets/8b1c48f8-7481-418f-ad10-ceb1dbdaf1e1" />

