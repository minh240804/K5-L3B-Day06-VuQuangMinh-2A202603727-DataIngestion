# Báo cáo cá nhân: Day 6

## Dữ liệu và pipeline

Corpus là *Sequential Problem Solving* của Fredric B. Lozo, lấy từ Project Gutenberg, ebook ID 16547. Manifest ghi rõ giấy phép Project Gutenberg, URL nguồn, ngày truy cập 2026-11-14 và quy tắc loại phần đầu/cuối khỏi nội dung chính. File nguồn là plain text nên không có trang vật lý đáng tin cậy. Pipeline chia phần nội dung chính thành 39 logical units, mỗi unit tối thiểu khoảng 1.500 ký tự, và dùng ID `TXT-n` để truy vết.

Văn bản được chuẩn hóa Unicode, line ending và khoảng trắng; phần header/footer của Project Gutenberg không được tính vào nội dung. Metadata của chunk gồm `document_id`, `source`, `page` (logical unit), `section` và `language`. Vì nguồn không có heading ổn định cho mọi unit, `section` được đặt là `Main content` khi không xác định được heading từ văn bản.

Embedding dùng `local-feature-hash-v1`, 384 chiều, chạy hoàn toàn offline bằng feature hashing từ token và character n-gram. Không dùng API key và không gửi corpus ra ngoài. Retrieval dùng cosine similarity trong pipeline local; chưa dùng persistent vector store trong lần chạy này. Đây là giới hạn cần khắc phục nếu nộp bản production, vì GUIDE yêu cầu vector store lưu bền vững.

Lệnh chạy:

```powershell
cd starter
python -m src.run
```

Chi phí API: 0. Kết quả được ghi vào `starter/results/traces.json` và `starter/results/summary.json`.

## Cấu hình và benchmark

- **A:** fixed-size chunk, 500 ký tự, overlap 50 ký tự; 184 chunk.
- **B:** paragraph-aware chunk, giới hạn 500 ký tự; 221 chunk.
- **C:** giống B nhưng áp dụng metadata filter khi câu hỏi có `filter`; 221 chunk.

Bộ benchmark có 27 câu, gồm 21 câu dev và 6 câu test. Ba câu test có metadata filter, dùng các trường `section` và `language`. Evidence được kiểm tra bằng cách tìm quote đã chuẩn hóa khoảng trắng trong text của chunk, đồng thời đối chiếu `document_id` và logical page khi có thể.

Tiêu chí so sánh được chốt trước khi xem test: ưu tiên Evidence Hit@3, sau đó Hit@1, rồi mới xem tác động của chunking, filter và chi phí tài nguyên. Không dùng test để điều chỉnh tham số.

## Kết quả retrieval

| Strategy | Split | Hit@1 | Evidence Hit@3 | Chunk count | Chi phí |
|---|---|---:|---:|---:|---:|
| A | dev | 0/21 | 1/21 | 184 | 0 |
| A | test | 1/6 | 2/6 | 184 | 0 |
| B | dev | 0/21 | 1/21 | 221 | 0 |
| B | test | 0/6 | 2/6 | 221 | 0 |
| C | dev | 0/21 | 1/21 | 221 | 0 |
| C | test | 0/6 | 2/6 | 221 | 0 |

## Chấm thủ công độc lập

Người chấm: **Vu Quang Minh (tác giả)**. Chấm riêng theo nội dung chunk và nguồn, không lấy Hit@1/Evidence Hit@3 làm nhãn thủ công.

### Chunk coherence

Chọn cùng vị trí mở đầu của 10 logical unit đầu tiên, `TXT-1` đến `TXT-10`; ở mỗi unit chấm chunk chứa ký tự mở đầu. A/B/C dùng cùng vị trí nguồn; C có chunk như B. Đây là quy tắc mẫu cố định, không chọn theo điểm retrieval. Thang điểm: 0 = không hiểu được ý; 1 = hiểu một phần/thiếu ngữ cảnh; 2 = tự hiểu được, giữ trọn ý.

| Vị trí | A | B | C | Lý do chính |
|---|---:|---:|---:|---|
| TXT-1 | 1 | 0 | 0 | A bị cắt giữa câu; B/C chỉ có thông tin đầu sách và tiêu đề “Introductory Note”. |
| TXT-2 | 1 | 1 | 1 | Cả ba bị cắt giữa câu ở phần mô tả vấn đề. |
| TXT-3 | 1 | 1 | 1 | Cả ba bị cắt giữa câu trước khi hoàn tất ý. |
| TXT-4 | 1 | 1 | 1 | Cả ba chỉ giữ một phần ví dụ về dàn ý; B/C dừng sớm hơn, ngay sau câu dẫn vào ví dụ. |
| TXT-5 | 1 | 1 | 1 | Chunk kết thúc dở ở phần “exaggeration”/tiêu đề “Memorization”. |
| TXT-6 | 1 | 1 | 1 | Cắt giữa ví dụ ghi nhớ, ngay sau “gcec”. |
| TXT-7 | 1 | 1 | 1 | Cắt giữa câu mô tả hình dung các con số. |
| TXT-8 | 1 | 2 | 2 | A cắt giữa câu hỏi; B/C giữ trọn đoạn mở đầu. |
| TXT-9 | 1 | 1 | 1 | Cắt giữa câu về các mục tiêu cơ bản. |
| TXT-10 | 1 | 1 | 1 | Cắt giữa câu phân tích nhân vật. |
| **Trung bình /2** | **1,0** | **1,0** | **1,0** | 10 vị trí mỗi cấu hình. |

