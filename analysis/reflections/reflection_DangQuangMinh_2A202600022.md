# Reflection ca nhan

Đặng Quang Minh - 2A202600022

## Vai tro trong nhom

Trong Lab 14, em dam nhan vai tro **Coder 3**, phu trach cac phan lien quan den **Multi-Judge Evaluation**, **Regression Gate**, va **tong hop metrics trong benchmark report**. Muc tieu cua phan nay la bien ket qua chay agent thanh cac chi so co the do luong duoc, tu do quyet dinh phien ban Agent V2 co du dieu kien release hay khong.

## Engineering Contribution

Git commits: "judge"
Dong gop chinh cua em nam o hai module:

- `engine/llm_judge.py`
- `main.py`

Trong `engine/llm_judge.py`, em trien khai he thong **Multi-Judge** gom hai judge doc lap:

- `semantic judge`: danh gia cau tra loi dua tren muc do bao phu y nghia cua ground truth.
- `strict judge`: cham nghiem hon, phat cac cau tra loi chung chung, thieu thong tin, hoac khong bam sat expected answer.

Sau khi co diem rieng cua tung judge, em tinh:

- `individual_scores`
- `final_score`
- `agreement_rate`
- `confidence`
- `needs_review`
- `conflict_resolution`
- `tokens_used`
- `estimated_cost`

Em cung bo sung co che goi **OpenAI API that** khi co `OPENAI_API_KEY`. He thong mac dinh co the dung `gpt-4o-mini` va `gpt-4o` lam hai judge khac nhau. Neu API bi loi, mat mang, hoac het quota, module se fallback ve heuristic judge de benchmark khong bi crash. Day la mot quyet dinh ky thuat quan trong vi pipeline danh gia can on dinh, ke ca khi phu thuoc vao dich vu ben ngoai.

Trong `main.py`, em phu trach phan tong hop ket qua benchmark va regression. Em them logic:

- Chay benchmark cho `Agent_V1_Base` va `Agent_V2_Optimized`.
- Tinh cac metric tong hop: `avg_score`, `hit_rate`, `mrr`, `agreement_rate`, `avg_latency`, `total_tokens`, `total_cost`.
- Tach rieng chi phi va token cua agent va judge: `agent_tokens`, `judge_tokens`, `agent_cost`, `judge_cost`.
- Tao `release_gate` de quyet dinh `APPROVE` hoac `BLOCK_RELEASE`.

Ket qua benchmark hien tai tren 58 test cases:

- `avg_score`: 1.1293
- `hit_rate`: 0.7931
- `mrr`: 0.7931
- `agreement_rate`: 0.756
- `avg_latency`: 0.3506 giay
- `total_cost`: 0.067712
- `release_gate.decision`: APPROVE

Em da chay `python check_lab.py` va checker xac nhan bai co du file report, co retrieval metrics, co multi-judge metrics va co thong tin regression version.

## Technical Depth

### MRR

MRR la viet tat cua **Mean Reciprocal Rank**. Metric nay dung de do chat luong retrieval, khong chi kiem tra co lay dung tai lieu hay khong, ma con xem tai lieu dung xuat hien o vi tri thu may.

Vi du:

```text
expected_retrieval_ids = ["doc_01"]
retrieved_ids = ["doc_03", "doc_01", "doc_09"]
```

Tai lieu dung `doc_01` nam o vi tri thu 2, nen reciprocal rank la:

```text
MRR = 1 / 2 = 0.5
```

Neu tai lieu dung nam o vi tri dau tien thi MRR = 1.0. Neu khong tim thay thi MRR = 0. Metric nay quan trong vi trong RAG, context dung nam cang cao thi LLM cang co kha nang sinh cau tra loi dung.

### Cohen's Kappa

Cohen's Kappa la metric do muc do dong thuan giua hai nguoi cham hoac hai judge, co tinh den kha nang dong thuan do ngau nhien. Neu chi dung agreement rate thong thuong, ta chi biet hai judge giong nhau bao nhieu phan tram. Con Cohen's Kappa di sau hon vi hoi: "Hai judge dong y voi nhau nhieu hon muc co the xay ra do may man bao nhieu?"

Trong lab nay, em chua trien khai full Cohen's Kappa, nhung da trien khai `agreement_rate` dua tren do lech diem giua hai judge. Cach nay phu hop voi thoi gian lab vi output cua judge la diem so tu 1 den 5, va minh can co mot chi so nhanh de phat hien bat dong lon. Neu tiep tuc cai tien, em se binarize hoac bucket diem judge thanh cac nhom nhu `fail`, `partial`, `pass`, sau do tinh Cohen's Kappa tren toan bo benchmark.

