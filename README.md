# 📚 Document-Grounded Conversational Assistant (RAG)

Conversational Assistant experiment. This system uses the **RAG** (Retrieval-Augmented Generation) architecture to provide accurate, contextual responses based on your private corpus of documents (PDFs).

---

## 💡 Overview of Functioning (Advanced RAG)

***Dynamic Indexing Note:*** *The document indexing process runs **automatically every time the chat is started** (`make start-chat`). This allows you to update your reference documents (in the `data/` folder) without having to manually restart or rebuild the entire project.*

The core of the system is enhancing information retrieval for the LLM.

1.  **Indexing:** Documents are split into chunks and converted into **embeddings** (vectors).
2.  **Advanced Contextual Retrieval:** The search uses **Hybrid Embedding**, which combines:
    * **Semantic search** (understanding meaning).
    * **Keyword search** (exact term precision).
    The **Reciprocal Rank Fusion (RRF)** algorithm merges the results from both methods to ensure maximum relevance before transmitting the context to the LLM.
3.  **Augmented Generation:** The most relevant context chunks are sent to the LLM (Groq) to generate a factual and justified response.

---

## 🛠️ Key Technologies and Tools

| Category | Tools/Libraries | Primary Role |
| :--- | :--- | :--- |
| **LLM & Inference** | Groq (API) / Llama-3.1-8b-Instant | Ultra-fast response generation and reasoning. |
| **Vector Databases** | ChromaDB | Storage, indexing, and vector search for documents. |
| **RAG Framework** | LangChain | Orchestration of the complete RAG workflow. |
| **Embeddings** | Multilingual models (e.g., E5) | Creation of vector representations (supports hybrid encoding). |
| **Parsing** | PyMuPDF | Extraction of plain text and metadata from PDF files. |

---

## 🚀 Quick Start

### 1. Environment Configuration

# RAG Assistant (Retrieval-Augmented Generation)

This service implements a hybrid RAG flow using the RRF (Reciprocal Rank Fusion) algorithm to combine results from a dense search engine (vector-based, using embeddings) and a sparse search engine (keyword-based, BM25).

The service is designed to interact with a vector database (ChromaDB) and an LLM gateway (`llm-gateway`) to generate responses anchored in reference documents.

---

## Environment Variables Configuration

The service's behavior is controlled by the following environment variables. They must be defined in your `.env` file or when launching the application.

| Variable | Default Value | Description | Usage |
| :--- | :--- | :--- | :--- |
| **GROQ_API_KEY** | (None) | API key required for accessing the **Groq platform**, which hosts the selected LLM model for high-speed inference. | Authentication and authorization for LLM calls via the gateway. |
| **LLM_MODEL** | `llama-3.1-8b-instant` | Name of the LLM model to call via the gateway. Ensure this model is available in your `llm-gateway`. | Defines the model used for final response generation. |
| **EMBEDDING_MODEL** | `intfloat/multilingual-e5-large` | Name of the model used to generate vector embeddings for indexing and querying documents. | Defines the embedding function used by the vector database (ChromaDB) for dense search. |
| **MAX_CONTEXT_TOKENS** | `4000` | Maximum context size (in tokens) that the LLM can accept. **Important**: This value is used to determine the maximum number of document chunks (`CHUNK_SIZE`) to include in the prompt. | Limits the amount of document content sent to the LLM to prevent context overflow. |
| **CHUNK_SIZE** | `1000` | Estimated size (in tokens) of an indexed document chunk. | Used to calculate the number of chunks to select: `MAX_CONTEXT_TOKENS / CHUNK_SIZE`. |
| **LLM_STRICT_RAG** | `True` | Determines whether the model can use its internal knowledge. If **`True`**, the system instruction **forces** the model to respond ONLY with the provided context. If it cannot find the answer, it must explicitly state so (Strict RAG mode). If **`False`** (Relaxed RAG mode), the model is allowed to use its general knowledge when the context is insufficient. **WARNING**: Setting this to `False` may lead to answers that are not 100% faithful to the document and potentially increase the risk of **hallucinations**. |

Define your API key and parameters in a **`.env`** file at the **project root**.

### 2. Adding Source Documents

Place all your **PDF files** in the directory:

```bash
data/
```

### 3. Running the Service

Use the provided Makefile commands to set up the environment, process documents, and start the chat application.

1. **Build Docker Project:**

```bash
make
```

2. **Start the Conversational Chat Interface (and run dynamic indexing):**

```bash
make start-chat
```

