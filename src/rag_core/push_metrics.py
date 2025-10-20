import os
import logging
import asyncio

from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

from evaluate import run_evaluation

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROMETHEUS_GATEWAY_URL = os.getenv("PROMETHEUS_GATEWAY_URL", "prometheus-pushgateway:9091")


async def main():
	try:
		logger.info("Starting scheduled RAG evaluation...")
		results = await run_evaluation()
		logger.info(f"Evaluation results: {results}")

		registry = CollectorRegistry()

		rag_faithfulness = Gauge('rag_eval_faithfulness', "Faithfulness score from RAGAs", registry=registry)
		rag_answer_relevancy = Gauge('rag_evel_answer_relevancy', "Answer relevancy score from RAGAs", registry=registry)
		rag_context_precision = Gauge('rag_eval_context_precision', "Context precision score from RAGAs", registry=registry)
		rag_context_recall = Gauge('rag_eval_context_recall', "Context recall score from RAGAs", registry=registry)
		rag_answer_correctness = Gauge('rag_eval_answer_correctness', "Answer correctness score from RAGAs", registry=registry)
		rag_answer_similarity = Gauge('rag_eval_answer_similarity', "Answer similarity score from RAGAs", registry=registry)

		scores = results.mean().to_dict()
		rag_faithfulness.set(scores.get('faithfulness', 0))
		rag_answer_relevancy.set(scores.get('answer_relevancy', 0))
		rag_context_precision.set(scores.get('context_precision', 0))
		rag_context_recall.set(scores.get('context_recall', 0))
		rag_answer_correctness.set(scores.get('answer_correctness', 0))
		rag_answer_similarity.set(scores.get('answer_similarity', 0))

		logger.info("Pushing metrics to Prometheus...")
		await push_to_gateway(PROMETHEUS_GATEWAY_URL, job="rag_evaluation", registry=registry)
		logger.info("Metrics pushed successfully.")
	
	except Exception as e:
		logger.error(f"Error during RAG evaluation: {e}")
		registry = CollectorRegistry()
		rag_error = Gauge('rag_eval_error', "Error during RAG evaluation", registry=registry)
		rag_error.set(1)
		try:
			await push_to_gateway(PROMETHEUS_GATEWAY_URL, job="rag_evaluation", registry=registry)
		except Exception as e:
			logger.error(f"Error pushing metrics to Prometheus: {e}")


if __name__ == "__main__":
	asyncio.run(main())