### Position Bias

Position Bias la hien tuong judge bi thien vi theo vi tri cua dap an. Vi du khi so sanh hai cau tra loi A va B, judge co the co xu huong uu tien cau tra loi dat o vi tri A, bat ke noi dung that su co tot hon hay khong.

Trong `llm_judge.py`, em giu ham `check_position_bias()` de co the test bang cach doi cho hai response va so sanh diem truoc/sau. Neu diem thay doi manh chi vi doi vi tri, ta co dau hieu judge khong on dinh. Day la ly do trong cac he thong evaluation nghiem tuc, viec kiem tra bias cua judge quan trong khong kem viec cham diem agent.

### Trade-off giua Chi phi va Chat luong

Dung judge manh hon nhu `gpt-4o` co the cho nhan xet tot va nghiem hon, nhung chi phi cao hon `gpt-4o-mini`. Trong benchmark hien tai, judge tokens chiem phan lon chi phi:

- `agent_cost`: 0.001939
- `judge_cost`: 0.065773

Dieu nay cho thay chi phi evaluation chu yeu den tu judge, khong phai agent. Vi vay em thiet ke `llm_judge.py` theo huong co the chuyen doi:

- Dung API that khi can ket qua chat luong cao.
- Dung fallback heuristic khi can chay nhanh, re, hoac khi debug.
- Tach `tokens_used` va `estimated_cost` de nhom co the theo doi chi phi moi lan benchmark.

Mot chien luoc toi uu sau nay la chi dung judge dat tien cho cac case kho, case bat dong giua judges, hoac case co diem gan nguong pass/fail. Cac case de co the dung `gpt-4o-mini` hoac heuristic judge de giam chi phi.

## Problem Solving

Van de dau tien em gap la pipeline can Multi-Judge nhung khong nen phu thuoc tuyet doi vao API. Neu moi lan mat mang hoac API loi ma benchmark dung lai, ca nhom se khong tao duoc `summary.json` va `benchmark_results.json`. De giai quyet, em thiet ke judge theo hai lop:

- Lop API judge: dung OpenAI de cham that.
- Lop fallback judge: dung heuristic dua tren overlap, semantic coverage va generic penalty.

Nho vay, khi API hoat dong, benchmark co ket qua judge that; khi API loi, pipeline van chay duoc va van giu dung schema output.

Van de thu hai la ket qua cua hai judge co the lech nhau. Neu chi lay trung binh don gian, nhung case conflict lon se bi che giau. Em them `agreement_rate`, `confidence`, `needs_review` va `conflict_resolution`. Khi hai judge lech lon, he thong danh dau do tin cay thap va co the yeu cau review thu cong. Cach nay giup evaluation minh bach hon.

Van de thu ba la regression khong chi nen dua vao moi `avg_score`. Mot agent co diem cao hon nhung retrieval te hon, latency cao hon hoac cost tang qua manh thi chua chac nen release. Vi vay em tao `release_gate` kiem tra nhieu dieu kien:

- Chat luong khong bi regression.
- Retrieval dat nguong chap nhan duoc.
- Agreement cua judge du tin cay.
- Latency khong tang qua nguong.
- Cost khong tang qua nguong.

Van de cuoi cung la checker cua lab chi kiem tra mot so field toi thieu, nhung rubric yeu cau sau hon. Em bo sung them cac field phuc vu phan tich nhu `mrr`, `agent_tokens`, `judge_tokens`, `agent_cost`, `judge_cost`, `needs_review_count`, `release_gate`, va `v1_metrics`. Cac field nay giup reporter co du so lieu de viet failure analysis va giai thich regression.

## Bai hoc rut ra

Qua phan Coder 3, em hieu ro hon rang evaluation khong chi la cham diem cau tra loi. Mot benchmark tot can do duoc nhieu lop:

- Retrieval co lay dung context khong.
- Generation co tra loi dung expected answer khong.
- Judge co dong thuan va dang tin khong.
- Phien ban moi co that su tot hon phien ban cu khong.
- Chi phi va latency co chap nhan duoc khong.

Neu chi nhin vao mot metric nhu `avg_score`, minh co the dua ra quyet dinh sai. Vi vay phan Multi-Judge va Regression Gate giup bien benchmark thanh mot cong cu ra quyet dinh co co so hon.
