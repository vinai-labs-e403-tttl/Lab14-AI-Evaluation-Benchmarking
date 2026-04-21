# Báo cáo Phân tích Thất bại (Failure Analysis Report)

> Data nguồn: `reports/benchmark_results.json` — chạy thật trên 58 test cases × 2 versions (V1 baseline, V2 optimized).
> Retriever: BM25 offline fallback trên ChromaDB (29 chunks, 5 documents).

---

## 1. Tổng quan Benchmark (V2 — Agent đã tối ưu)

| Chỉ số | V1 (Baseline) | V2 (Optimized) | Δ |
|---|---|---|---|
| Số test cases | 58 | 58 | - |
| **Pass rate (judge ≥ 3)** | 63.8% (37/58) | 63.8% (37/58) | 0.0% |
| **Hit Rate @ top-5** | 0.8793 | **0.9138** | **+3.45%** |
| **MRR** | 0.8103 | **0.8233** | +0.0130 |
| Avg judge score | 3.181 | 3.181 | 0.00 |
| Agreement rate (2 judges) | 0.970 | 0.970 | 0.00 |
| Cases with judge disagreement | 7/58 | 7/58 | — |
| Avg latency | 0.104 s | 0.121 s | +0.017 s |
| Tổng chi phí ước tính | $0.0003 | $0.0004 | +$0.0001 |

**Quan sát quan trọng:**
- V2 cải thiện Retrieval (+3.45% Hit Rate, +0.013 MRR) nhờ `top_k=5` + MMR reranking, nhưng **không cải thiện Judge Score**. Điều này hợp lý vì V2 chỉ đổi cách lấy chunk, không đổi generation logic → chất lượng answer phụ thuộc vào template, không phải vào độ đa dạng của chunks.
- → **Bài học:** Chỉ cải thiện retrieval mà không upgrade generation thì không đẩy được pass rate. Phần retrieval tốt hơn là *điều kiện cần, không phải điều kiện đủ*.

---

## 2. Phân cụm lỗi (Failure Clustering)

### 2.1 Theo loại câu hỏi (question type)
| Nhóm lỗi | Số lượng | Nguyên nhân dự kiến |
|---|---|---|
| `detail` (chi tiết cụ thể) | 6 | Query keyword ngắn → BM25 không đủ tín hiệu |
| `factoid` (dữ liệu đơn) | 6 | Từ khoá trong ground truth (tên hệ thống, email) không xuất hiện đủ đậm trong query |
| `detail_check` / `detail-check` | 4 | Câu hỏi kiểm tra chi tiết → retrieval lấy sai chunk chung chung |
| `fact` | 2 | Query cực ngắn, BM25 match sai ngữ cảnh |
| `procedural` / `procedure` | 2 | Câu hỏi quy trình bị phân mảnh qua nhiều chunks |
| `factual` | 1 | Cạnh tranh giữa các chunks tương tự |

### 2.2 Theo độ khó
| Difficulty | Số fail | Ghi chú |
|---|---|---|
| medium | 12 | Cao nhất — cần ngữ nghĩa, BM25 không match được |
| easy | 9 | Bị fail do answer template quá generic (Judge bắt) |
| hard | 0 | Golden set có ít case `hard` → cần bổ sung adversarial |

### 2.3 Theo root cause (phân cụm thủ công 21 fail)
| Root cause | Số lượng | % |
|---|---|---|
| **Retrieval sai chunk** (hit_rate=0) | 5 | 23.8% |
| **Retrieval đúng nhưng answer extract sai câu** | 10 | 47.6% |
| **Answer generic / placeholder** bị strict-judge phạt | 6 | 28.6% |

---

## 3. Phân tích 5 Whys (3 case tệ nhất)

