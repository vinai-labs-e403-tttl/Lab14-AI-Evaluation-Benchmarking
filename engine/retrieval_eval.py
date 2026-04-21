from typing import List, Dict


class RetrievalEvaluator:
    def __init__(self):
        pass

    def calculate_hit_rate(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        """
        Tính toán xem ít nhất 1 trong expected_ids có nằm trong top_k của retrieved_ids không.
        Hit = 1.0 nếu có ít nhất 1 expected_id trong top_k, ngược lại = 0.0
        """
        top_retrieved = retrieved_ids[:top_k]
        hit = any(doc_id in top_retrieved for doc_id in expected_ids)
        return 1.0 if hit else 0.0

    def calculate_mrr(self, expected_ids: List[str], retrieved_ids: List[str]) -> float:
        """
        Tính Mean Reciprocal Rank.
        Tìm vị trí đầu tiên của một expected_id trong retrieved_ids (1-indexed).
        MRR = 1 / position. Nếu không thấy thì = 0.
        """
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in expected_ids:
                return 1.0 / (i + 1)
        return 0.0

    def evaluate_retrieval(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 5) -> Dict:
        """
        Tính toán các retrieval metrics cho một test case.
        """
        hit_rate = self.calculate_hit_rate(expected_ids, retrieved_ids, top_k)
        mrr = self.calculate_mrr(expected_ids, retrieved_ids)

        return {
            "hit_rate": hit_rate,
            "mrr": mrr,
            "top_k": top_k,
            "expected_ids": expected_ids,
            "retrieved_ids": retrieved_ids[:top_k]
        }

    async def score(self, test_case: Dict, agent_response: Dict) -> Dict:
        """
        Tính faithfulness và relevancy scores cho RAGAS metrics.
        Đây là simulation - trong thực tế sẽ gọi LLM để đánh giá.
        """
        import random
        # Simulation của RAGAS scores
        faithfulness = random.uniform(0.75, 0.95)
        relevancy = random.uniform(0.70, 0.90)

        return {
            "faithfulness": round(faithfulness, 3),
            "relevancy": round(relevancy, 3)
        }

    async def evaluate_batch(self, dataset: List[Dict], results: List[Dict]) -> Dict:
        """
        Tính toán metrics trung bình từ benchmark results.
        """
        if not results:
            return {"avg_hit_rate": 0.0, "avg_mrr": 0.0}

        total_hit_rate = sum(r["ragas"]["retrieval"]["hit_rate"] for r in results)
        total_mrr = sum(r["ragas"]["retrieval"]["mrr"] for r in results)

        return {
            "avg_hit_rate": round(total_hit_rate / len(results), 4),
            "avg_mrr": round(total_mrr / len(results), 4),
            "total_cases": len(results)
        }
