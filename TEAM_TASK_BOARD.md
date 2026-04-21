# Task Board - Lab14 AI Evaluation Benchmarking

## Mục tiêu chung
- Hoàn thành pipeline benchmark đạt chuẩn `expert level` theo `README.md` và `GRADING_RUBRIC.md`.
- Tạo đủ file nộp bài:
  - `reports/summary.json`
  - `reports/benchmark_results.json`
  - `analysis/failure_analysis.md`
  - `analysis/reflections/reflection_[Tên_SV].md`
- Đảm bảo có:
  - `50+` test cases
  - Retrieval metrics: `hit_rate`, `MRR`
  - Multi-judge với ít nhất `2` model
  - Regression `V1 vs V2`
  - Async runner
  - Cost / token / latency tracking

---

## Phân vai
- `Coder 1`: Data + Golden Dataset + Retrieval Eval
- `Coder 2`: Agent + Async Runner + Cost/Latency
- `Coder 3`: Multi-Judge + Regression Gate + Reports logic
- `Reporter`: Failure Analysis + Reflection + Submission QA

---

## Luồng phụ thuộc
1. `Coder 1` chuẩn hóa schema của `data/golden_set.jsonl`
2. `Coder 2` sửa `agent/main_agent.py` để trả đúng schema output
3. `Coder 1` + `Coder 2` nối retrieval metrics
4. `Coder 3` nối multi-judge vào runner và summary
5. Team chạy benchmark `V1`
6. Reporter tổng hợp lỗi, team tối ưu `V2`
7. Team chạy regression `V1 vs V2`
8. Reporter chốt báo cáo và chạy `python check_lab.py`

---

## Schema thống nhất trước khi code

### 1. Schema cho từng dòng trong `data/golden_set.jsonl`
```json
{
  "id": "case_001",
  "question": "...",
  "expected_answer": "...",
  "expected_retrieval_ids": ["doc_12", "doc_15"],
  "context": "...",
  "metadata": {
    "difficulty": "easy|medium|hard",
    "type": "fact-check|adversarial|ambiguous|out-of-context|conflict|multi-turn",
    "topic": "..."
  }
}
```

### 2. Schema output của `agent/main_agent.py`
```json
{
  "answer": "...",
  "contexts": ["...", "..."],
  "retrieved_ids": ["doc_12", "doc_09", "doc_15"],
  "metadata": {
    "model": "gpt-4o-mini",
    "tokens_used": 150,
    "estimated_cost": 0.0012,
    "sources": ["policy_handbook.pdf"]
  }
}
```

### 3. Schema mỗi phần tử trong `reports/benchmark_results.json`
```json
{
  "test_case": "...",
  "agent_response": "...",
  "latency": 0.42,
  "ragas": {
    "faithfulness": 0.9,
    "relevancy": 0.8,
    "retrieval": {
      "hit_rate": 1.0,
      "mrr": 0.5
    }
  },
  "judge": {
    "final_score": 4.5,
    "agreement_rate": 1.0,
    "individual_scores": {
      "judge_a": 5,
      "judge_b": 4
    }
  },
  "status": "pass"
}
```

---

## Task Board theo người

### Coder 1 - Data + Retrieval Eval

**Phụ trách chính**
- `data/synthetic_gen.py`
- `data/golden_set.jsonl` (generated)
- `engine/retrieval_eval.py`
- Có thể hỗ trợ `README` nội bộ nếu cần ghi schema

**Mục tiêu**
- Tạo bộ `50+` test cases đủ loại hard cases
- Chuẩn hóa `expected_retrieval_ids`
- Tính đúng `hit_rate` và `MRR`

**Checklist**
- [ ] Định nghĩa schema chính thức cho golden dataset
- [ ] Sinh ít nhất `50` cases
- [ ] Có đủ các nhóm:
- [ ] `fact-check`
- [ ] `adversarial`
- [ ] `ambiguous`
- [ ] `out-of-context`
- [ ] `conflicting information`
- [ ] `hard / long-context`
- [ ] Mỗi case có `id`
- [ ] Mỗi case có `question`
- [ ] Mỗi case có `expected_answer`
- [ ] Mỗi case có `expected_retrieval_ids`
- [ ] Mỗi case có `metadata.difficulty`
- [ ] Mỗi case có `metadata.type`
- [ ] `synthetic_gen.py` ghi ra `data/golden_set.jsonl`
- [ ] `RetrievalEvaluator.calculate_hit_rate()` chạy đúng top-k
- [ ] `RetrievalEvaluator.calculate_mrr()` chạy đúng reciprocal rank
- [ ] Có hàm batch eval thực sự, không để placeholder
- [ ] Kiểm tra file tạo ra đọc được bằng `json.loads`

