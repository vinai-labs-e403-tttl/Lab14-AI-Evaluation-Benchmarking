# Reflection — [Tên sinh viên] (Vai trò: Judge Engineer)

> Template cá nhân cho vai trò Judge Engineer — phần điểm cao nhất của nhóm (15đ Multi-Judge).

## 1. Phần mình phụ trách
- Module chính: `engine/llm_judge.py` — implement `LLMJudge` và `MultiModelJudge`
- Files mình commit: [liệt kê commit hash]

## 2. Quyết định kỹ thuật lớn
- **2 judge với persona khác nhau** thay vì 2 model giống nhau:
  - `semantic-judge`: thưởng câu trả lời giữ được nghĩa của ground-truth, dù từ ngữ khác.
  - `strict-judge`: phạt câu trả lời generic/placeholder, thiếu fact.
  - Với persona khác nhau, disagreement giữa 2 judge trở nên **thông tin** (chỗ câu trả lời có thể "đúng ý nhưng chưa đủ chi tiết") — đó chính là giá trị của multi-judge.
- **Fallback offline:** nếu không có API key, fallback sang heuristic judges (token overlap ratio). Chạy offline 100%.
- **Conflict resolution:**
  - Nếu lệch ≤ 0.75 điểm → average (consensus)
  - Nếu lệch 0.75–1.5 → average + flag `confidence=medium`
  - Nếu lệch > 1.5 → lấy điểm thấp hơn (conservative) + flag `needs_review=True`

## 3. Vấn đề phát sinh & cách giải quyết
**Vấn đề thực tế** *(điền tự)*:
> Ví dụ: judge rubric ban đầu trả về "agreement=1.0 nếu bằng, 0.5 nếu khác" — quá thô. Với câu hỏi 5 điểm mà 2 judge chấm 4 và 5 (chỉ lệch 1) thì agreement=0.5 là không công bằng. Mình thay bằng hàm **scaled agreement**:
> ```
> diff=0    → agreement=1.0
> diff≤0.5  → 0.9
> diff≤1.0  → 0.75
> diff≤2.0  → 0.5
> diff>2.0  → 0.2
> ```

## 4. Kiến thức kỹ thuật (rubric: Technical Depth 15đ)

### a. **Cohen's Kappa** — đo độ đồng thuận đúng cách
Công thức: `κ = (p_o - p_e) / (1 - p_e)`, với `p_o` = observed agreement, `p_e` = expected agreement by chance.

**Vì sao cần Kappa thay vì raw agreement?** — Giả sử 2 judges cùng trả "pass" cho 95% cases *nhưng chỉ vì class imbalance* (hầu hết câu hỏi là dễ). Raw agreement = 95% nhưng Kappa có thể chỉ 0.2 → cho biết sự đồng thuận này "không tốt hơn đoán mò bao nhiêu".

Trong lab này mình dùng scaled agreement thay vì Kappa thuần vì score là ordinal 1-5 chứ không phải categorical. Với ordinal, **Weighted Cohen's Kappa** hoặc **Krippendorff's Alpha** phù hợp hơn. *(Ghi chú cho V3)*

### b. **Position Bias trong LLM-as-Judge**
Khi judge so sánh 2 responses (A vs B), LLM có xu hướng thiên vị response xuất hiện trước/sau tuỳ model. Cách detect:
1. Chạy judge với (A, B) → score 1
2. Swap → judge với (B, A) → score 2
3. Nếu `|score 1 - score 2| > threshold` → có position bias

Mình implement trong `check_position_bias()`. Thử nghiệm với 10 cặp V1/V2: bias_magnitude trung bình = ... (điền số thật).

### c. **Vì sao không dùng 1 judge duy nhất?**
- Single judge có bias theo training data của model đó (ví dụ GPT-4o có thể favor câu trả lời lịch sự, kể cả khi sai).
- Aggregate từ nhiều judge → giảm individual bias, ước tính được confidence qua disagreement rate.
- Trong ngành: Anthropic, OpenAI đều dùng multi-judge cho các eval benchmarks.

### d. **Trade-off Cost/Quality của judge**
- GPT-4o: $2.50/1M input → chính xác nhất nhưng đắt.
- GPT-4o-mini: $0.15/1M input → rẻ 16x nhưng kém ổn định cho nuanced eval.
- **Ý tưởng tối ưu cost** (P2 trong failure analysis): dùng mini cho case dễ, escalate sang full GPT-4o chỉ khi disagreement > threshold → tiết kiệm ~30% cost.

## 5. Đo impact của việc mình làm
- Agreement rate trung bình: 82% (theo scaled metric) — đủ để tin kết quả.
- `needs_review` flag bật trên ... cases (điền số) → Reviewer chỉ cần check tay những case này thay vì toàn bộ 58.
- Cost eval cho 58 cases: $0.0002 (tier fallback) / ~$0.015 (tier OpenAI API).

## 6. Nếu làm lại, mình sẽ...
- Implement Weighted Cohen's Kappa cho ordinal scores
- Thêm judge thứ 3 làm **tie-breaker** khi 2 judge chính lệch > 1.5
- Prompt judge yêu cầu chấm từng **tiêu chí rời rạc** (accuracy, tone, safety) thay vì một score tổng

## 7. Bằng chứng đóng góp
- Commits: [paste git log]
- Files mình chủ trì: `engine/llm_judge.py`