### Case #1 — Câu hỏi về hệ thống IAM
- **Question:** *"Hệ thống IAM nào được liệt kê trong mục 'Công cụ liên quan'?"*
- **Expected:** `access_control_sop_6`
- **Retrieved (top 5):** `it_helpdesk_faq_3, it_helpdesk_faq_1, it_helpdesk_faq_4, it_helpdesk_faq_0, policy_refund_v4_2`
- **Hit Rate:** 0 — miss hoàn toàn.

1. **Symptom:** Agent trả lời hoàn toàn lệch chủ đề (không có IAM system nào trong câu trả lời).
2. **Why 1 — Generation:** LLM không thấy tên IAM trong context → không extract được.
3. **Why 2 — Retrieval:** Top-5 retrieved không có `access_control_sop_6` — chunk đúng thậm chí không ở top-10.
4. **Why 3 — Matching:** BM25 token-based không match "IAM" với nội dung chunk 6 (chunk 6 dùng tên cụ thể như "Okta", "Azure AD" chứ không viết chữ "IAM").
5. **Why 4 — Chunking + Vocabulary gap:** Keywords trong query và keywords trong ground-truth chunk thuộc hai lớp khác nhau — generic term ("IAM") vs. concrete terms ("Okta"). Đây là **vocabulary mismatch** cổ điển mà BM25 không xử lý được.
6. **Root Cause:** 🎯 **Cần dense retrieval (vector embedding) thay vì keyword matching** — embedding hiểu "IAM" ≈ "Okta / Azure AD" qua semantic space. Khi chạy với OpenAI embeddings (tier 2), hit rate cho class này dự kiến lên ~95%+.

**Action:** Export `OPENAI_API_KEY` để retriever tự nâng lên tier 2; hoặc khi chunk, ghi *embedding-friendly tags* (e.g. thêm keywords synonym vào metadata).

---

### Case #2 — Câu hỏi về giờ làm việc HR
- **Question:** *"HR làm việc vào những ngày nào và giờ hành chính bắt đầu và kết thúc vào lúc nào?"*
- **Expected:** `hr_leave_policy_4`
- **Retrieved:** `hr_leave_policy_3, it_helpdesk_faq_3, sla_p1_2026_1, ...`
- **Hit Rate:** 0 — chunk đúng bị đẩy ra khỏi top-5 bởi một chunk HR khác.

1. **Symptom:** Retrieved được tài liệu HR đúng (`hr_leave_policy_3`) nhưng **sai section** — chunk 3 nói về leave policy, không phải giờ làm việc.
2. **Why 1:** Chunks cùng document cạnh tranh nhau — BM25 chọn chunk có nhiều keyword lặp lại ("HR", "làm việc") mà không hiểu ngữ nghĩa "giờ hành chính" khác "ngày nghỉ phép".
3. **Why 2:** Câu hỏi là compound query (ngày + giờ) — BM25 ranking dựa trên tần suất keyword, không penalize khi chunk chỉ match 1 trong 2 vế.
4. **Why 3:** Chunking strategy chia document HR thành 5 chunks, mỗi chunk ~1 section. Section "giờ làm việc" (chunk 4) ngắn hơn section "leave policy" (chunk 3) → ít keyword hơn → BM25 xếp thấp.
5. **Why 4 — Chunking + Length bias:** BM25 có length normalization nhưng không đủ mạnh cho chunks ngắn chứa facts chính xác.
6. **Root Cause:** 🎯 **Chunking không đồng đều + BM25 bias về chunks dài.** Giải pháp: (a) re-chunk để có chunks cùng kích cỡ (~300 tokens), (b) thêm bước reranking dùng cross-encoder để ưu tiên semantic match, (c) thêm metadata filter theo section.

**Action:** V3 nên thử `semantic chunking` (chia theo ý) + filter metadata `section` khi retrieve.

---

### Case #3 — Câu hỏi về hệ thống ticket
- **Question:** *"Hệ thống ticket nào được sử dụng và tên dự án liên quan là gì?"*
- **Expected:** `sla_p1_2026_3`
- **Retrieved:** `it_helpdesk_faq_1, it_helpdesk_faq_4, sla_p1_2026_0, access_control_sop_3, it_helpdesk_faq_3`
- **Hit Rate:** 0 — `sla_p1_2026_3` không có trong top-5.

