# Reflection — Trinh Ngoc Tu (Vai trò: Release Analyst)

> Lab14 AI Evaluation Benchmarking - Individual Reflection
> Vai trò: Chạy benchmark, phân tích kết quả, viết báo cáo failure analysis

## 1. Phần mình phụ trách

- **Module chính**: `main.py` (orchestration), `reports/summary.json`, `reports/benchmark_results.json` (output)
- **Nhiệm vụ chính**: 
  - Chạy `python main.py` để benchmark Agent V1 vs V2 trên 58 test cases
  - Phân tích kết quả benchmark từ `reports/summary.json` và `reports/benchmark_results.json`
  - Viết báo cáo `analysis/failure_analysis.md` với phân cụm lỗi và 5 Whys root cause analysis
  - Đưa ra quyết định Release Gate dựa trên metrics

## 2. Engineering Contribution

### a. Benchmark Orchestration
Mình chạy `python main.py` để:
- Khởi động Agent V1 (baseline) và V2 (optimized)
- Chạy 58 test cases qua cả hai phiên bản
- Collect metrics: `avg_score`, `hit_rate`, `mrr`, `agreement_rate`, `avg_latency`, `total_cost`
- Tính delta (V1 vs V2) để so sánh hiệu suất

**Kết quả chạy thực tế:**
- V1 metrics: Hit Rate 87.93%, MRR 0.8103, Avg Score 3.181
- V2 metrics: Hit Rate 91.38%, MRR 0.8233, Avg Score 3.181
- V2 cải thiện retrieval (+3.45% hit rate, +0.013 MRR) nhưng **không cải thiện answer quality** (score vẫn 3.181)

### b. Failure Analysis & Root Cause Investigation
Mình phân tích 27 fail cases (53.4% pass rate) và phân cụm theo:

**Theo loại lỗi:**
- 63% (17 cases): Answer không match expected_answer → lỗi generation/judge
- 18.5% (5 cases): Retrieval miss (hit_rate=0) → lỗi retrieval
- 18.5% (5 cases): Answer generic/placeholder → lỗi template

**Theo độ khó:**
- Medium: 12 fail (cao nhất) — cần semantic understanding, BM25 không đủ
- Easy: 9 fail — bị fail do answer quá generic
- Hard: 0 fail — dataset ít case hard

### c. 5 Whys Root Cause Analysis
Mình viết 3 case study chi tiết:

**Case #1 — IAM System Query:**
- Why 1: LLM không thấy tên IAM trong context
- Why 2: Top-5 retrieved không có chunk đúng
- Why 3: BM25 token-based không match "IAM" với "Okta/Azure AD"
- Why 4: Vocabulary gap giữa query (generic) và chunk (concrete)
- **Root Cause**: Cần dense retrieval (vector embedding) thay vì keyword matching

**Case #2 — HR Working Hours:**
- Why 1: Retrieved chunk HR sai section (leave policy thay vì working hours)
- Why 2: BM25 ranking bias về chunks dài
- Why 3: Chunking không đồng đều
- **Root Cause**: Cần semantic chunking + cross-encoder reranking

**Case #3 — Ticket System:**
- Why 1: Retrieved nhiều IT helpdesk nhưng miss SLA P1 đúng
- Why 2: Query compound (2 phần) nhưng pipeline chỉ làm single-shot retrieval
- **Root Cause**: Cần Query Decomposition

### d. Release Gate Decision
Mình đưa ra quyết định **APPROVE** dựa trên:
- ✅ Quality không regression (score V2 == V1)
- ✅ Retrieval acceptable (hit rate 91.38% ≥ 75%)
- ✅ Judge reliable (agreement 96.98% ≥ 70%)
- ✅ Latency acceptable (+3.52% < 30%)
- ✅ Cost acceptable (-$0.000026, rẻ hơn V1)

**Kết luận**: V2 được release nhưng nên kết hợp với action P0 (dense retrieval) để nâng pass rate từ 53.4% lên 70%+.

