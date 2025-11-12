# 📚 Document-Grounded Conversational Assistant (RAG)

Conversational Assistant experiment. This system uses the **RAG** (Retrieval-Augmented Generation) architecture to provide accurate, contextual responses based on your private corpus of documents (PDFs).

---

## 💡 Overview of Functioning (Advanced RAG)

***Note on Smart & Dynamic Ingestion:*** *The document indexing process runs **automatically when the RAG service starts**. It can also be triggered at any time via the Streamlit UI or an API endpoint (`/ingest`). This allows you to update your reference documents in real-time by adding or removing them from the `data/` folder or the UI. The assistant will benefit from the new knowledge without any service interruption.*

The core of the system is enhancing information retrieval for the LLM.

1.  **Indexing with Parent Document Retriever (PDR):** Documents are processed through a sophisticated chunking strategy:
    *   **Parent Chunks:** Documents are initially split into larger, semantically coherent chunks (e.g., 2000 characters with overlap) to capture broader context. These are stored in a **PostgreSQL `docstore` table**.
    *   **Child Chunks:** Each parent chunk is then further split into smaller, precise chunks (e.g., 300 characters with overlap). These smaller chunks are converted into **embeddings** (vectors) and indexed in a **PostgreSQL `PGVector` collection** for efficient retrieval.
    This two-tier approach allows for precise retrieval of relevant information while providing rich, contextual parent chunks to the LLM.
2.  **Query Expansion :** Before searching, the user's original question is sent to an LLM to generate several alternative versions. This technique helps overcome the limitations of keyword or semantic search by exploring different formulations of the same intent, thus casting a wider net to find the most relevant documents.
3.  **Advanced Contextual Retrieval:** The search is performed using the **Parent Document Retriever**, which retrieves the most relevant **child chunks** via vector search (on `PGVector`) and then fetches their corresponding **parent chunks** from the `PostgreSQL DocStore`.
4.  **Re-Ranking & Filtering:** To further refine the results, a **Cross-Encoder** model re-ranks the documents retrieved in the previous step. It calculates a precise relevance score for each document in relation to the query. Only documents with a score exceeding a configurable **threshold** are kept, ensuring that only the most relevant information is passed to the LLM.
5.  **Augmented Generation:** The most relevant context chunks are sent to the LLM (Groq) to generate a factual and justified response. The answer is delivered in real-time via **streaming**, ensuring an interactive and fluid user experience with very low latency.

---

## 🛠️ Key Technologies and Tools

| Category | Tools/Libraries | Primary Role |
| :--- | :--- | :--- |
| **User Interface** | Streamlit | Provides an interactive web UI for chat and document management. |
| **LLM Gateway** | LiteLLM | Provides a unified, OpenAI-compatible API to interact with 100+ LLM providers (Groq, OpenAI, Anthropic, etc.). |
| **LLM & Inference** | Any LiteLLM Provider (e.g., Groq) | Ultra-fast response generation and reasoning. |
| **Document Storage** | PostgreSQL | Robust, transactional storage for parent chunks and metadata. |
| **Vector Database** | PostgreSQL + PGVector | Robust, transactional storage, indexing, and vector search for documents. |
| **RAG Framework** | LangChain | Orchestration of the complete RAG workflow. |
| **Chunking Strategies** | `RecursiveCharacterTextSplitter` | Creates predictable parent and child chunks for PDR. |
| **Embeddings** | Multilingual models (e.g., E5) | Creation of vector representations (supports hybrid seaarch). |
| **Reranking & Filtering**| BAAI/bge-reranker-v2-m3 (Cross-Encoder) | Refines search results by calculating a precise relevance score for each document. |
| **Parsing** | PyPDF, Unstructured | Extraction of text from various file formats (.pdf, .docx, .md). |
| **Observability** | LangSmith | Tracing, debugging, and evaluating RAG pipeline execution. |

---

## 🚀 Quick Start

### 1. Environment Variables Configuration

The service's behavior is controlled by the following environment variables. They must be defined in your `.env` file or when launching the application.

#### Provider-Specific API Keys
You must provide the API key for the LLM provider you intend to use. LiteLLM automatically detects these standard environment variables.