1. **Symptom:** Retrieved nhiều chunk IT Helpdesk nhưng miss chunk SLA P1 đúng.
2. **Why 1:** "Ticket" là keyword xuất hiện ở cả IT helpdesk FAQ (nói về VPN ticket, email ticket) và SLA P1 → BM25 đưa FAQ lên top vì có tần suất cao hơn.
3. **Why 2:** Chunk `sla_p1_2026_3` (chứa đáp án về Jira + project name) bị cạnh tranh bởi chunk `sla_p1_2026_0` (general SLA intro) — cả hai cùng document.
4. **Why 3:** Query có 2 hợp phần ("hệ thống ticket" + "tên dự án") nhưng keyword "hệ thống" bị share với nhiều tài liệu, còn "tên dự án" thì quá generic.
5. **Why 4 — Query intent:** Người dùng hỏi câu gộp cần compound retrieval, nhưng pipeline hiện tại chỉ làm single-shot retrieval.
6. **Root Cause:** 🎯 **Thiếu Query Decomposition.** Với multi-part questions, nên tách thành 2 queries con ("hệ thống ticket nào?", "tên dự án là gì?"), retrieve riêng, rồi merge.

**Action:** Thêm pre-processing step dùng LLM để phân tách multi-part queries.

---

## 4. Kế hoạch cải tiến (Action Plan — V3)

Ưu tiên theo tỷ lệ impact / effort:

- [ ] **P0 — Bật Dense Retrieval (vector embedding)** — Fix ngay vocabulary gap (Case #1). Chỉ cần set `OPENAI_API_KEY` → retriever tự động nâng lên tier 2. Dự kiến Hit Rate @ top-5 tăng từ 91% → 96%+.
- [ ] **P1 — Chunk metadata filter** — Thêm filter theo `section` / `department` để loại chunk không liên quan (Fix Case #2). Đã có sẵn metadata trong ChromaDB, chỉ cần wire lên query.
- [ ] **P1 — Cross-Encoder Reranking** — Thay MMR bằng `ms-marco-MiniLM` để rerank top-20 thành top-5. Dự kiến MRR tăng từ 0.82 → 0.90+.
- [ ] **P2 — Query Decomposition** — Dùng LLM nhỏ (gpt-4o-mini) decompose compound queries (Fix Case #3). Tăng cost eval nhưng đáng cho cases khó.
- [ ] **P2 — Semantic Chunking** — Thay fixed-size chunking bằng semantic chunking (boundary theo ý, không theo byte). Giải quyết length bias.
- [ ] **P3 — Bổ sung adversarial cases** — Golden set hiện 0 case `hard`. Thêm 10 cases kiểu prompt injection, out-of-context, ambiguous để Red Team.
- [ ] **P3 — Upgrade Generation** — Answer hiện là extractive, nên tốt hơn bằng abstractive (gọi LLM thật) để pass rate tăng theo Hit Rate thay vì plateau ở 63.8%.

---

## 5. Release Gate Decision

V2 được **APPROVE** cho release dựa trên:
- ✅ `quality_not_regressed`: Judge score V2 == V1 (không giảm)
- ✅ `retrieval_acceptable`: Hit Rate 91.4% ≥ 75%, MRR 0.82 ≥ 0.5
- ✅ `judge_reliable`: Agreement rate 97% ≥ 70%
- ✅ `latency_acceptable`: V2 latency +16% (< ngưỡng +30%)
- ✅ `cost_acceptable`: V2 cost +$0.0001 (< ngưỡng +30%)

→ **APPROVE** với note: V2 cải thiện retrieval nhưng **không** cải thiện end-to-end answer quality. Chỉ nên release khi kết hợp với một trong các action P0–P1 ở trên.
