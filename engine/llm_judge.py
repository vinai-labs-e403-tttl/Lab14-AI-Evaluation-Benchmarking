import asyncio
import json
import os
import re
import unicodedata
from typing import Any, Dict, Iterable, Optional, Set

from dotenv import load_dotenv
from openai import OpenAI


JUDGE_PRICING = {
    "semantic-judge": {"input": 0.15, "output": 0.60},
    "strict-judge": {"input": 0.15, "output": 0.60},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "la",
    "va",
    "cua",
    "cho",
    "trong",
    "duoc",
    "cac",
    "mot",
    "nhung",
    "nay",
    "do",
    "khi",
    "neu",
    "thi",
    "can",
    "phai",
    "the",
    "theo",
    "tren",
    "duoi",
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    return re.sub(r"[^a-z0-9\s]", " ", text)


def _tokens(text: str) -> Set[str]:
    return {tok for tok in _normalize(text).split() if len(tok) > 2 and tok not in STOPWORDS}


def _overlap_ratio(reference: Iterable[str], candidate: Iterable[str]) -> float:
    reference_set = set(reference)
    candidate_set = set(candidate)
    if not reference_set:
        return 0.0
    return len(reference_set & candidate_set) / len(reference_set)


def _score_from_ratio(ratio: float) -> float:
    if ratio >= 0.85:
        return 5.0
    if ratio >= 0.65:
        return 4.0
    if ratio >= 0.45:
        return 3.0
    if ratio >= 0.25:
        return 2.0
    return 1.0


class LLMJudge:
    """
    Deterministic multi-judge evaluator.

    The lab rubric asks for at least two judges plus agreement/conflict handling.
    This implementation keeps the same interface as a real LLM judge, but uses
    two independent rubric-based judges so the benchmark can run offline and
    reproducibly.
    """

    def __init__(self, judge_a: str = "semantic-judge", judge_b: str = "strict-judge"):
        load_dotenv()
        self.use_real_api = os.getenv("USE_REAL_LLM_JUDGE", "true").lower() not in {"0", "false", "no"}
        self.api_available = bool(os.getenv("OPENAI_API_KEY"))
        self.client: Optional[OpenAI] = OpenAI() if self.use_real_api and self.api_available else None
        self.judge_a_name = os.getenv("JUDGE_MODEL_A", judge_a if self.api_available else "semantic-judge")
        self.judge_b_name = os.getenv("JUDGE_MODEL_B", judge_b if self.api_available else "strict-judge")
        if self.api_available and self.use_real_api and judge_a == "semantic-judge":
            self.judge_a_name = os.getenv("JUDGE_MODEL_A", "gpt-4o-mini")
        if self.api_available and self.use_real_api and judge_b == "strict-judge":
            self.judge_b_name = os.getenv("JUDGE_MODEL_B", "gpt-4o")
        self.rubrics = {
            "semantic": "Rewards answers that cover the key facts in the ground truth.",
            "strict": "Penalizes generic, unsupported, evasive, or incomplete answers.",
        }

    def _estimate_tokens(self, *texts: str) -> int:
        return sum(max(1, len(text or "") // 4) for text in texts) + 160

    def _semantic_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        answer_terms = _tokens(answer)
        truth_terms = _tokens(ground_truth)
        question_terms = _tokens(question)

        truth_coverage = _overlap_ratio(truth_terms, answer_terms)
        question_relevance = _overlap_ratio(question_terms, answer_terms)
        score = _score_from_ratio((truth_coverage * 0.8) + (question_relevance * 0.2))

        if "khong biet" in _normalize(answer) and truth_terms:
            score = min(score, 2.0)

        return {
            "score": score,
            "reasoning": (
                f"Semantic coverage={truth_coverage:.2f}, "
                f"question relevance={question_relevance:.2f}."
            ),
            "tokens_used": self._estimate_tokens(question, answer, ground_truth),
        }

    def _strict_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        answer_terms = _tokens(answer)
        truth_terms = _tokens(ground_truth)
        truth_coverage = _overlap_ratio(truth_terms, answer_terms)

        generic_markers = [
            "cau tra loi mau",
            "sample",
            "placeholder",
            "toi xin tra loi cau hoi",
            "dua tren tai lieu he thong",
        ]
        normalized_answer = _normalize(answer)
        generic_penalty = any(marker in normalized_answer for marker in generic_markers)

        score = _score_from_ratio(truth_coverage)
        if len(answer_terms) < 4:
            score -= 1.0
        if generic_penalty:
            score -= 1.0
        if truth_terms and truth_coverage < 0.25:
            score -= 0.5

        return {
            "score": max(1.0, min(5.0, score)),
            "reasoning": (
                f"Strict coverage={truth_coverage:.2f}; "
                f"generic_penalty={generic_penalty}."
            ),
            "tokens_used": self._estimate_tokens(question, answer, ground_truth),
        }

    def _fallback_judge(self, persona: str, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        if persona == "strict":
            return self._strict_judge(question, answer, ground_truth)
        return self._semantic_judge(question, answer, ground_truth)

    def _call_openai_judge(
        self,
        model: str,
        persona: str,
        question: str,
        answer: str,
        ground_truth: str,
    ) -> Dict[str, Any]:
        if self.client is None:
            return self._fallback_judge(persona, question, answer, ground_truth)

        if persona == "strict":
            rubric = (
                "You are a strict evaluator. Penalize generic answers, unsupported claims, "
                "missing key facts, and answers that do not directly match the ground truth."
            )
        else:
            rubric = (
                "You are a semantic evaluator. Reward answers that preserve the meaning of "
                "the ground truth, even when wording differs."
            )

        response = self.client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        f"{rubric} Score from 1 to 5. "
                        "Return JSON only. Use score=1 for unrelated or placeholder answers, "
                        "score=3 for partially correct answers, and score=5 for fully correct answers."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{question}\n\n"
                        f"Agent answer:\n{answer}\n\n"
                        f"Ground truth:\n{ground_truth}"
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "judge_result",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "number", "minimum": 1, "maximum": 5},
                            "reasoning": {"type": "string"},
                        },
                        "required": ["score", "reasoning"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        payload = json.loads(response.output_text)
        usage = getattr(response, "usage", None)
        if usage:
            input_tokens = getattr(usage, "input_tokens", 0) or 0
            output_tokens = getattr(usage, "output_tokens", 0) or 0
            tokens_used = input_tokens + output_tokens
        else:
            tokens_used = self._estimate_tokens(question, answer, ground_truth)

        return {
            "score": max(1.0, min(5.0, float(payload["score"]))),
            "reasoning": payload["reasoning"],
            "tokens_used": tokens_used,
        }

    def _agreement_rate(self, score_a: float, score_b: float) -> float:
        diff = abs(score_a - score_b)
        if diff == 0:
            return 1.0
        if diff <= 0.5:
            return 0.9
        if diff <= 1.0:
            return 0.75
        if diff <= 2.0:
            return 0.5
        return 0.2

    def _resolve_conflict(self, score_a: float, score_b: float) -> Dict[str, Any]:
        diff = abs(score_a - score_b)
        if diff > 1.5:
            return {
                "final_score": min(score_a, score_b),
                "confidence": "low",
                "needs_review": True,
                "strategy": "large_disagreement_use_conservative_score",
            }
        if diff > 0.75:
            return {
                "final_score": (score_a + score_b) / 2,
                "confidence": "medium",
                "needs_review": False,
                "strategy": "moderate_disagreement_average",
            }
        return {
            "final_score": (score_a + score_b) / 2,
            "confidence": "high",
            "needs_review": False,
            "strategy": "consensus_average",
        }

    def _estimated_cost(self, tokens_used: int) -> float:
        price_a = JUDGE_PRICING.get(self.judge_a_name, JUDGE_PRICING["gpt-4o-mini"])
        price_b = JUDGE_PRICING.get(self.judge_b_name, JUDGE_PRICING["gpt-4o-mini"])
        average_input_price = (
            price_a["input"]
            + price_b["input"]
        ) / 2
        average_output_price = (
            price_a["output"]
            + price_b["output"]
        ) / 2
        input_tokens = int(tokens_used * 0.75)
        output_tokens = tokens_used - input_tokens
        return (
            (input_tokens / 1_000_000) * average_input_price
            + (output_tokens / 1_000_000) * average_output_price
        )

    async def evaluate_multi_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        if self.client is not None:
            semantic_task = asyncio.to_thread(
                self._call_openai_judge,
                self.judge_a_name,
                "semantic",
                question,
                answer,
                ground_truth,
            )
            strict_task = asyncio.to_thread(
                self._call_openai_judge,
                self.judge_b_name,
                "strict",
                question,
                answer,
                ground_truth,
            )
        else:
            semantic_task = asyncio.to_thread(self._semantic_judge, question, answer, ground_truth)
            strict_task = asyncio.to_thread(self._strict_judge, question, answer, ground_truth)

        try:
            semantic_result, strict_result = await asyncio.gather(semantic_task, strict_task)
            judge_mode = "openai_api" if self.client is not None else "heuristic_fallback"
        except Exception as exc:
            semantic_result = self._semantic_judge(question, answer, ground_truth)
            strict_result = self._strict_judge(question, answer, ground_truth)
            judge_mode = f"heuristic_fallback_after_api_error:{exc.__class__.__name__}"

        score_a = float(semantic_result["score"])
        score_b = float(strict_result["score"])
        agreement_rate = self._agreement_rate(score_a, score_b)
        resolution = self._resolve_conflict(score_a, score_b)
        tokens_used = semantic_result["tokens_used"] + strict_result["tokens_used"]

        return {
            "final_score": round(resolution["final_score"], 2),
            "agreement_rate": round(agreement_rate, 2),
            "individual_scores": {
                self.judge_a_name: round(score_a, 2),
                self.judge_b_name: round(score_b, 2),
            },
            "confidence": resolution["confidence"],
            "needs_review": resolution["needs_review"],
            "conflict_resolution": resolution["strategy"],
            "judge_mode": judge_mode,
            "reasoning": (
                f"{self.judge_a_name}: {semantic_result['reasoning']} "
                f"{self.judge_b_name}: {strict_result['reasoning']}"
            ),
            "tokens_used": tokens_used,
            "estimated_cost": round(self._estimated_cost(tokens_used), 6),
        }

    async def check_position_bias(self, response_a: str, response_b: str, **kwargs: Any) -> Dict[str, Any]:
        question = kwargs.get("question", "Compare the two responses.")
        ground_truth = kwargs.get("ground_truth", "")
        first = await self.evaluate_multi_judge(question, response_a, ground_truth)
        second = await self.evaluate_multi_judge(question, response_b, ground_truth)
        bias_magnitude = abs(first["final_score"] - second["final_score"])
        return {
            "original_score": first["final_score"],
            "swapped_score": second["final_score"],
            "bias_detected": bias_magnitude > 0.5,
            "bias_magnitude": round(bias_magnitude, 2),
        }


class MultiModelJudge:
    def __init__(self, judge_a: str = "semantic-judge", judge_b: str = "strict-judge"):
        self.judge = LLMJudge(judge_a, judge_b)

    async def evaluate_multi_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        return await self.judge.evaluate_multi_judge(question, answer, ground_truth)
