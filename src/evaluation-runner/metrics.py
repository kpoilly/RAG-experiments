from prometheus_client import Counter, Gauge

# Generation quality
EVAL_FAITHFULNESS = Gauge("rag_eval_faithfulness_score", "Faithfulness score from the latest RAGAS evaluation.")
EVAL_ANSWER_RELEVANCY = Gauge("rag_eval_answer_relevancy_score", "Answer relevancy score from the latest RAGAS evaluation.")
EVAL_ANSWER_CORRECTNESS = Gauge("rag_eval_answer_correctness_score", "Answer Correctness: How accurate is the answer compared to the ground truth. (1.0 = Perfect)")

# Retrieval quality
EVAL_CONTEXT_PRECISION = Gauge("rag_eval_context_precision_score", "Context Precision: Signal-to-noise ratio of the retrieved context. (1.0 = Perfect)")
EVAL_CONTEXT_RECALL = Gauge("rag_eval_context_recall_score", "Context Recall: How well the retriever fetched all necessary information. (1.0 = Perfect)")

EVALUATION_RUNS_TOTAL = Counter("rag_evaluation_runs_total", "Total number of evaluation runs initiated.", ["status"])
