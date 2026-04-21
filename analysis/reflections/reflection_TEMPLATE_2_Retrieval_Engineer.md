# Reflection — [Tên sinh viên] (Vai trò: Retrieval Engineer)

> Template cá nhân cho vai trò Retrieval Engineer. Đây là phần có nhiều điểm technical depth nhất — mình nên viết sâu.

## 1. Phần mình phụ trách
- Module chính: `engine/real_retriever.py`, `engine/retrieval_eval.py`
- Tích hợp ChromaDB từ Lab 8 vào agent
- Files mình commit: [liệt kê commit hash]

## 2. Quyết định kỹ thuật lớn: 3-tier fallback retriever

Khi nhóm thảo luận, có 2 option:
- **Option A:** Dùng thẳng code Lab 8, require `OPENAI_API_KEY` để chạy.
- **Option B:** Viết retriever có fallback để không ai trong nhóm bị block khi develop.

Mình chọn **Option B** và thiết kế 3 tầng:
1. **Tier 1:** Import `get_embedding` từ `index.py` (Lab 8) — dùng nếu có.
2. **Tier 2:** OpenAI `text-embedding-3-small` trực tiếp nếu có API key.
3. **Tier 3:** BM25 offline — tokenize tiếng Việt (normalize diacritics) → chạy được mọi lúc.

Tất cả 3 tầng đều trả về cùng doc_id format trong ChromaDB → Hit Rate metric không bị ảnh hưởng.

**Trade-off:** BM25 có chất lượng thấp hơn dense (vocabulary gap — xem Case #1 trong failure analysis). Nhưng offline được là value lớn cho workflow nhóm.

## 3. Vấn đề phát sinh & cách giải quyết
**Vấn đề thực tế** *(điền tự)*:
> Ví dụ: code ban đầu trong `main_agent.py` có bug bí mật — `_simulate_retrieval` truyền `expected_ids` vào retrieval rồi copy ngược vào retrieved_ids để "đảm bảo hit rate 85%". Đây là **data leakage** trắng trợn. Mình phát hiện khi thử set `expected_ids=None` thì hit rate tụt xuống 0. Fix: loại bỏ parameter `expected_ids` khỏi retrieval path hoàn toàn.

## 4. Kiến thức kỹ thuật (rubric: Technical Depth 15đ)

### a. **MRR (Mean Reciprocal Rank)**
```
MRR = (1/N) * Σ (1 / rank_i)
```
với `rank_i` = vị trí đầu tiên mà retrieved_ids chứa expected_id (1-indexed). Nếu không hit → RR = 0.

- **Vì sao MRR tốt cho RAG nhưng không đủ?** — MRR chỉ quan tâm vị trí đầu tiên của 1 chunk đúng. Nếu expected có nhiều chunks (ví dụ câu hỏi cần tổng hợp 3 chunks), MRR không phản ánh được. Khi đó cần **MAP (Mean Average Precision)** hoặc **NDCG**.

### b. **Hit Rate @ k vs Recall @ k**
- Hit Rate@k = 1 nếu *có ít nhất 1* expected trong top-k, 0 nếu không. Binary.
- Recall@k = *tỷ lệ* expected xuất hiện trong top-k. Fractional.
- Trong lab này mình dùng Hit Rate@5 vì mỗi case thường chỉ có 1 ground-truth chunk.

### c. **Vocabulary Gap & vì sao BM25 thua Dense Retrieval**
Case #1 trong failure analysis: query "Hệ thống **IAM**" cần match chunk chứa "**Okta**, **Azure AD**". BM25 là **exact keyword match** → không hiểu IAM ⊃ {Okta, Azure AD}. Dense embedding đã học được khái niệm này trong quá trình training → cosine similarity giữa vector "IAM" và "Okta" cao. Đây là lí do hybrid retrieval (BM25 + dense) thường vượt trội cả hai.

### d. **Cosine similarity trong ChromaDB**
ChromaDB trả về `distance` theo công thức `1 - cosine_similarity`. Mình convert: `score = max(0, 1 - distance)`. Dimension embedding của collection là **1536** (OpenAI `text-embedding-3-small`).

### e. **MMR Reranking (dùng cho V2)**
```
MMR(d_i) = λ * sim(d_i, query) - (1-λ) * max_{d_j ∈ selected} sim(d_i, d_j)
```
λ=0.7 trong implementation của mình. Khi λ=1 → chỉ tối ưu relevance (= không rerank). Khi λ=0 → chỉ tối ưu diversity. Trade-off: quá đa dạng thì có thể bỏ sót chunks rất relevant.

## 5. Đo impact của việc mình làm
Trước fix:
- Hit Rate giả 85% (hard-coded bằng `random.random() > 0.15`)
- retrieved_ids format `doc_000...` không khớp golden set
- Không thể làm failure analysis có ý nghĩa

Sau fix:
- Hit Rate thật V1=87.9%, V2=91.4% (data thật từ ChromaDB)
- retrieved_ids khớp 100% format golden set (`access_control_sop_X`, ...)
- Đã identify được 5 retrieval-miss cases để làm 5 Whys

## 6. Nếu làm lại, mình sẽ...
- Add hybrid retrieval (BM25 + dense) thay vì fallback
- Implement Cross-Encoder reranker (ms-marco-MiniLM) thay vì MMR-lite
- Thêm metadata filter (`section`, `department`) khi retrieve

## 7. Bằng chứng đóng góp
- Commits: [paste git log]
- Files mình chủ trì: `engine/real_retriever.py`, `engine/retrieval_eval.py`
