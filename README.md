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

Define your API key and parameters in a **`.env`** file at the project root:

```
GROQ_API_KEY (Mandatory)
LLM_MODEL (Optional, default is "llama-3.1-8b-instant")
EMBEDDING_MODEL (Optional, default is "intfloat/multilingual-e5-large")
MAX_CONTEXT_TOKEN (Optional, default is 4000)
CHUNK_SIZE (Optional, default is 1000)
CHUNK_OVERLAP (Optional, default is 200)
```

### 2. Adding Source Documents

Place all your **PDF files** in the directory:

```bash
data/
```

### 3. Running the Service

Use the provided Makefile commands to set up the environment, process documents, and start the chat application.

1. **Build Environment (Install Dependencies):**

```bash
make
```

2. **Start the Conversational Chat Interface (and run dynamic indexing):**

```bash
make start-chat
```

