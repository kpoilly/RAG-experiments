import json
import os
import time
from urllib.parse import quote

import requests
import streamlit as st

# --- Config ---

API_URL = os.getenv("API_URL", "http://nginx/api")
HEALTH_URL = f"{API_URL}/health"
AUTH_URL = f"{API_URL}/auth"
DOCUMENTS_URL = f"{API_URL}/documents"
CHAT_URL = f"{API_URL}/chat"
HISTORY_URL = f"{API_URL}/history"


# --- API ---


def get_api_headers():
    if "auth_token" not in st.session_state:
        return None
    return {"Authorization": f"Bearer {st.session_state['auth_token']}"}


def register_user(email, password):
    try:
        response = requests.post(f"{AUTH_URL}/register", json={"email": email, "password": password})
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        st.error(f"Registration failed: {e.response.json().get('detail') if e.response else e}")
        return False


def login_user(email, password):
    try:
        response = requests.post(f"{AUTH_URL}/token", data={"username": email, "password": password})
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.RequestException as e:
        st.error(f"Login failed: {e.response.json().get('detail') if e.response else e}")
        return None


# --- App Pages ---


def display_login_page():
    _, col_center, _ = st.columns([1, 2, 1], gap="medium")
    with col_center:
        st.title("Conversational RAG Assistant")
        login_tab, register_tab = st.tabs(["Login", "Register"])

        with login_tab:
            with st.form("login_form"):
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Login")
                if submitted:
                    token = login_user(email, password)
                    if token:
                        st.session_state["auth_token"] = token
                        st.session_state["user_email"] = email
                        st.success("Login successful!")
                        time.sleep(1)
                        st.rerun()

        with register_tab:
            with st.form("register_form"):
                email = st.text_input("Email", key="reg_email")
                password = st.text_input("Password", type="password", key="reg_password")
                submitted = st.form_submit_button("Register")
                if submitted:
                    if register_user(email, password):
                        st.success("Registration successful! Please proceed to the Login tab.")
                        time.sleep(2)


