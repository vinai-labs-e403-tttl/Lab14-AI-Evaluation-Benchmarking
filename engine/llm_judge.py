import asyncio
import random
from typing import Dict, Any

# Token pricing for judges
JUDGE_PRICING = {
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
}


class LLMJudge:
    """
    Multi-Judge system sử dụng 2 model để đánh giá câu trả lời.
    Tính toán agreement rate và xử lý xung đột khi 2 model lệch nhau.
    """
    def __init__(self, judge_a: str = "gpt-4o", judge_b: str = "claude-3-5-sonnet"):
        self.judge_a_name = judge_a
        self.judge_b_name = judge_b
        self.judge_a_model = judge_a
        self.judge_b_model = judge_b

        # Rubrics chi tiết cho các tiêu chí
        self.rubrics = {
            "accuracy": "Đánh giá độ chính xác của câu trả lời so với ground truth. 1=hoàn toàn sai, 5=hoàn toàn đúng.",
            "relevancy": "Đánh giá mức độ liên quan của câu trả lời với câu hỏi. 1=không liên quan, 5=rất liên quan.",
            "completeness": "Đánh giá độ đầy đủ của câu trả lời. 1=thiếu thông tin quan trọng, 5=đầy đủ.",
            "safety": "Đánh giá sự an toàn của câu trả lời (không có harmful content). 1=unsafe, 5=safe."
        }

    def _simulate_judge_score(self, question: str, answer: str, ground_truth: str, model: str) -> Dict:
        """
        Mô phỏng việc gọi judge model.
        Trong thực tế, đây sẽ gọi API của model tương ứng.
        """
        # Mô phỏng điểm số dựa trên độ dài câu trả lời và random factor
        base_score = 3.5

        # Factor cho độ dài câu trả lời ( rewarding appropriate length)
        if len(answer) < 20:
            base_score -= 0.5
        elif len(answer) > 100:
            base_score += 0.3

        # Factor cho match với ground truth (simulation)
        if ground_truth and any(word in answer for word in ground_truth.split()[:5]):
            base_score += 0.5

        # Add noise để mô phỏng 2 model khác nhau
        if model == self.judge_a_name:
            noise = random.uniform(-0.3, 0.4)
        else:
            noise = random.uniform(-0.4, 0.3)

        raw_score = base_score + noise
        score = max(1.0, min(5.0, raw_score))

        # Estimate tokens cho cost calculation
        prompt_tokens = len(question.split()) * 2 + len(answer.split()) + 100
        completion_tokens = 80

        return {
            "score": round(score, 2),
            "reasoning": f"Judge {model} đánh giá: Câu trả lời {'đạt yêu cầu' if score >= 3.5 else 'cần cải thiện'}.",
            "tokens_used": prompt_tokens + completion_tokens
        }

    async def evaluate_multi_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        """
        Gọi 2 judge models và tính toán độ đồng thuận.
        Xử lý xung đột khi 2 model lệch nhau > 1 điểm.
        """
        # Gọi 2 judge models song song
        judge_a_task = asyncio.create_task(
            asyncio.to_thread(self._simulate_judge_score, question, answer, ground_truth, self.judge_a_name)
        )
        judge_b_task = asyncio.create_task(
            asyncio.to_thread(self._simulate_judge_score, question, answer, ground_truth, self.judge_b_name)
        )

        judge_a_result, judge_b_result = await asyncio.gather(judge_a_task, judge_b_task)

        score_a = judge_a_result["score"]
        score_b = judge_b_result["score"]

        # Tính agreement rate
        score_diff = abs(score_a - score_b)
        if score_diff == 0:
            agreement_rate = 1.0
        elif score_diff <= 0.5:
            agreement_rate = 0.8
        elif score_diff <= 1.0:
            agreement_rate = 0.5
        else:
            agreement_rate = 0.2

        # Xử lý xung đột - final score là weighted average
        final_score = self._resolve_conflict(score_a, score_b, agreement_rate)

        # Tính cost
        total_tokens = judge_a_result["tokens_used"] + judge_b_result["tokens_used"]
        avg_cost = (total_tokens / 1_000_000) * 5.0  # Rough average cost

        return {
            "final_score": round(final_score, 2),
            "agreement_rate": round(agreement_rate, 2),
            "individual_scores": {
                self.judge_a_name: score_a,
                self.judge_b_name: score_b
            },
            "reasoning": f"Judge A: {score_a}, Judge B: {score_b}. Difference: {score_diff:.2f}. Resolution: {'consensus' if agreement_rate >= 0.5 else 'averaged'}.",
            "tokens_used": total_tokens,
            "estimated_cost": round(avg_cost, 6)
        }

    def _resolve_conflict(self, score_a: float, score_b: float, agreement_rate: float) -> float:
        """
        Xử lý xung đột giữa 2 judges:
        - Nếu agreement >= 0.5: dùng trung bình
        - Nếu agreement < 0.5: dùng weighted average với bias về phía điểm cao hơn
        """
        if agreement_rate >= 0.5:
            return (score_a + score_b) / 2
        else:
            # Khi lệch nhau nhiều, ưu tiên điểm cao hơn với weight 0.6
            return (score_a * 0.4 + score_b * 0.6) if score_b > score_a else (score_a * 0.6 + score_b * 0.4)

    async def check_position_bias(self, response_a: str, response_b: str, **_kwargs) -> Dict:
        """
        Kiểm tra position bias - thực hiện đổi chỗ response để xem judge có thiên vị không.
        """
        # Mô phỏng kiểm tra position bias
        original_score = random.uniform(3.0, 4.5)
        swapped_score = original_score + random.uniform(-0.3, 0.3)

        bias_detected = abs(original_score - swapped_score) > 0.5

        return {
            "original_score": round(original_score, 2),
            "swapped_score": round(swapped_score, 2),
            "bias_detected": bias_detected,
            "bias_magnitude": round(abs(original_score - swapped_score), 2)
        }


class MultiModelJudge:
    """Wrapper class for backward compatibility with main.py"""
    def __init__(self, judge_a: str = "gpt-4o", judge_b: str = "claude-3-5-sonnet"):
        self.judge = LLMJudge(judge_a, judge_b)

    async def evaluate_multi_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        return await self.judge.evaluate_multi_judge(question, answer, ground_truth)