## 3. Vấn đề phát sinh & cách giải quyết

### Vấn đề 1: Pass rate thấp (53.4%) không như dự kiến
- **Ban đầu**: Tưởng pass rate sẽ cao hơn vì hit rate đã 91%
- **Phát hiện**: Khi phân tích, thấy rằng hit rate cao nhưng answer quality vẫn thấp
- **Giải thích**: Hit rate cao là điều kiện **cần** nhưng không **đủ**. Cần generation quality tốt để convert retrieval thành answer đúng
- **Kết luận**: Phần retrieval của V2 tốt, nhưng phần generation (LLM prompt/template) cần cải tiến

### Vấn đề 2: Khó phân biệt lỗi retrieval vs lỗi generation
- **Ban đầu**: Khi thấy answer sai, không biết lỗi ở đâu
- **Giải pháp**: Dùng `doc_id` và `expected_retrieval_ids` để check xem retrieved chunk có đúng không
- **Kết quả**: Có thể tách rõ: 18.5% fail do retrieval miss, 63% fail do generation/judge

### Vấn đề 3: Cần giải thích tại sao V2 không cải thiện pass rate
- **Phân tích**: V2 chỉ tối ưu retrieval (reranking, better ranking), không đổi generation logic
- **Kết luận**: Để nâng pass rate, cần upgrade generation (abstractive answering, better prompting) không chỉ retrieval
- **Bài học**: Optimization phải toàn diện, không chỉ một phần

## 4. Kiến thức kỹ thuật (rubric: Technical Depth 15đ)

### a. MRR (Mean Reciprocal Rank)
MRR đo vị trí của document đúng đầu tiên trong danh sách retrieved.

**Công thức**: MRR = 1 / (vị trí đầu tiên tìm thấy relevant doc)

**Ví dụ**:
- Expected: `doc_005`, Retrieved: `[doc_012, doc_005, doc_003]`
- Position = 2 → MRR = 1/2 = 0.5

**Tại sao MRR quan trọng cho RAG**:
- Hit Rate chỉ hỏi "có tìm thấy hay không" (binary)
- MRR hỏi "tìm thấy sớm đến mức nào" (ranking quality)
- LLM chú ý nhiều vào context đầu tiên → document đúng ở top-1 tốt hơn top-5

**Trong benchmark này**:
- V1 MRR: 0.8103 (document đúng trung bình ở vị trí 1.23)
- V2 MRR: 0.8233 (document đúng trung bình ở vị trí 1.21)
- V2 cải tiến +0.013 → ranking tốt hơn

### b. Agreement Rate & Multi-Judge Reliability
Agreement Rate đo mức độ đồng thuận giữa 2 judges.

**Cách tính**:
- Score difference = 0 → Agreement = 1.0 (hoàn toàn đồng ý)
- Score difference ≤ 0.5 → Agreement = 0.8
- Score difference ≤ 1.0 → Agreement = 0.5
- Score difference > 1.0 → Agreement = 0.2 (xung đột lớn)

**Ý nghĩa**:
- Agreement cao (96.98%) → 2 judges đồng thuận tốt → kết quả tin cậy
- Nếu agreement thấp → cần review rubric judge hoặc bài toán quá khó

**Trong benchmark này**:
- Agreement rate 96.98% → rất cao, judges ổn định
- Chỉ 0 cases cần review (needs_review_count = 0)

### c. Position Bias trong LLM Judge
Position Bias là hiện tượng judge có xu hướng đánh giá cao response ở vị trí đầu tiên.

**Ví dụ**: So sánh A vs B, judge chấm A cao hơn. Nhưng khi đổi chỗ (B vs A), judge lại chấm B cao hơn → position bias detected.

**Cách kiểm soát**:
- Randomize thứ tự input
- Chạy judge 2 lần với thứ tự khác nhau
- Nếu điểm thay đổi đáng kể → có position bias