**Definition of done**
- Chạy `python data/synthetic_gen.py` tạo được `data/golden_set.jsonl`
- File có `>= 50` dòng hợp lệ
- `engine/retrieval_eval.py` trả được metric trung bình từ dataset thật

**Rủi ro cần tránh**
- Chỉ sinh 1-5 case như placeholder hiện tại
- Không có `expected_retrieval_ids`
- Dữ liệu không đa dạng nên failure analysis nghèo

---

### Coder 2 - Agent + Async Runner + Cost/Latency

**Phụ trách chính**
- `agent/main_agent.py`
- `engine/runner.py`

**Mục tiêu**
- Agent trả output đúng schema để benchmark được
- Runner chạy async ổn định cho `50+` cases
- Ghi nhận `latency`, `tokens`, `estimated_cost`

**Checklist**
- [ ] Sửa `MainAgent.query()` để trả `retrieved_ids`
- [ ] Giữ `contexts` trong response
- [ ] Giữ `metadata.model`
- [ ] Thêm `metadata.tokens_used`
- [ ] Thêm `metadata.estimated_cost`
- [ ] Thêm `metadata.sources`
- [ ] Nếu chưa có vector DB thật, mock retrieval hợp lý nhưng phải nhất quán với `expected_retrieval_ids`
- [ ] `BenchmarkRunner.run_single_test()` lấy đủ field từ agent response
- [ ] `BenchmarkRunner.run_single_test()` tính `latency`
- [ ] `BenchmarkRunner.run_all()` dùng async batch rõ ràng
- [ ] Có `batch_size` để tránh rate limit
- [ ] Không làm mất thứ tự kết quả
- [ ] Đảm bảo benchmark `50` cases chạy nhanh, mục tiêu `< 2 phút`
- [ ] Chuẩn bị dữ liệu đầu vào cho reporter:
- [ ] top fail cases
- [ ] latency cao nhất
- [ ] cases retrieval miss

**Definition of done**
- Runner chạy hết dataset không crash
- Mỗi result có `latency`
- Mỗi result có `ragas.retrieval`
- Có thể tính tổng token và cost từ output agent

**Rủi ro cần tránh**
- Agent không trả `retrieved_ids` nên retrieval eval không dùng được
- Runner chỉ gọi tuần tự, không đạt yêu cầu async
- Không log cost/token nên mất điểm performance

---

### Coder 3 - Multi-Judge + Regression Gate + Summary

**Phụ trách chính**
- `engine/llm_judge.py`
- `main.py`
- Có thể đụng nhẹ `engine/runner.py` nếu cần nối judge output

**Mục tiêu**
- Có ít nhất `2` judge models
- Tính `agreement_rate`
- Có logic conflict handling
- Có quyết định `APPROVE / BLOCK RELEASE` cho `V2`

**Checklist**
- [ ] Thay placeholder judge bằng 2 judge riêng
- [ ] Trả `individual_scores`
- [ ] Trả `final_score`
- [ ] Trả `agreement_rate`
- [ ] Có `reasoning` ngắn để debug
- [ ] Nếu 2 judge lệch quá ngưỡng, có chiến lược xử lý:
- [ ] average có điều kiện
- [ ] hoặc gọi tie-breaker
- [ ] hoặc đánh dấu low-confidence
- [ ] `main.py` chạy được benchmark cho `Agent_V1_Base`
- [ ] `main.py` chạy được benchmark cho `Agent_V2_Optimized`
- [ ] Tính `delta avg_score`
- [ ] Tính thêm delta cho `hit_rate`, `agreement_rate`, `latency`, `cost` nếu có
- [ ] Ghi `reports/summary.json`
- [ ] Ghi `reports/benchmark_results.json`
- [ ] Summary có `metadata.version`
- [ ] Summary có `metadata.total`
- [ ] Summary có `metrics.avg_score`
- [ ] Summary có `metrics.hit_rate`
- [ ] Summary có `metrics.agreement_rate`
- [ ] Có release gate rõ ràng:
- [ ] approve nếu chất lượng tăng
- [ ] block nếu quality tụt hoặc cost/latency xấu quá ngưỡng