| Variable | Example | Description |
| :--- | :--- | :--- |
| **GROQ_API_KEY** | `gsk_...` | API key for the Groq platform. |
| **OPENAI_API_KEY** | `sk-...` | API key for the OpenAI platform. |
| **ANTHROPIC_API_KEY** | `sk-ant-...` | API key for the Anthropic platform. |
| *(and others...)* | | See LiteLLM documentation for more. |

#### Main Application Configuration

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| **LLM_MODEL** | `groq/llama-3.1-8b-instant` | **Crucial.** Name of the LLM model to call via the gateway, prefixed with the provider. Examples: `groq/llama-3.1-8b-instant`, `gpt-4o`, `claude-3-opus-20240229`. || **EMBEDDING_MODEL** | `intfloat/multilingual-e5-small` | Name of the model used to generate vector embeddings for indexing and querying documents. | Defines the embedding function used by the vector database (ChromaDB) for dense search. |
| **MAX_CONTEXT_TOKENS** | `4000` | Maximum context size (in tokens) that the LLM can accept. **Important**: This value is used to determine the maximum number of document chunks (`CHUNK_SIZE`) to include in the prompt. | Limits the amount of document content sent to the LLM to prevent context overflow. |
| **LLM_STRICT_RAG** | `True` | Determines whether the model can use its internal knowledge. | If **`True`**, the system instruction **forces** the model to respond ONLY with the provided context. If it cannot find the answer, it must explicitly state so (Strict RAG mode). If **`False`** (Relaxed RAG mode), the model is allowed to use its general knowledge when the context is insufficient. **WARNING**: Setting this to `False` may lead to answers that are not 100% faithful to the document and potentially increase the risk of **hallucinations**. |
| **RERANKER_MODEL** | `BAAI/bge-reranker-v2-m3` | Name of the **Cross-Encoder** model used to re-rank documents and calculate a precise relevance score. | Refines the list of documents retrieved before sending them to the LLM. |
| **RERANKER_THRESHOLD** | `0.4` | Minimum relevance score (float between 0.0 and 1.0) required for a document to be included in the final context. | Filters out documents considered irrelevant by the reranker. A higher value leads to stricter, more relevant context, but risks omitting potentially useful information. |
| **DB_HOST** | `postgres` | Hostname of the PostgreSQL service (as defined in `docker-compose.yml`). | Database connection. |
| **DB_PORT** | `5432` | Listening port of the PostgreSQL service. | Database connection. |
| **DB_USER** | `user` | Username for connecting to the PostgreSQL database. | Database access. |
| **DB_PASSWORD** | `password` | Password for connecting to the PostgreSQL database. | Database access. |
| **DB_NAME** | `rag_db` | Name of the database to use within the PostgreSQL instance. | Specifies the target database. |
| **COLLECTION_NAME** | `rag_documents` | Name of the logical "collection" within PGVector. This isolates the project's documents. | Filters searches to only include documents from this project. |

Define your API key and parameters in a **`.env`** file at the **project root**.

### 2. Adding Source Documents

You have two ways to add documents:

1.  **Manually:** Place your **PDF, DOCX, or MD files** in the `data/` directory before starting the service and use the folowing command to run a new ingestion.
```bash
make ingest
```
2.  **Via the UI:** Use the upload feature in the Streamlit interface once the application is running.


### 3. Running the Service

Use the provided Makefile commands to set up the environment, process documents, and start the chat application.

1. **Build, Start, and Run the Chat Interface:**

```bash
make
```
This single command will perform all the necessary steps. Build all the Docker images, start all services, run the initial document ingestion based on the content of the `data/` folder and automatically open the **Streamlit web interface** in your browser at `http://localhost:8501`.

2.  **Using the Interface:**
    *   The main page provides a **chat interface** to interact with the assistant.
    *   The **"Document Management"** panel on the right allows you to **upload** new files or **remove** existing ones. Uploading or removing documents will automatically trigger a re-ingestion process to update the assistant's knowledge base.
    *   You can reopen the interface at any time with `make ui`

3.   **Using the CLI:**
    *   You can also use the CLI interface directly in your terminal.
    *   Open a new chat with the CLI by using `make cli` 

4.  **Stopping the Service:**
    ```bash
    make down
    ```

### Preview Screenshots

<img width="1908" height="898" alt="image" src="https://github.com/user-attachments/assets/8b1c48f8-7481-418f-ad10-ceb1dbdaf1e1" />

