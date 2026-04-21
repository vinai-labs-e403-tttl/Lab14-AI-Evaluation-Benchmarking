# Reflection — Dang Thanh Tung

> Lab14 AI Evaluation Benchmarking - Individual Reflection

## 1. Phần mình phụ trách

- Module chính mình làm là `engine/retrieval_eval.py` và `data/synthetic_gen.py`.
- Mình cũng xây dựng bộ tài liệu nguồn trong `data/docs/`, persist dữ liệu vào `chroma_db/`, sinh `data/golden_set.jsonl` và sau đó bổ sung `doc_id` để truy vết từng sample về đúng chunk trong ChromaDB.
- Mình không phải người implement core của `Async Runner` hay `Multi-Judge`, nhưng phần mình làm là lớp dữ liệu và metrics để các module đó chạy đúng và có thể đo được chất lượng retrieval trước khi chấm generation.

## 2. Engineering Contribution

### a. Retrieval metrics

Ở commit `879540d` (`retrieval eval`), mình thay placeholder trong [engine/retrieval_eval.py](/home/dang/Projects/vinai/Lab14-team/engine/retrieval_eval.py) bằng logic thật để:

- duyệt toàn bộ dataset,
- lấy `expected_retrieval_ids`, `retrieved_ids`, `top_k`,
- tính `hit_rate` và `mrr` cho từng sample,
- sau đó aggregate thành `avg_hit_rate` và `avg_mrr`.

Điểm kỹ thuật ở đây là mình chuyển module từ dạng hard-code sang evaluator có thể chạy trên dữ liệu benchmark thật. Điều này quan trọng vì nếu retrieval không được đo độc lập thì điểm generation dễ bị “ảo”, không biết lỗi nằm ở retrieve sai hay judge chấm sai.

### b. Data generation + ChromaDB grounding

Ở commit `a75c6e1` (`gen bộ data qa mẫu`), mình làm các việc sau:

- tạo bộ tài liệu test domain-specific trong `data/docs/`,
- thêm `chromadb>=0.5.0` vào `requirements.txt`,
- persist corpus vào `chroma_db/`,
- viết lại [data/synthetic_gen.py](/home/dang/Projects/vinai/Lab14-team/data/synthetic_gen.py) để đọc trực tiếp từ ChromaDB collection `rag_lab`,
- dùng OpenAI SDK để sinh 2 câu hỏi cho mỗi document chunk,
- chuẩn hóa `context` tối đa 200 ký tự và ghi thành `golden_set.jsonl`.

Phần này là đóng góp vào pipeline đánh giá ở mức dữ liệu: benchmark không còn dùng text mẫu rời rạc mà dùng chính chunk đã được index trong vector DB. Nhờ vậy retrieval stage, expected answer và context đều bám cùng một nguồn dữ liệu.

### c. Data traceability cho evaluation

Ở commit `a942699` (`add doc_id`), mình bổ sung `doc_id` vào metadata của từng sample trong `golden_set.jsonl` và sửa generator để mỗi QA pair giữ lại id chunk gốc trong ChromaDB.

Giá trị kỹ thuật của thay đổi này là:

- trace được mỗi câu hỏi về đúng document chunk đã index,
- dễ debug khi retrieval miss,
- dễ tính hit rate/MRR dựa trên id thật thay vì so sánh text thủ công,
- hỗ trợ failure analysis vì có thể biết hệ thống fail ở chunk nào, section nào, source nào.

### d. Liên hệ với Async và Multi-Judge

Mình không trực tiếp viết `engine/runner.py` hay `engine/llm_judge.py`, nhưng phần mình làm có tác dụng trực tiếp tới hai module phức tạp đó:

- Async Runner cần dataset ổn định, có format chuẩn và có thể xử lý hàng loạt. `golden_set.jsonl` mình sinh ra đã đáp ứng điều đó.
- Multi-Judge chỉ có ý nghĩa khi input benchmark đủ grounded. Nếu không có `doc_id`, `context`, và expected answer bám document gốc, judge agreement cao vẫn chưa chắc phản ánh chất lượng thật.
- Metrics layer cần expected ids để tách lỗi retrieval khỏi lỗi generation. Đây là phần mình chịu trách nhiệm chính.

## 3. Bằng chứng qua Git commits

- `a75c6e1` - sinh bộ data QA mẫu, thêm ChromaDB corpus, viết lại pipeline tạo `golden_set.jsonl`.
- `a942699` - thêm `doc_id` vào metadata để trace sample về document chunk.
- `879540d` - hiện thực hóa retrieval evaluation với `avg_hit_rate` và `avg_mrr`.
- `3735f4b` - merge branch `main`, giúp đồng bộ phần retrieval/data của mình với các module còn lại trong team.

Nhìn theo chuỗi commit, có thể thấy phần mình làm không phải một chỉnh sửa nhỏ lẻ mà là một luồng tương đối hoàn chỉnh:

1. dựng corpus và dataset benchmark,
2. gắn dataset với vector DB thật,
3. thêm traceability bằng `doc_id`,
4. viết evaluator để đo retrieval trên chính dataset đó.

## 4. Technical Depth

### a. MRR

MRR (Mean Reciprocal Rank) đo vị trí của document đúng đầu tiên trong danh sách retrieved.

- Nếu relevant document xuất hiện ở vị trí 1 thì reciprocal rank = `1.0`.
- Nếu xuất hiện ở vị trí 2 thì reciprocal rank = `1/2 = 0.5`.
- Nếu không xuất hiện thì điểm là `0`.

MRR quan trọng hơn hit rate ở chỗ nó không chỉ hỏi “có tìm thấy hay không” mà còn hỏi “tìm thấy sớm đến mức nào”. Với RAG, document đúng nằm càng cao thì xác suất model dùng đúng context càng lớn. Vì vậy trong commit `879540d`, mình giữ cả hai chỉ số:

- `Hit Rate` để đo khả năng retrieve trúng,
- `MRR` để đo chất lượng ranking.

### b. Cohen's Kappa

Cohen's Kappa là thước đo mức độ đồng thuận giữa hai judge sau khi đã loại trừ phần đồng thuận ngẫu nhiên. Khác với agreement rate thô, Kappa hữu ích khi cần trả lời câu hỏi: “hai judge có thực sự đồng ý với nhau, hay chỉ tình cờ cho điểm giống nhau?”

Ý nghĩa thực tế:

- `Kappa` cao cho thấy judge ổn định, có thể tin cậy hơn.
- `Kappa` thấp cho thấy prompt judge chưa rõ, rubric mơ hồ, hoặc bài toán quá khó.

Trong hệ thống này, dù mình không trực tiếp implement multi-judge, mình hiểu rằng nếu sau này mở rộng từ agreement rate sang Cohen's Kappa thì quality gate sẽ chặt hơn vì đánh giá được reliability tốt hơn, không chỉ nhìn raw agreement.

### c. Position Bias

Position Bias là hiện tượng judge có xu hướng ưu ái đáp án hoặc context xuất hiện trước, dù chất lượng thật chưa chắc tốt hơn. Với LLM-as-a-Judge, đây là một rủi ro thực tế.

Nếu không kiểm soát Position Bias thì:

- judge có thể chấm thiên lệch khi so sánh A/B,
- kết quả benchmark dễ phụ thuộc vào thứ tự input,
- regression analysis có thể sai kết luận.

Một cách giảm bias là randomize thứ tự câu trả lời hoặc hoán đổi A/B rồi chấm lại. Từ góc nhìn dữ liệu, việc mình giữ `doc_id`, `source`, `section` giúp việc audit các case nghi ngờ bias dễ hơn vì có thể lần lại exact sample đã được dùng để chấm.

### d. Trade-off giữa Chi phí và Chất lượng