**Definition of done**
- Không còn trạng thái single-judge placeholder
- `summary.json` đủ field để `check_lab.py` nhận
- Có console output hoặc summary thể hiện regression decision

**Rủi ro cần tránh**
- Chỉ dùng 1 judge sẽ bị chặn điểm nặng
- Agreement rate tính sơ sài, không phản ánh xung đột
- Summary thiếu field nên fail checker

---

### Reporter - Failure Analysis + Reflection + Submission QA

**Phụ trách chính**
- `analysis/failure_analysis.md`
- `analysis/reflections/reflection_[Tên_SV].md`
- Kiểm tra `reports/summary.json`
- Kiểm tra `reports/benchmark_results.json`
- Chạy `check_lab.py`

**Mục tiêu**
- Viết báo cáo đúng rubric
- Bám kết quả benchmark thật, không viết chung chung
- Chốt checklist nộp bài

**Checklist**
- [ ] Tạo thư mục `analysis/reflections/` nếu chưa có
- [ ] Yêu cầu mỗi thành viên viết 1 file reflection riêng
- [ ] Điền `analysis/failure_analysis.md` bằng số liệu thật
- [ ] Ghi tổng số cases
- [ ] Ghi tỉ lệ pass/fail
- [ ] Ghi điểm retrieval
- [ ] Ghi điểm judge
- [ ] Phân nhóm lỗi theo cụm:
- [ ] hallucination
- [ ] incomplete
- [ ] retrieval miss
- [ ] ambiguous handling fail
- [ ] tone / instruction-following fail
- [ ] Chọn 3 case fail nặng nhất
- [ ] Viết `5 Whys` cho từng case
- [ ] Chỉ ra root cause ở mức hệ thống:
- [ ] ingestion
- [ ] chunking
- [ ] retrieval
- [ ] prompting
- [ ] judge calibration
- [ ] Viết action plan cải tiến cho `V2`
- [ ] Đối chiếu lại repo theo submission checklist
- [ ] Chạy `python check_lab.py`
- [ ] Ghi lại lỗi checker nếu có và giao ngược lại coder sửa

**Definition of done**
- `analysis/failure_analysis.md` không còn placeholder `X/Y`, `0.XX`
- Có đủ reflection cho từng người
- `python check_lab.py` pass

**Rủi ro cần tránh**
- Viết báo cáo trước khi có số liệu thật
- Failure analysis chỉ mô tả symptom, không có root cause
- Không gom evidence từ coder nên reflection cá nhân yếu

---

## Task Board theo file

### `data/synthetic_gen.py`
- Owner: `Coder 1`
- Việc cần làm:
- [ ] Đọc nguồn text / corpus đầu vào
- [ ] Sinh `50+` QA pairs
- [ ] Thêm hard cases theo `data/HARD_CASES_GUIDE.md`
- [ ] Gắn `expected_retrieval_ids`
- [ ] Ghi `data/golden_set.jsonl`

### `engine/retrieval_eval.py`
- Owner: `Coder 1`
- Việc cần làm:
- [ ] Hoàn thiện `calculate_hit_rate`
- [ ] Hoàn thiện `calculate_mrr`
- [ ] Viết batch aggregation
- [ ] Nhận `expected_retrieval_ids` và `retrieved_ids`

### `agent/main_agent.py`
- Owner: `Coder 2`
- Việc cần làm:
- [ ] Trả `answer`
- [ ] Trả `contexts`
- [ ] Trả `retrieved_ids`
- [ ] Trả `tokens_used`
- [ ] Trả `estimated_cost`
- [ ] Trả `sources`

### `engine/runner.py`
- Owner: `Coder 2`
- Shared with: `Coder 3`
- Việc cần làm:
- [ ] Chạy agent
- [ ] Chạy retrieval evaluator
- [ ] Chạy multi-judge
- [ ] Gom `latency`
- [ ] Gom status `pass/fail`
- [ ] Batch async ổn định

