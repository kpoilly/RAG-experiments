import os
import logging
import requests
import json
import tempfile
from typing import List, Dict, Any

import boto3

from datasets import Dataset
from ragas import evaluate
from ragas.testset import TestsetGenerator
from ragas.metrics import (faithfulness, answer_relevancy, context_precision, 
                           context_recall, answer_correctness,)

from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader, UnstructuredMarkdownLoader
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_openai import ChatOpenAI

from metrics import (
    EVAL_FAITHFULNESS,
    EVAL_ANSWER_RELEVANCY,
    EVAL_CONTEXT_PRECISION,
    EVAL_CONTEXT_RECALL,
    EVAL_ANSWER_CORRECTNESS,
    EVALUATION_RUNS_TOTAL,
)
from config import settings as env


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


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

  
def run_rag_pipeline(question: str) -> Dict[str, Any]:
    """
    Calls rag-core's API to get final answer and context documents for evaluation.
    """
    answer = ""
    contexts = []
    try:
        response = requests.post(
            f"{env.RAG_CORE_URL}/chat",
            json={"query": question, "history": []},
            stream=True,
            timeout=120
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if not line.startswith(b'data:'):
                continue
            
            data_str = line.decode('utf-8')[6:].strip()
            if not data_str or data_str == "[DONE]":
                continue

            data = json.loads(data_str)
            if data.get("type") == "context":
                contexts = data.get("data", {}).get("texts", [])
            else:
                delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                answer += delta
        
        logger.info(f"RAG pipeline answered for question: '{question[:30]}...'")
        return {"answer": answer, "contexts": contexts}

    except requests.RequestException as e:
        logger.error(f"Failed to call RAG Core API: {e}")
        return {"answer": "", "contexts": []}


def run_evaluation_task():
    """
    Loads sample docs, generate an evaluation dataset and execute RAG to evaluate it.
    """
    try:
        EVALUATION_RUNS_TOTAL.labels(status='started').inc()
        logger.info("--- Starting background RAG evaluation task ---")
        
        documents = load_documents_from_s3()
        if not documents:
            logger.warning("No documents found to evaluate. Skipping run.")
            EVALUATION_RUNS_TOTAL.labels(status='completed').inc()
            return

        generator_llm = ChatOpenAI(model=env.GENERATOR_LLM, base_url=f"{env.LLM_GATEWAY_URL}/chat/completions", api_key="dummy_key")
        critic_llm = ChatOpenAI(model=env.CRITIC_LLM, base_url=f"{env.LLM_GATEWAY_URL}/chat/completions", api_key="dummy_key")
        embeddings = FastEmbedEmbeddings(model_name=env.EMBEDDING_MODEL)

        logger.info("Generating synthetic evaluation set from documents...")
        generator = TestsetGenerator.from_langchain(generator_llm, critic_llm, embeddings)
        testset = generator.generate_with_langchain_docs(documents, testset_size=10)
        
        logger.info("Running RAG pipeline for each generated question...")
        results = []
        for test_case in testset.to_list():
            rag_output = run_rag_pipeline(test_case["question"])
            results.append({
                "question": test_case["question"],
                "ground_truth": test_case["ground_truth"],
                "answer": rag_output["answer"],
                "contexts": rag_output["contexts"],
            })
        
        logger.info("Evaluating the results with RAGAS...")
        result_dataset = Dataset.from_list(results)
        score = evaluate(
            result_dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall, answer_correctness],
            llm=critic_llm,
        )
        logger.info(f"Evaluation results: \n{score}")

        EVAL_FAITHFULNESS.set(score.get('faithfulness', 0))
        EVAL_ANSWER_RELEVANCY.set(score.get('answer_relevancy', 0))
        EVAL_CONTEXT_PRECISION.set(score.get('context_precision', 0))
        EVAL_CONTEXT_RECALL.set(score.get('context_recall', 0))
        EVAL_ANSWER_CORRECTNESS.set(score.get('answer_correctness', 0))
        EVALUATION_RUNS_TOTAL.labels(status='completed').inc()
        logger.info("--- RAG evaluation task finished successfully ---")

    except Exception as e:
        EVALUATION_RUNS_TOTAL.labels(status='failed').inc()
        logger.error(f"--- RAG evaluation task failed: {e} ---", exc_info=True)