Trong commit `a75c6e1`, mình dùng OpenAI SDK để sinh câu hỏi từ document thật. Trade-off ở đây là:

- dùng LLM giúp câu hỏi tự nhiên hơn, đa dạng hơn, bớt cứng nhắc hơn template rule-based,
- nhưng chi phí cao hơn và thời gian tạo dataset lâu hơn,
- thêm nữa, nếu prompt không chặt thì chất lượng QA có thể không ổn định.

Mình giải quyết trade-off này bằng cách:

- chỉ sinh `2` câu hỏi cho mỗi chunk thay vì quá nhiều,
- giới hạn `context` ở `200` ký tự để dataset gọn hơn,
- ép output bằng JSON schema để giảm lỗi format,
- thêm `doc_id` để nếu chất lượng câu hỏi kém thì có thể rà lại đúng chunk gốc thay vì regenerate toàn bộ mù mờ.

Nói ngắn gọn, mình ưu tiên chất lượng benchmark đủ grounded trước, sau đó mới tối ưu cost bằng cách giữ số lượng QA vừa phải và format chặt.

## 5. Problem Solving

### Vấn đề 1: Retrieval eval ban đầu chỉ là placeholder

- Ban đầu module evaluator trả về giá trị hard-code nên không có giá trị benchmark thực tế.
- Mình thay bằng vòng lặp tính metric trên từng sample rồi aggregate lại, giúp kết quả phản ánh đúng dataset đang chạy.

### Vấn đề 2: Dataset benchmark không gắn chặt với vector DB

- Nếu chỉ có câu hỏi và expected answer mà không biết chúng thuộc chunk nào trong ChromaDB thì rất khó debug retrieval.
- Mình giải quyết bằng cách sinh dataset trực tiếp từ collection `rag_lab`, rồi thêm `doc_id` vào metadata để nối benchmark với retrieval layer.

### Vấn đề 3: Cần dữ liệu đủ thực tế để test nhiều loại câu hỏi

- Nếu dùng 1-2 file mẫu đơn giản thì benchmark sẽ quá hẹp.
- Mình tạo nhiều tài liệu thuộc các domain khác nhau như IT Security, HR, CS, SLA để agent bị buộc phải retrieve đúng nguồn và đúng section.

### Vấn đề 4: Khó tách lỗi retrieval với lỗi generation

- Không có `expected_retrieval_ids` hoặc `doc_id` thì khi answer sai rất khó biết lỗi nằm ở retrieve hay ở prompt/generation.
- Phần traceability mình thêm vào giúp failure analysis rõ ràng hơn: có thể kiểm tra retrieved chunk có đúng id không trước khi đổ lỗi cho answer hay judge.

## 6. Nếu làm lại, mình sẽ cải thiện gì

- Bổ sung `expected_retrieval_ids` tường minh cho mọi sample ngay trong lúc sinh dataset thay vì chỉ giữ `doc_id`.
- Thêm validation script để kiểm tra mỗi dòng `golden_set.jsonl` có đủ `question`, `expected_answer`, `context`, `doc_id`, `difficulty`, `type`.
- Tối ưu generator để batch hoặc cache response LLM, giảm cost khi phải regenerate dataset.
- Tạo thêm một nhóm câu hỏi khó kiểu multi-hop hoặc negative cases để retrieval metrics phản ánh sát hơn các lỗi biên.

## 7. Tự đánh giá

Mình đánh giá phần đóng góp mạnh nhất của mình nằm ở tầng dữ liệu và metrics:

- biến benchmark từ mức template sang mức có corpus thật trong ChromaDB,
- thêm khả năng trace sample về document gốc,
- và hiện thực hóa retrieval metrics để nhóm có thể đo chất lượng retrieval một cách định lượng.

Điểm mình chưa trực tiếp làm là async orchestration và multi-judge core, nhưng phần mình phụ trách là điều kiện cần để hai module đó hoạt động có ý nghĩa và để kết quả benchmark có thể giải thích được bằng dữ liệu.