### `engine/llm_judge.py`
- Owner: `Coder 3`
- Việc cần làm:
- [ ] Cấu hình 2 judges
- [ ] Tính `individual_scores`
- [ ] Tính `final_score`
- [ ] Tính `agreement_rate`
- [ ] Xử lý conflict
- [ ] Nếu kịp, thêm `position bias check`

### `main.py`
- Owner: `Coder 3`
- Shared with: `Coder 2`
- Việc cần làm:
- [ ] Chạy benchmark `V1`
- [ ] Chạy benchmark `V2`
- [ ] Tính regression delta
- [ ] Ghi `reports/summary.json`
- [ ] Ghi `reports/benchmark_results.json`
- [ ] In quyết định approve/block

### `analysis/failure_analysis.md`
- Owner: `Reporter`
- Shared with: cả team
- Việc cần làm:
- [ ] Điền benchmark overview
- [ ] Failure clustering
- [ ] 3 case `5 Whys`
- [ ] Action plan cho `V2`

### `analysis/reflections/reflection_[Tên_SV].md`
- Owner: `Reporter` theo dõi, từng người tự viết
- Việc cần làm:
- [ ] Mỗi người ghi contribution
- [ ] Kỹ thuật đã làm
- [ ] Vấn đề gặp phải
- [ ] Cách giải quyết
- [ ] Bài học rút ra

### `check_lab.py`
- Owner: `Reporter`
- Shared with: cả team
- Việc cần làm:
- [ ] Chạy trước khi nộp
- [ ] Nếu fail, assign bug fix ngược lại đúng owner

---

## Mốc thời gian đề xuất trong 4 giờ

### Giai đoạn 1 - 45 phút
- `Coder 1`: chốt schema dataset và bắt đầu sinh cases
- `Coder 2`: chuẩn hóa output schema của agent
- `Coder 3`: chốt rubric cho judge và rule regression
- `Reporter`: tạo bảng theo dõi kết quả và template reflection

### Giai đoạn 2 - 90 phút
- `Coder 1`: hoàn thiện retrieval metrics
- `Coder 2`: runner async + logging cost/latency
- `Coder 3`: multi-judge + summary + release gate
- `Reporter`: cập nhật evidence và danh sách lỗi

### Giai đoạn 3 - 60 phút
- Team chạy benchmark `V1`
- `Reporter`: phân cụm lỗi
- Team chọn 3 case fail tệ nhất
- Team làm `5 Whys`
- Team sửa nhanh để tạo `V2`

### Giai đoạn 4 - 45 phút
- Team chạy regression `V1 vs V2`
- `Reporter`: hoàn thiện `failure_analysis.md`
- Mỗi người viết reflection cá nhân
- `Reporter`: chạy `python check_lab.py`
- Team fix lỗi cuối

---

## Quy tắc phối hợp
- Mỗi người chỉ giữ ownership chính ở file đã giao để tránh conflict.
- Nếu cần sửa file shared:
- [ ] Báo trong nhóm trước
- [ ] Pull / rebase trước khi sửa
- [ ] Không overwrite code của người khác
- Mỗi người phải ghi lại:
- [ ] file đã sửa
- [ ] metric trước/sau
- [ ] 1 quyết định kỹ thuật chính
- [ ] 1 vấn đề đã xử lý

---

## Checklist cuối trước khi nộp
- [ ] `python data/synthetic_gen.py` chạy thành công
- [ ] `data/golden_set.jsonl` có `>= 50` cases
- [ ] `python main.py` chạy thành công
- [ ] Có `reports/summary.json`
- [ ] Có `reports/benchmark_results.json`
- [ ] `summary.json` có `hit_rate`
- [ ] `summary.json` có `agreement_rate`
- [ ] Có regression `V1 vs V2`
- [ ] Có `analysis/failure_analysis.md`
- [ ] Có đủ reflection cá nhân
- [ ] `python check_lab.py` pass
- [ ] Không commit `.env`

---

## Ưu tiên nếu thiếu thời gian
1. Hoàn thiện `50+ dataset` + `retrieval metrics`
2. Hoàn thiện `2-judge consensus`
3. Hoàn thiện `summary/report` để checker pass
4. Tối ưu async/performance
5. Nâng cao như `position bias`, tie-breaker phức tạp, cost optimization sâu
