# Reflection — [Tên sinh viên] (Vai trò: Release Gate / Analyst)

> Template cá nhân cho vai trò Release Gate + Failure Analyst.
> Rubric trọng tâm: Regression Testing (10đ) + Failure Analysis (5đ).

## 1. Phần mình phụ trách
- Logic V1 vs V2 regression trong `main.py` (`run_regression_gate`)
- `analysis/failure_analysis.md` — phân tích 5 Whys, failure clustering
- Thiết kế ngưỡng Release Gate
- Files mình commit: [liệt kê commit hash]

## 2. Quyết định kỹ thuật lớn: Release Gate đa trục

Gate check không chỉ nhìn vào 1 metric. Mình thiết kế 5 điều kiện **AND** (tất cả phải pass):

```python
checks = {
    "quality_not_regressed": delta["avg_score"] >= -0.1,
    "retrieval_acceptable": v2.hit_rate >= 0.75 and v2.mrr >= 0.5,
    "judge_reliable":       v2.agreement_rate >= 0.7,
    "latency_acceptable":   v2.avg_latency <= max(v1.avg_latency * 1.3, v1.avg_latency + 0.2),
    "cost_acceptable":      v2.total_cost   <= max(v1.total_cost * 1.3, v1.total_cost + 0.01),
}
decision = "APPROVE" if all(checks.values()) else "BLOCK_RELEASE"
```

**Lí do mỗi check:**
- `quality_not_regressed` (Δ≥ -0.1): cho phép V2 hơi kém V1 trong khoảng noise, nhưng không chấp nhận tụt rõ rệt.
- `retrieval_acceptable`: Hit Rate phải ≥ 75% — dưới mức này agent không dùng được trong production.
- `judge_reliable` ≥ 70%: nếu 2 judges lệch nhau quá → chính kết quả benchmark không đáng tin.
- `latency_acceptable`: V2 không được chậm quá +30% hoặc +0.2s so với V1 (whichever larger — tránh vấn đề chia cho số nhỏ khi V1 nhanh).
- `cost_acceptable`: tương tự latency, với floor +$0.01.

**Quan trọng:** Dùng `max(ratio, absolute_delta)` thay vì chỉ `ratio` để tránh edge case khi V1 rất nhanh/rẻ → ratio phóng đại.

## 3. Vấn đề phát sinh & cách giải quyết
**Vấn đề thực tế** *(điền tự)*:
> Ví dụ: V2 ban đầu chỉ khác V1 ở mỗi format câu trả lời ("V2: ..."). Delta cho mọi metric gần = 0 → gate luôn APPROVE nhưng không có ý nghĩa gì. Mình làm việc với Retrieval Engineer để V2 thực sự khác về **chiến lược retrieval** (top_k=5 + MMR rerank). Sau fix, Hit Rate delta = +3.5% — gate mới có data để quyết định thật.
>
> Vấn đề thứ 2: ngưỡng +30% latency ban đầu là dạng nhân thuần `v1*1.3`. Khi V1 chạy = 0.05s (rất nhanh), +30% = 0.065s (chỉ hơn 15ms) → V2 vượt quá dễ dàng. Fix bằng `max(v1*1.3, v1+0.2)` để có absolute floor.

## 4. Kiến thức kỹ thuật (rubric: Technical Depth 15đ)

### a. **Regression testing trong ML khác Unit test như thế nào?**
- Unit test: deterministic, 0 hoặc 1, binary.
- ML regression test: **statistical** — metric là distribution trên dataset, so sánh bằng delta.
- Không có câu trả lời "đúng tuyệt đối" → phải chọn ngưỡng hợp lý, làm sense check thủ công.
- Tương đương với **A/B testing** trong production: V1 = control, V2 = treatment.

### b. **5 Whys Framework — vì sao dừng ở 5?**
5 Whys là guidance, không phải quy tắc cứng. Ý tưởng: mỗi "why" bóc 1 lớp trách nhiệm.
- Why 1–2: thường ở surface (symptom).
- Why 3–4: ở hệ thống (component design).
- Why 5+: ở process/architecture.
Nếu chỉ dừng ở Why 2, hành động fix sẽ band-aid. Nếu đi sâu Why 5, mới thấy root cause (ví dụ "chunking strategy sai", "vocabulary gap", "thiếu query decomposition").

Áp dụng cho Case #1 trong lab: câu hỏi "Hệ thống IAM?" miss retrieval.
- Why 1 (symptom): answer sai
- Why 2 (generation): LLM không có info trong context
- Why 3 (retrieval): chunk đúng không ở top-5
- Why 4 (matching): BM25 không hiểu IAM ⊃ {Okta, Azure AD}
- **Why 5 (root): vocabulary gap — cần dense retrieval**

### c. **Failure Clustering — Cách nhóm lỗi có ý nghĩa**
Có 3 cách nhóm:
1. Theo **loại câu hỏi** (factoid/procedural/adversarial) — trace lại Data Lead.
2. Theo **độ khó** (easy/medium/hard) — để biết agent đuối ở đâu.
3. Theo **root cause** (retrieval miss / answer generic / judge-too-strict) — để biết nên fix module nào.

Trong failure_analysis.md mình cluster bằng cả 3 cách, mỗi cách chỉ ra một hướng khác nhau:
- Theo type: `detail` và `factoid` là 2 cluster lớn nhất.
- Theo difficulty: `medium` fail nhiều nhất (12 cases) — không phải `hard` vì dataset không có `hard`.
- Theo root cause: 47.6% là "retrieval đúng nhưng answer extract sai câu" → cho biết cần upgrade generation, không phải retrieval.

### d. **Vì sao V2 APPROVE dù Judge Score = V1?**
Rubric: Release Gate không đơn thuần là "score cao hơn". V2 có:
- Hit Rate tốt hơn → chunk đúng đến prompt nhiều hơn
- Same cost range + same latency range
- Không regression

Nghĩa là foundation tốt hơn → khi có V3 upgrade generation, V3 sẽ thừa hưởng lợi ích retrieval. APPROVE V2 là đầu tư cho tương lai, không chỉ performance trước mắt.

## 5. Đo impact của việc mình làm
- Release Gate đã chạy thành công 1 lần (V1 vs V2) với decision APPROVE có căn cứ.
- Failure Analysis identify được **3 root causes distinct**:
  1. Vocabulary gap (BM25 limitation)
  2. Length bias trong chunking
  3. Thiếu query decomposition cho compound questions
- Action Plan có 7 đề xuất cụ thể theo priority P0–P3, mỗi cái có effort estimate.

## 6. Nếu làm lại, mình sẽ...
- Thêm **statistical significance test** (paired t-test trên score của từng case V1 vs V2) thay vì chỉ nhìn delta trung bình
- Lưu trace "who fixed what" — link từng fail case về PR/commit đã fix nó
- Dashboard Grafana/Streamlit để visualize benchmark runs theo thời gian (trend analysis qua nhiều release)
- Auto-generate Action Plan dựa trên failure clustering (ví dụ: nếu cluster retrieval-miss > 10%, flag "cần upgrade retriever")

## 7. Bằng chứng đóng góp
- Commits: [paste git log]
- Files mình chủ trì: `main.py` (`run_regression_gate`), `analysis/failure_analysis.md`