**Trong hệ thống này**:
- Multi-judge (2 judges) giúp giảm position bias vì 2 judges độc lập
- Nếu cả 2 judges đều chấm cao → kết quả tin cậy hơn

### d. Trade-off giữa Chi phí và Chất lượng Eval
| Chiến lược | Chi phí | Chất lượng | Ghi chú |
|-----------|---------|-----------|---------|
| 1 judge (GPT-4o) | Cao | Cao | Nhưng có position bias |
| 2 judges (GPT-4o-mini) | Trung bình | Cao + tin cậy | Consensus giảm bias |
| Heuristic judge | Rẻ | Thấp | Chỉ dùng khi debug |

**Quyết định trong benchmark**:
- Dùng 2 judges (semantic + strict) để tăng reliability
- Dùng GPT-4o-mini để tiết kiệm cost
- Total cost: $0.009441 cho 58 cases (~$0.000163 per case)

## 5. Problem Solving

### Vấn đề 1: Hiểu sai về pass rate
- **Ban đầu**: Tưởng hit rate 91% → pass rate sẽ ~90%
- **Phát hiện**: Chạy benchmark thấy pass rate chỉ 53.4%
- **Phân tích**: Nhận ra hit rate và pass rate là 2 metrics khác nhau
  - Hit rate: retrieval có lấy đúng chunk không
  - Pass rate: answer có match expected_answer không
- **Kết luận**: Retrieval tốt ≠ Answer tốt. Cần cả retrieval + generation tốt

### Vấn đề 2: Khó giải thích tại sao V2 không cải thiện pass rate
- **Quan sát**: V2 hit rate +3.45%, MRR +0.013, nhưng pass rate vẫn 53.4%
- **Phân tích**: V2 chỉ tối ưu retrieval (reranking), không đổi generation
- **Kết luận**: Để nâng pass rate, cần upgrade generation logic (abstractive answering, better prompting)
- **Bài học**: Optimization phải toàn diện, không chỉ một phần

### Vấn đề 3: Cần quyết định release hay không
- **Dữ liệu**: V2 cải thiện retrieval nhưng không cải thiện answer quality
- **Quyết định**: APPROVE vì:
  - Quality không regression (score vẫn 3.181)
  - Retrieval cải tiến (hit rate +3.45%)
  - Latency + cost chấp nhận được
- **Điều kiện**: Nên release khi kết hợp với action P0 (dense retrieval) để nâng pass rate

## 6. Nếu làm lại, mình sẽ...
- Chạy benchmark sớm hơn để phát hiện pass rate thấp sớm
- Phân tích chi tiết hơn từng fail case để đưa ra action plan cụ thể
- Tạo dashboard để visualize metrics (hit rate, MRR, pass rate, cost) theo thời gian
- Thêm A/B testing để so sánh nhiều strategy retrieval/generation

## 7. Bằng chứe đóng góp

- **Chạy benchmark**: `python main.py` → tạo `reports/summary.json` và `reports/benchmark_results.json`
- **Phân tích kết quả**: Đọc 2 file report, phân cụm 27 fail cases
- **Viết báo cáo**: `analysis/failure_analysis.md` với 3 case study 5 Whys
- **Đưa ra quyết định**: Release Gate APPROVE với điều kiện

## 8. Tự đánh giá

Mình đánh giá phần đóng góp của mình nằm ở tầng **Analysis & Decision Making**:

- Chạy benchmark để có dữ liệu thực tế
- Phân tích sâu để hiểu root cause của lỗi
- Viết báo cáo chi tiết để team có thể cải tiến
- Đưa ra quyết định release dựa trên dữ liệu, không phỏng đoán

Điểm mạnh: Phân tích kỹ, giải thích rõ ràng, có bằng chứng dữ liệu.
Điểm cần cải tiến: Nên chạy benchmark sớm hơn để có thời gian cải tiến dựa trên kết quả.
