import os
import math
import time
import logging
import requests
import json
import tempfile
import random
import asyncio
from typing import List, Dict, Any

import boto3

from fastembed import TextEmbedding
from fastembed.common.model_description import PoolingType, ModelSource
from datasets import Dataset
from ragas import evaluate, RunConfig
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall, answer_correctness
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

from langchain_core.embeddings import Embeddings
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader, UnstructuredMarkdownLoader
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_openai import ChatOpenAI
from langchain_classic.prompts import ChatPromptTemplate
from langchain_classic.output_parsers import ResponseSchema, StructuredOutputParser

from metrics import (
    EVAL_FAITHFULNESS,
    EVAL_ANSWER_RELEVANCY,
    EVAL_CONTEXT_PRECISION,
    EVAL_CONTEXT_RECALL,
    EVAL_ANSWER_CORRECTNESS,
    EVALUATION_RUNS_TOTAL,
)
from config import settings as env
from config import MODELS_CONFIG


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Dumb fix 1 - random pydantic crash
class SafeFastEmbed(Embeddings):
    def __init__(self, model_name: str):
        self.model = model_name
        self._client = FastEmbedEmbeddings(model_name=model_name)
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._client.embed_documents(texts)
    def embed_query(self, text: str) -> List[float]:
        return self._client.embed_query(text)


# --- Utils ---
def get_s3_client():
    """
    Create a boto3 client for Minio/S3
    """
    return boto3.client("s3", endpoint_url=env.S3_ENDPOINT_URL, aws_access_key_id=env.S3_ACCESS_KEY_ID, aws_secret_access_key=env.S3_SECRET_ACCESS_KEY)


def load_documents_from_s3(sample_size: int = 5) -> List:
    """
    Loads a sample of documents from S3 to generate evaluation dataset.
    """
    logger.info(f"Loading up to {sample_size} documents from S3 bucket '{env.S3_BUCKET_NAME}'...")
    s3_client = get_s3_client()
    documents = []
    
    loader_map = {
        ".pdf": PyPDFLoader,
        ".docx": UnstructuredWordDocumentLoader,
        ".md": UnstructuredMarkdownLoader,
    }
    
    try:
        response = s3_client.list_objects_v2(Bucket=env.S3_BUCKET_NAME)
        files_to_process = [obj["Key"] for obj in response.get("Contents", [])][:sample_size]

        with tempfile.TemporaryDirectory() as temp_dir:
            for file_key in files_to_process:
                file_ext = os.path.splitext(file_key)[1].lower()
                if file_ext not in loader_map:
                    logger.warning(f"Unsupported file type for '{file_key}' in S3 bucket, skipping.")
                    continue

                local_path = os.path.join(temp_dir, file_key.replace("/", "_"))
                logger.info(f"Downloading {file_key}...")
                s3_client.download_file(env.S3_BUCKET_NAME, file_key, local_path)
                
                loader_class = loader_map[file_ext]
                loader = loader_class(local_path)
                documents.extend(loader.load())

        logger.info(f"Successfully loaded {len(documents)} document pages from {len(files_to_process)} files.")
        return documents
    except Exception as e:
        logger.error(f"Failed to load documents from S3: {e}", exc_info=True)
        return []
    

def configure_embedding_model(user_choice: str):
    """
    """
    user_choice = user_choice.lower().strip()
    if user_choice not in MODELS_CONFIG:
        logger.info(f"Model '{user_choice}' not an alias.")
        return

    config = MODELS_CONFIG[user_choice]
    logger.info(f"Model config: '{user_choice}' -> {config['name']} (Dim: {config['dim']})")

    TextEmbedding.add_custom_model(
        model=config["name"], 
        pooling=PoolingType.MEAN,
        normalization=True,
        dim=config["dim"],
        sources=ModelSource(hf=config["source"]),
        model_file=config["filename"]
    )
    env.EMBEDDING_MODEL = config["name"]


# --- Eval ---
def generate_synthetic_testset(documents: List, generator_llm: ChatOpenAI, size: int) -> List[Dict]:
    """
    Génère des questions/réponses via un prompt simple, sans passer par la machinerie complexe de Ragas.
    """
    logger.info(f"Generating {size} synthetic Q&A pairs manually...")
    
    response_schemas = [
        ResponseSchema(name="question", description="A clear question based on the text."),
        ResponseSchema(name="ground_truth", description="The precise answer found in the text.")
    ]
    output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
    format_instructions = output_parser.get_format_instructions()

    prompt = ChatPromptTemplate.from_template(
        """You are an evaluation expert. Generate a question and its answer based ONLY on the following context.
        
        Context:
        {context}
        
        {format_instructions}
        """
    )
    chain = prompt | generator_llm | output_parser

    chunks = documents.copy()
    while len(chunks) < size:
        chunks.extend(documents)
    random.shuffle(chunks)
    selected_chunks = chunks[:size]

    results = []
    for i, doc in enumerate(selected_chunks):
        try:
            output = chain.invoke({"context": doc.page_content[:2000], "format_instructions": format_instructions})
            results.append(output)
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Generation failed for chunk {i}: {e}")
    return results


