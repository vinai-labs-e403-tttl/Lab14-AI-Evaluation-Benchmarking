import asyncio
import time
from typing import List, Dict


class BenchmarkRunner:
    def __init__(self, agent, evaluator, judge):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge

    async def run_single_test(self, test_case: Dict) -> Dict:
        start_time = time.perf_counter()

        # 1. Gọi Agent với expected_retrieval_ids để simulate consistent retrieval
        expected_ids = test_case.get("expected_retrieval_ids", [])
        response = await self.agent.query(test_case["question"], expected_retrieval_ids=expected_ids)
        latency = time.perf_counter() - start_time

        # 2. Chạy Retrieval Evaluation (hit_rate, MRR)
        retrieval_metrics = self.evaluator.evaluate_retrieval(
            expected_ids=expected_ids,
            retrieved_ids=response.get("retrieved_ids", []),
            top_k=5
        )

        # 3. Chạy RAGAS metrics (faithfulness, relevancy)
        ragas_scores = await self.evaluator.score(test_case, response)
        ragas_scores["retrieval"] = retrieval_metrics

        # 4. Chạy Multi-Judge
        judge_result = await self.judge.evaluate_multi_judge(
            test_case["question"],
            response["answer"],
            test_case.get("expected_answer", "")
        )

        # 5. Determine pass/fail status
        final_score = judge_result.get("final_score", 0)
        status = "pass" if final_score >= 3 else "fail"

        return {
            "test_case": test_case.get("id", test_case["question"][:50]),
            "question": test_case["question"],
            "agent_response": response["answer"],
            "retrieved_ids": response.get("retrieved_ids", []),
            "expected_retrieval_ids": expected_ids,
            "latency": round(latency, 4),
            "tokens_used": response.get("metadata", {}).get("tokens_used", 0),
            "estimated_cost": response.get("metadata", {}).get("estimated_cost", 0),
            "ragas": ragas_scores,
            "judge": judge_result,
            "status": status
        }

    async def run_all(self, dataset: List[Dict], batch_size: int = 10) -> List[Dict]:
        """
        Chạy song song bằng asyncio.gather với giới hạn batch_size để không bị Rate Limit.
        """
        results = []
        total = len(dataset)

        for i in range(0, total, batch_size):
            batch = dataset[i:i + batch_size]
            tasks = [self.run_single_test(case) for case in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

        return results

    def summarize_failures(self, results: List[Dict]) -> Dict:
        """Tạo báo cáo về các case thất bại cho Reporter"""
        failures = [r for r in results if r["status"] == "fail"]

        # Cases với retrieval miss
        retrieval_misses = [r for r in results if r["ragas"]["retrieval"]["hit_rate"] == 0]

        # Cases có latency cao nhất
        sorted_by_latency = sorted(results, key=lambda x: x["latency"], reverse=True)
        highest_latency_cases = sorted_by_latency[:5]

        # Cases có điểm judge thấp nhất
        sorted_by_score = sorted(results, key=lambda x: x["judge"]["final_score"])
        lowest_score_cases = sorted_by_score[:5]

        return {
            "total_failures": len(failures),
            "retrieval_misses": len(retrieval_misses),
            "top_fail_cases": failures[:10] if len(failures) > 10 else failures,
            "retrieval_miss_cases": retrieval_misses,
            "highest_latency_cases": highest_latency_cases,
            "lowest_score_cases": lowest_score_cases
        }