def display_main_app():
    with st.sidebar:
        st.title("Conversational RAG Assistant")

        st.write(f"Logged in as: {st.session_state.get('user_email', 'Unknown')}")
        if st.button("Logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        if st.button("Clear Chat History", type="secondary"):
            try:
                headers = get_api_headers()
                response = requests.delete(HISTORY_URL, headers=headers)
                response.raise_for_status()

                if "messages" in st.session_state:
                    del st.session_state["messages"]

                st.success("Chat history cleared!")
                time.sleep(1)
                st.rerun()
            except requests.RequestException:
                st.error("Failed to clear history. Please try again.")

        st.divider()
        page = st.radio("Navigation", ["💬 Chat", "⚙️ Settings", "ℹ️ Info"])

    if page == "💬 Chat":
        display_chat_page()
    elif page == "⚙️ Settings":
        display_settings_page()
    elif page == "ℹ️ Info":
        display_info_page()


def display_chat_page():
    st.title("🤖 Chat")

    @st.cache_data(ttl=10)
    def get_current_documents():
        """get current document filenames."""
        headers = get_api_headers()
        if not headers:
            return []
        try:
            response = requests.get(DOCUMENTS_URL, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            st.error(f"Error fetching document list: {e}")
            return []

    col_chat, col_docs = st.columns([0.7, 0.3])

    if "messages" not in st.session_state:
        try:
            headers = get_api_headers()
            response = requests.get(HISTORY_URL, headers=headers)
            response.raise_for_status()
            st.session_state.messages = response.json()
        except requests.RequestException:
            st.session_state.messages = []
            st.warning("Could not load chat history.")

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
                        headers = get_api_headers()
                        request_payload = {
                            "query": prompt,
                            "temperature": st.session_state.llm_temperature,
                            "strict_rag": st.session_state.llm_strict_rag,
                            "rerank_threshold": st.session_state.rerank_threshold,
                        }
                        with requests.post(CHAT_URL, json=request_payload, headers=headers, stream=True, timeout=120) as response:
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
            uploaded_file = st.file_uploader("Upload files...", accept_multiple_files=False, type=["pdf", "md", "docx"], label_visibility="collapsed")
            submitted = st.form_submit_button("Add")
            if submitted and uploaded_file:
                with st.spinner("Uploading and processing documents..."):
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    try:
                        headers = get_api_headers()
                        response = requests.post(DOCUMENTS_URL, files=files, headers=headers)
                        response.raise_for_status()
                    except requests.RequestException as e:
                        st.error(f"Failed to process {uploaded_file.name}: {e.response.text if e.response else e}")

                st.success("Documents processed successfully!")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()

        st.subheader("Remove Documents")
        docs_to_delete = st.multiselect("Select documents to remove:", get_current_documents())
        if st.button("Remove Selected", type="primary"):
            with st.spinner("Removing documents..."):
                for doc_name in docs_to_delete:
                    try:
                        headers = get_api_headers()
                        delete_url = f"{DOCUMENTS_URL}/{quote(doc_name)}"
                        response = requests.delete(delete_url, headers=headers)
                        response.raise_for_status()
                    except requests.RequestException as e:
                        st.error(f"Failed to remove {doc_name}: {e}")

            st.success("Documents removed successfully!")
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()


def display_settings_page():
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
    st.session_state.rerank_threshold = st.slider(
        label="Reranker Threshold", min_value=-10.0, max_value=10.0, step=0.05, value=st.session_state.rerank_threshold, width=500
    )
    st.text_input("Chunk Size (Parent)", value=os.getenv("CHUNK_SIZE_P", "Not Set"), disabled=True)
    st.text_input("Overlap (Parent)", value=os.getenv("CHUNK_OVERLAP_P", "Not Set"), disabled=True)
    st.text_input("Chunk Size (Child)", value=os.getenv("CHUNK_SIZE_C", "Not Set"), disabled=True)
    st.text_input("Overlap (Child)", value=os.getenv("CHUNK_OVERLAP_C", "Not Set"), disabled=True)


def display_info_page():
    st.title("ℹ️ About This Project")

    st.info(
        """
        This project is a **production-ready boilerplate** for a multi-tenant,
        document-grounded conversational assistant (RAG).

        It is built on a modern, cloud-native architecture designed for scalability, observability, and flexibility.

        Core Architectural Principles:

        - **Cloud-Agnostic Design:** Using S3-compatible object storage and PostgreSQL allowing for seamless deployment to any major cloud provider (AWS, GCP, Azure)..
        - **Advanced RAG Pipeline:** Advanced PDR retrieval workflow with query expansion and Cross-Encoder re-ranking.
        - **Deep Observability:** Prometheus & Grafana for real-time metrics, and LangSmith for end-to-end tracing and evaluation of the RAG pipeline.
        - **Optimized for CI/CD and Dev Experience:** Built for efficiency with multi-stage Docker builds and `uv` for high-speed dependency management
        """
    )
    st.success("For a complete technical overview, check out the [GitHub repository](https://github.com/kpoilly/RAG-Boilerplate).")


# --- Init ---

st.set_page_config(page_title="Conversational RAG Assistant", page_icon="🤖", layout="wide")

st.markdown(
    """
<style>
    .block-container { padding-top: 1rem; }
    h1 { padding-top: 0rem; }
</style>
""",
    unsafe_allow_html=True,
)

if "llm_temperature" not in st.session_state:
    st.session_state.llm_temperature = float(os.getenv("LLM_TEMPERATURE", 0.3))
if "llm_strict_rag" not in st.session_state:
    st.session_state.llm_strict_rag = os.getenv("LLM_STRICT_RAG", "True").lower() == "true"
if "rerank_threshold" not in st.session_state:
    st.session_state.rerank_threshold = float(os.getenv("RERANKER_THRESHOLD", 0.4))

if "auth_token" not in st.session_state:
    display_login_page()
else:
    display_main_app()