def run_rag_pipeline(question: str) -> Dict[str, Any]:
    answer = ""
    contexts = []
    try:
        response = requests.post(f"{env.RAG_CORE_URL}/chat",
                                 json={"query": question, "history": []},stream=True, timeout=120)
        response.raise_for_status()

        for line in response.iter_lines():
            if not line: continue
            line_str = line.decode('utf-8').strip()
            if not line_str.startswith("data:"): 
                continue

            data_str = line_str[5:].strip()
            if not data_str or data_str == "[DONE]": 
                continue

            try:
                data = json.loads(data_str)
                if data.get("type") == "context":
                    contexts = data.get("data", {}).get("texts", [])

                else:
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            answer += content
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode JSON line: {data_str}")
                continue
        return {"answer": answer, "contexts": contexts}
    except Exception as e:
        logger.error(f"RAG Pipeline Error: {e}")
        return {"answer": "", "contexts": []}


async def run_evaluation_task():
    try:
        EVALUATION_RUNS_TOTAL.labels(status='started').inc()
        logger.info("--- Starting RAG evaluation ---")
        
        documents = load_documents_from_s3()
        if not documents:
            EVALUATION_RUNS_TOTAL.labels(status='completed').inc()
            return

        # very low config to save rpm
        ragas_config = RunConfig(max_workers=1, timeout=240, max_retries=3)
        generator_llm_raw = ChatOpenAI(model=env.GENERATOR_LLM, base_url=env.LLM_GATEWAY_URL, api_key="dummy_key")
        critic_llm_raw = ChatOpenAI(model=env.CRITIC_LLM, base_url=env.LLM_GATEWAY_URL, api_key="dummy_key")

        logger.info("Splitting documents...")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=env.CHUNK_SIZE, chunk_overlap=env.CHUNK_OVERLAP)
        split_documents = text_splitter.split_documents(documents)

        testset_data = generate_synthetic_testset(split_documents, generator_llm_raw, env.EVAL_TESTSET_SIZE)
        if not testset_data:
            logger.error("No test data generated.")
            return

        logger.info("Running RAG pipeline...")
        results = []
        for item in testset_data:
            rag_output = run_rag_pipeline(item["question"])
            if rag_output["answer"]:
                results.append({
                    "question": item["question"],
                    "contexts": rag_output["contexts"],
                    "answer": rag_output["answer"],
                    "ground_truth": item["ground_truth"]
                })
        if not results:
            logger.error("RAG Pipeline returned no answers.")
            return
        
        logger.info("Computing Metrics with Ragas...")
        ragas_critic_llm = LangchainLLMWrapper(critic_llm_raw)

        # Dumb fix 2 - ragas forces n=3 but groq doesn't like it
        _original_generate = ragas_critic_llm.generate   
        async def _safe_generate(prompts, n=1, **kwargs):
            return await _original_generate(prompts, n=1, **kwargs)
        ragas_critic_llm.generate = _safe_generate
        
        embeddings = SafeFastEmbed(model_name=env.EMBEDDING_MODEL)
        ragas_embeddings = LangchainEmbeddingsWrapper(embeddings)

        score = await asyncio.to_thread(
            evaluate,
            dataset=Dataset.from_list(results),
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall, answer_correctness],
            llm=ragas_critic_llm,
            embeddings=ragas_embeddings,
            run_config=ragas_config,
            raise_exceptions=False
        )

        logger.info(f"Results: \n{score}")
        def safe_get_score(result_object, key):
            try:
                if key in result_object:
                    val = result_object[key]
                    if isinstance(val, float) and math.isnan(val):
                        return 0.0
                    return val
                return 0.0
            except Exception:
                return 0.0

        EVAL_FAITHFULNESS.set(safe_get_score(score, 'faithfulness'))
        EVAL_ANSWER_RELEVANCY.set(safe_get_score(score, 'answer_relevancy'))
        EVAL_CONTEXT_PRECISION.set(safe_get_score(score, 'context_precision'))
        EVAL_CONTEXT_RECALL.set(safe_get_score(score, 'context_recall'))
        EVAL_ANSWER_CORRECTNESS.set(safe_get_score(score, 'answer_correctness'))
        EVALUATION_RUNS_TOTAL.labels(status='completed').inc()
        logger.info("--- Finished ---")

    except Exception as e:
        EVALUATION_RUNS_TOTAL.labels(status='failed').inc()
        logger.error(f"--- Failed: {e} ---", exc_info=True)
