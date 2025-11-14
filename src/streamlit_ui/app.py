import json
import os
import time

import requests
import streamlit as st

# --- Config ---

API_URL = os.getenv("API_URL", "http://nginx/api")
CHAT_URL = f"{API_URL}/chat"
INGEST_URL = f"{API_URL}/ingest"
HEALTH_URL = f"{API_URL}/health"

DATA_PATH = "/app/data"

# --- Utils ---


@st.cache_data(ttl=10)
def get_current_documents():
    """get current document filenames in the data directory."""
    try:
        return sorted([f for f in os.listdir(DATA_PATH) if os.path.isfile(os.path.join(DATA_PATH, f)) and f.lower().endswith((".pdf", ".docx", ".md"))])
    except FileNotFoundError:
        st.error(f"Data directory not found at {DATA_PATH}")
        return []


def trigger_ingestion():
    """Call the RAG Core ingestion endpoint to process documents."""
    try:
        response = requests.post(INGEST_URL)
        response.raise_for_status()
        return True, response.json()
    except requests.RequestException as e:
        return False, str(e)


# --- Init ---

st.set_page_config(page_title="Conversational RAG Assistant", page_icon="🤖", layout="wide")

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1rem; /* Réduit l'espace en haut de la page */
        }
        h1 {
            padding-top: 0rem; /* Réduit l'espace au-dessus du titre */
        }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("RAG")
    page = st.radio("Navigation", ["💬 Chat", "⚙️ Settings", "ℹ️ Info"])


if "messages" not in st.session_state:
    st.session_state.messages = []
if "upload_processed" not in st.session_state:
    st.session_state.upload_processed = False
if "llm_temperature" not in st.session_state:
    st.session_state.llm_temperature = float(os.getenv("LLM_TEMPERATURE", 0.3))
if "llm_strict_rag" not in st.session_state:
    st.session_state.llm_strict_rag = os.getenv("LLM_STRICT_RAG", "True").lower() == "true"
if "rerank_threshold" not in st.session_state:
    st.session_state.rerank_threshold = float(os.getenv("RERANKER_THRESHOLD", 0.4))


# --- Main Page ---

if page == "💬 Chat":
    st.title("🤖 Chat")
    col_chat, col_docs = st.columns([0.7, 0.3])

    with col_chat:
        chat_container = st.container(height=600)
        with chat_container:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        if prompt := st.chat_input("Ask a question about your documents..."):
            st.session_state.messages.append({"role": "user", "content": prompt})

            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
            with chat_container:
                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    full_response = ""
                    try:
                        api_history = [{"role": msg["role"], "content": msg["content"]} for msg in st.session_state.messages]
                        request_payload = {
                            "query": prompt,
                            "history": api_history,
                            "temperature": st.session_state.llm_temperature,
                            "strict_rag": st.session_state.llm_strict_rag,
                            "rerank_threshold": st.session_state.rerank_threshold,
                        }
                        with requests.post(CHAT_URL, json=request_payload, stream=True, timeout=120) as response:
                            response.raise_for_status()
                            for line in response.iter_lines():
                                decoded_line = line.decode("utf-8")
                                if decoded_line.startswith("data:"):
                                    json_str = decoded_line[6:].strip()
                                    if "[DONE]" in json_str:
                                        break
                                    if not json_str:
                                        continue
                                    try:
                                        data = json.loads(json_str)
                                        content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if content:
                                            full_response += content
                                            message_placeholder.markdown(full_response + "▌")
                                    except json.JSONDecodeError:
                                        continue
                        message_placeholder.markdown(full_response)
                    except requests.RequestException as e:
                        full_response = f"Error: {e}"
                        message_placeholder.error("RAG Service is not up yet. Please try again later.")

            st.session_state.messages.append({"role": "assistant", "content": full_response})

    with col_docs:
        st.header("📄 Documents")

        st.subheader("Current Documents")
        with st.expander("Show/Hide documents", expanded=False):
            st.write(get_current_documents() or ["No documents found."])

        st.subheader("Add Documents")
        with st.form("upload_form", clear_on_submit=True):
            uploaded_files = st.file_uploader("Upload files...", accept_multiple_files=True, type=["pdf", "md", "docx"], label_visibility="collapsed")
            submitted = st.form_submit_button("Add")
            if submitted and uploaded_files:
                for uploaded_file in uploaded_files:
                    with open(os.path.join(DATA_PATH, uploaded_file.name), "wb") as f:
                        f.write(uploaded_file.getbuffer())

                with st.spinner("Processing documents... This may take a few minutes."):
                    success, _ = trigger_ingestion()

                st.cache_data.clear()
                if success:
                    st.success("✅ Ingestion successful!")
                else:
                    st.error("❌ Ingestion failed.")
                time.sleep(2)
                st.rerun()

        st.subheader("Remove Documents")
        docs_to_delete = st.multiselect("Select documents to remove:", get_current_documents())
        if st.button("Remove Selected", type="primary"):
            if docs_to_delete:
                for doc_name in docs_to_delete:
                    os.remove(os.path.join(DATA_PATH, doc_name))
                with st.spinner("Updating knowledge base..."):
                    trigger_ingestion()
                st.cache_data.clear()
                st.rerun()

elif page == "⚙️ Settings":
    st.title("⚙️ Application Settings")
    st.info(
        "These settings are read from the environment variables at startup. To change them, please update your `.env`\
              file and restart the Docker services with `docker-compose up --build`."
    )

    st.subheader("Models")
    st.text_input("LLM Model", value=os.getenv("LLM_MODEL", "Not Set"), disabled=True)
    st.text_input("Embedding Model", value=os.getenv("EMBEDDING_MODEL", "Not Set"), disabled=True)
    st.text_input("Reranker Model", value=os.getenv("RERANKER_MODEL", "Not Set"), disabled=True)

    st.subheader("RAG Behavior")
    st.session_state.llm_strict_rag = st.toggle(
        "Strict RAG Mode",
        value=st.session_state.llm_strict_rag,
        help="If enabled, \
            the assistant is strictly forbidden from using any knowledge outside of the provided documents.",
    )
    st.session_state.llm_temperature = st.slider(label="LLM Temperature", min_value=0.0, max_value=2.0, step=0.05, value=st.session_state.llm_temperature, width=500)
    st.session_state.rerank_threshold = st.slider(label="Reranker Threshold", min_value=0.0, max_value=1.0, step=0.05, value=st.session_state.rerank_threshold, width=500)
    st.text_input("Chunk Size (Parent)", value=os.getenv("CHUNK_SIZE_P", "Not Set"), disabled=True)
    st.text_input("Overlap (Parent)", value=os.getenv("CHUNK_OVERLAP_P", "Not Set"), disabled=True)
    st.text_input("Chunk Size (Child)", value=os.getenv("CHUNK_SIZE_C", "Not Set"), disabled=True)
    st.text_input("Overlap (Child)", value=os.getenv("CHUNK_OVERLAP_C", "Not Set"), disabled=True)

elif page == "ℹ️ Info":
    st.title("ℹ️ About This Project")
    st.info(
        "This is a boilerplate for a production-ready RAG conversational assistant. It uses a Parent Document Retrieval strategy with a PostgreSQL+PGVector backend,\
              and a provider-agnostic LLM Gateway powered by LiteLLM."
    )
    st.markdown("For more details, check out the [GitHub repository](https://github.com/kpoilly/RAG-experiments).")