### Metadata usefulness

Kiểm tra top-3 của năm câu test đầu (`T01`–`T05`), tối đa 15 bản ghi mỗi cấu hình. Thực tế có 39 bản ghi: A 15, B 15, C 9; C không trả bản ghi nào cho `T03` và `T04`. Với 39 bản ghi trả về, đường dẫn `source`, `page` (đối chiếu text với logical unit) và `language` đúng **39/39**. Tuy nhiên, đây chưa phải kết luận rằng toàn bộ metadata đúng:

- `document_id` là `SEQ_PROBLEM_SOLVING_001`, trong khi manifest khai báo `source_id` là `gutenberg-16547`; chưa có mapping giải thích hai ID này.
- `section` không đủ tin cậy để lọc: ví dụ chunk ở `TXT-29` chứa phần repression nhưng section là `1. ANGER.`, và chunk có nội dung Appendix 3 lại có thể mang nhãn `APPENDIX 1`. Các nhãn chung như `Main content` cũng không phân biệt được phần sách.
- Trong cả ba câu test có filter (`T03`, `T04`, `T06`), cấu hình C trả về **0/3 top-3 dùng được**. Không có bản ghi vi phạm filter trong các kết quả rỗng; đây là lỗi filter không tìm được kết quả, không phải bằng chứng filter hoạt động tốt. A/B không lọc nên mục này N/A.

`source` và `page` giúp truy vết chunk về văn bản; `language` không giúp phân biệt tài liệu trong corpus đơn ngữ này. Cần chuẩn hóa nhãn section và ghi rõ quan hệ giữa `source_id` với `document_id`.

### Grounding quality

Chấm thủ công 5 câu test đầu (`T01`–`T05`), điểm cho cả top-3 của từng cấu hình: 0 = không có bằng chứng; 1 = có thông tin liên quan nhưng thiếu ngữ cảnh/điều kiện; 2 = đủ bằng chứng để trả lời và truy nguồn.

| Câu test | A | B | C | Nhận xét |
|---|---:|---:|---:|---|
| T01 | 0 | 0 | 0 | Chunk top-3 nói về học tập, không nêu thứ tự nguồn thông tin theo độ tin cậy. |
| T02 | 1 | 1 | 1 | Có nói về môi trường “risk-free”, nhưng không gắn với hướng dẫn bắt đầu free association. |
| T03 | 0 | 0 | 0 | Có mục lục/từ khóa về fallacy nhưng không có định nghĩa false dilemma; C không trả kết quả. |
| T04 | 2 | 2 | 0 | A/B có nguyên văn định nghĩa repression; C không trả kết quả sau filter. |
| T05 | 2 | 2 | 2 | Có nguyên văn câu Aristotle’s Pentad dùng làm framework giải quyết vấn đề cá nhân. |
| **Điểm 0 / 1 / 2** | **2 / 1 / 2** | **2 / 1 / 2** | **3 / 1 / 1** | |
| **Trung bình /2** | **1,0** | **1,0** | **0,6** | |

Đáng chú ý, top-3 của A/B ở T04 có evidence nguyên văn tại `TXT-29`, trong khi gold ghi `TXT-32`; T05 có evidence tại `TXT-22`, trong khi gold ghi `TXT-24`. Vì vậy điểm tự động vẫn 0/6 cho test theo điều kiện khớp gold page, dù chấm grounding thủ công thấy evidence truy được trong nguồn. Đây là sai khác page ID cần sửa/kiểm chứng trong benchmark; không được coi điểm thủ công là thay thế Hit@3. T03/T04/T06 của C không có kết quả do filter không khớp metadata hiện có.

Trace đầy đủ nằm trong [traces.json](../../starter/results/traces.json); summary tự động nằm trong [summary.json](../../starter/results/summary.json).

## Phân tích và kết luận

Điểm tự động ban đầu bằng 0 chủ yếu bị ảnh hưởng bởi page ID gold không khớp logical unit, không phải bằng chứng rằng corpus bị chia mất toàn bộ. Kiểm tra trực tiếp cho thấy evidence xuất hiện trong 21/27 câu của A và 26/27 câu của B. Sau khi chuẩn hóa quote, nới kiểm tra page cho plain text và thêm lexical rerank local, kết quả là A: 1/6 Hit@1 và 2/6 Evidence Hit@3 trên test; B/C: 0/6 Hit@1 và 2/6 Evidence Hit@3. Feature hashing vẫn là baseline yếu với câu paraphrase; C còn phụ thuộc section metadata chưa đủ tin cậy.

Hai ví dụ thất bại có thể kiểm tra trong trace:

- **D01:** câu hỏi về learning sequence; chunk liên quan xuất hiện ở top-3 nhưng không đạt điều kiện evidence/page.
- **T03:** câu hỏi có filter về Appendix 3; C áp dụng filter nhưng không đưa được quote false-dilemma vào top-3.

Kết quả hiện tại chứng minh pipeline offline chạy được, tạo ba cấu hình và lưu trace. Bản 0/0 trước đó là kết quả đánh giá quá chặt với page ID và ranking baseline; sau khi kiểm tra evidence độc lập, có thể xác nhận chunking không làm mất toàn bộ dữ liệu. Tuy vậy điểm còn thấp, nên chưa đủ cơ sở kết luận A, B hay C tốt hơn về retrieval.
