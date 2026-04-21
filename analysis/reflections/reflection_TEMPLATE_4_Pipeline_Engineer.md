# Reflection — [Tên sinh viên] (Vai trò: Pipeline / Performance Engineer)

> Template cá nhân cho vai trò Pipeline & Performance Engineer.
> Rubric trọng tâm: Performance Async (10đ) + Cost tracking.

## 1. Phần mình phụ trách
- Module chính: `engine/runner.py`, phần async execution trong `main.py`
- Cost + token tracking pipeline trong `calculate_summary()`
- Files mình commit: [liệt kê commit hash]

## 2. Quyết định kỹ thuật lớn

### a. Concurrency pattern: batched `asyncio.gather`
Mình dùng pattern **batch + gather** thay vì `Semaphore` thuần:
```python
for i in range(0, total, batch_size):
    batch = dataset[i:i + batch_size]
    tasks = [self.run_single_test(case) for case in batch]
    batch_results = await asyncio.gather(*tasks)
    results.extend(batch_results)
```
- `batch_size=10` → max 10 concurrent calls → tránh rate limit từ OpenAI (500 req/min cho tier 1).
- Ưu điểm so với `Semaphore`: đơn giản hơn, rõ batching boundary để log progress.
- Nhược điểm: tail latency trong batch kéo cả batch chờ → nếu có case rất chậm sẽ idle.

### b. Cost & Token tracking tại 2 lớp
- Agent-level: mỗi call trả `metadata.estimated_cost` + `metadata.tokens_used`.
- Judge-level: mỗi call `evaluate_multi_judge` cũng trả `tokens_used` + `estimated_cost`.
- Aggregate trong `calculate_summary()` thành 4 con số: `agent_cost`, `judge_cost`, `agent_tokens`, `judge_tokens`.

Mục đích: khi đề xuất giảm cost 30% (rubric Expert Tips), phải **biết** phần nào đang đốt tiền. Result từ benchmark thật cho thấy Judge chiếm ~60% tổng cost.

## 3. Vấn đề phát sinh & cách giải quyết
**Vấn đề thực tế** *(điền tự)*:
> Ví dụ: ban đầu mình thử làm **fully parallel** với `asyncio.gather(*all_tasks)` cho cả 58 cases cùng lúc. Chạy local thì ok, nhưng khi set OPENAI_API_KEY và chạy thật thì bị 429 Rate Limit sau case 30. Mình phải thêm batching để giới hạn ở 10 concurrent.
>
> Sau đó gặp vấn đề second-order: `asyncio.to_thread` + heavy I/O trong retriever gây contention. Fix bằng cách tách retrieval và judging thành 2 pha (retrieve all → judge all) — nhưng mình không push phiên bản này vì code hiện tại đủ đạt benchmark.

## 4. Kiến thức kỹ thuật (rubric: Technical Depth 15đ)

### a. `asyncio.gather` vs `asyncio.Semaphore` vs `asyncio.TaskGroup`
- `gather(*tasks)`: chạy song song, chờ tất cả, không giới hạn concurrency.
- `Semaphore(n)`: giới hạn n concurrent; nên dùng khi tasks không đều thời gian.
- `TaskGroup` (Python 3.11+): structured concurrency, tự handle exception tốt hơn.
- Mình chọn batched-`gather` vì code đơn giản và batch boundary giúp log dễ hơn.

### b. Tokens — vì sao đếm xấp xỉ?
Mình dùng `len(text) // 4` để xấp xỉ token count (cho fallback offline). Accurate hơn sẽ cần `tiktoken`:
```python
import tiktoken
enc = tiktoken.encoding_for_model("gpt-4o-mini")
n_tokens = len(enc.encode(text))
```
Khi có `OPENAI_API_KEY`, response từ OpenAI trả `usage.input_tokens` + `usage.output_tokens` chính xác → mình dùng luôn số đó thay cho xấp xỉ.

### c. Trade-off Cost vs Quality
| Strategy | Cost / 58 cases | Quality |
|---|---|---|
| Mini judge only | ~$0.003 | Thấp (bias theo fine-tuning data) |
| GPT-4o only | ~$0.08 | Tốt nhất |
| **Multi-judge (mini + 4o)** | ~$0.04 | Tốt + có agreement signal |
| Tiered (mini đầu, 4o khi disagree) | ~$0.015 | Gần bằng multi-judge |

**Đề xuất giảm cost 30%**: dùng **tiered judging** — chạy 2 `mini` trước, chỉ khi disagreement > 1 điểm thì escalate lên 1 lần `gpt-4o` làm arbiter.

### d. Latency metrics cần track
- `avg_latency`: trung bình — dễ bị outlier méo.
- `p50` (median): robust hơn cho case typical.
- `p95`: cho SLA — 95% user không bị chờ lâu hơn con số này.
- Trong lab mình chỉ track `avg_latency` (rubric không yêu cầu p95). **Note cho V3:** thêm p95 vào `summary.json`.

## 5. Đo impact của việc mình làm
- **Throughput**: 58 cases × 2 versions = 116 benchmark runs → 5.3 giây tổng → **~22 runs/sec**.
- Batch size=10 → mỗi batch ~0.5s (vì mỗi run chỉ có extractive answer). Khi dùng OpenAI API thật, dự kiến mỗi batch ~3–5s → 58 cases ~60s total → vẫn trong budget 2 phút.
- Cost summary (từ `reports/summary.json`): Total $0.0004 (offline BM25) — minimal, vì chủ yếu là token xấp xỉ cho reporting.

## 6. Nếu làm lại, mình sẽ...
- Switch sang `asyncio.TaskGroup` để exception handling sạch hơn
- Thêm **retry logic** với exponential backoff cho OpenAI 429
- Thêm **progress bar** (`tqdm.asyncio`) cho developer experience
- Thêm p50/p95 latency ngoài avg
- Cache judge results bằng hash(question + answer + ground_truth) — tiết kiệm re-eval khi chỉ thay prompt agent

## 7. Bằng chứng đóng góp
- Commits: [paste git log]
- Files mình chủ trì: `engine/runner.py`, `main.py` (phần `calculate_summary` và `run_benchmark`)
