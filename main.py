import asyncio
import json
import os
import time
from typing import Any, Dict, List, Tuple

from agent.main_agent import MainAgent, MainAgentV2
from engine.llm_judge import MultiModelJudge
from engine.retrieval_eval import RetrievalEvaluator
from engine.runner import BenchmarkRunner


class ExpertEvaluator:
    """Adapter that exposes retrieval and RAGAS-style metrics to BenchmarkRunner."""

    def __init__(self) -> None:
        self.retrieval_eval = RetrievalEvaluator()

    async def score(self, test_case: Dict[str, Any], agent_response: Dict[str, Any], **_kwargs: Any) -> Dict[str, Any]:
        return await self.retrieval_eval.score(test_case, agent_response)

    def evaluate_retrieval(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 5) -> Dict[str, Any]:
        return self.retrieval_eval.evaluate_retrieval(expected_ids, retrieved_ids, top_k)


def normalize_dataset(dataset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure cases have stable ids and retrieval ground-truth ids."""
    normalized = []
    for index, case in enumerate(dataset, start=1):
        item = dict(case)
        item.setdefault("id", f"case_{index:03d}")

        metadata = item.get("metadata") or {}
        if not item.get("expected_retrieval_ids"):
            doc_id = metadata.get("doc_id") or metadata.get("source")
            item["expected_retrieval_ids"] = [doc_id] if doc_id else []

        normalized.append(item)
    return normalized


def calculate_summary(results: List[Dict[str, Any]], version: str) -> Dict[str, Any]:
    total = len(results)
    if total == 0:
        raise ValueError("Cannot summarize an empty benchmark result set.")

    pass_count = sum(1 for result in results if result["status"] == "pass")
    fail_count = total - pass_count
    total_agent_tokens = sum(result.get("tokens_used", 0) for result in results)
    total_judge_tokens = sum(result.get("judge", {}).get("tokens_used", 0) for result in results)
    total_agent_cost = sum(result.get("estimated_cost", 0.0) for result in results)
    total_judge_cost = sum(result.get("judge", {}).get("estimated_cost", 0.0) for result in results)

    avg_score = sum(result["judge"]["final_score"] for result in results) / total
    avg_hit_rate = sum(result["ragas"]["retrieval"]["hit_rate"] for result in results) / total
    avg_mrr = sum(result["ragas"]["retrieval"]["mrr"] for result in results) / total
    avg_agreement = sum(result["judge"]["agreement_rate"] for result in results) / total
    avg_latency = sum(result["latency"] for result in results) / total
    needs_review_count = sum(1 for result in results if result["judge"].get("needs_review"))

    return {
        "metadata": {
            "version": version,
            "total": total,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "metrics": {
            "avg_score": round(avg_score, 4),
            "hit_rate": round(avg_hit_rate, 4),
            "mrr": round(avg_mrr, 4),
            "agreement_rate": round(avg_agreement, 4),
            "avg_latency": round(avg_latency, 4),
            "total_tokens": total_agent_tokens + total_judge_tokens,
            "agent_tokens": total_agent_tokens,
            "judge_tokens": total_judge_tokens,
            "total_cost": round(total_agent_cost + total_judge_cost, 6),
            "agent_cost": round(total_agent_cost, 6),
            "judge_cost": round(total_judge_cost, 6),
            "needs_review_count": needs_review_count,
        },
        "performance": {
            "avg_latency_seconds": round(avg_latency, 4),
            "tokens_per_case": round((total_agent_tokens + total_judge_tokens) / total, 2),
            "cost_per_case": round((total_agent_cost + total_judge_cost) / total, 6),
        },
    }


def run_regression_gate(v1_summary: Dict[str, Any], v2_summary: Dict[str, Any]) -> Dict[str, Any]:
    v1_metrics = v1_summary["metrics"]
    v2_metrics = v2_summary["metrics"]

    delta = {
        "avg_score": round(v2_metrics["avg_score"] - v1_metrics["avg_score"], 4),
        "hit_rate": round(v2_metrics["hit_rate"] - v1_metrics["hit_rate"], 4),
        "mrr": round(v2_metrics["mrr"] - v1_metrics["mrr"], 4),
        "agreement_rate": round(v2_metrics["agreement_rate"] - v1_metrics["agreement_rate"], 4),
        "avg_latency": round(v2_metrics["avg_latency"] - v1_metrics["avg_latency"], 4),
        "total_cost": round(v2_metrics["total_cost"] - v1_metrics["total_cost"], 6),
    }

    checks = {
        "quality_not_regressed": delta["avg_score"] >= -0.1,
        "retrieval_acceptable": v2_metrics["hit_rate"] >= 0.75 and v2_metrics["mrr"] >= 0.5,
        "judge_reliable": v2_metrics["agreement_rate"] >= 0.7,
        "latency_acceptable": v2_metrics["avg_latency"] <= max(v1_metrics["avg_latency"] * 1.3, v1_metrics["avg_latency"] + 0.2),
        "cost_acceptable": v2_metrics["total_cost"] <= max(v1_metrics["total_cost"] * 1.3, v1_metrics["total_cost"] + 0.01),
    }
    decision = "APPROVE" if all(checks.values()) else "BLOCK_RELEASE"
    failed = [name for name, passed in checks.items() if not passed]

    return {
        "decision": decision,
        "delta": delta,
        "checks": checks,
        "reason": "All release checks passed." if not failed else f"Failed checks: {', '.join(failed)}.",
    }


async def run_benchmark(agent: Any, version: str, dataset: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    evaluator = ExpertEvaluator()
    judge = MultiModelJudge()
    runner = BenchmarkRunner(agent, evaluator, judge)
    results = await runner.run_all(dataset, batch_size=10)
    return results, calculate_summary(results, version)


def load_dataset(path: str = "data/golden_set.jsonl") -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path}. Run python data/synthetic_gen.py first.")

    with open(path, "r", encoding="utf-8") as file:
        dataset = [json.loads(line) for line in file if line.strip()]

    if not dataset:
        raise ValueError(f"{path} is empty.")
    return normalize_dataset(dataset)


async def main() -> None:
    print("Starting Lab14 benchmark...")
    dataset = load_dataset()
    print(f"Loaded {len(dataset)} test cases.")

    print("Running V1 benchmark...")
    _v1_results, v1_summary = await run_benchmark(MainAgent(), "Agent_V1_Base", dataset)
    print(
        "V1: "
        f"score={v1_summary['metrics']['avg_score']:.4f}, "
        f"hit_rate={v1_summary['metrics']['hit_rate']:.4f}, "
        f"mrr={v1_summary['metrics']['mrr']:.4f}, "
        f"latency={v1_summary['metrics']['avg_latency']:.4f}s"
    )

    print("Running V2 benchmark...")
    v2_results, v2_summary = await run_benchmark(MainAgentV2(), "Agent_V2_Optimized", dataset)
    print(
        "V2: "
        f"score={v2_summary['metrics']['avg_score']:.4f}, "
        f"hit_rate={v2_summary['metrics']['hit_rate']:.4f}, "
        f"mrr={v2_summary['metrics']['mrr']:.4f}, "
        f"latency={v2_summary['metrics']['avg_latency']:.4f}s"
    )

    release_gate = run_regression_gate(v1_summary, v2_summary)
    print(f"Release decision: {release_gate['decision']}")
    print(f"Reason: {release_gate['reason']}")

    final_summary = {
        **v2_summary,
        "release_gate": release_gate,
        "regression": release_gate,
        "v1_metrics": v1_summary["metrics"],
    }

    os.makedirs("reports", exist_ok=True)
    with open("reports/summary.json", "w", encoding="utf-8") as file:
        json.dump(final_summary, file, ensure_ascii=False, indent=2)
    with open("reports/benchmark_results.json", "w", encoding="utf-8") as file:
        json.dump(v2_results, file, ensure_ascii=False, indent=2)

    print("Reports saved to reports/summary.json and reports/benchmark_results.json.")


if __name__ == "__main__":
    asyncio.run(main())
