# Báo cáo cá nhân — Day 6

## Dữ liệu và pipeline

- **Chủ đề, nguồn và quyền:** Sách *How to Study and Teaching How to Study* của Frank M. McMurry, lấy từ Project Gutenberg ebook #6109. Corpus được chuẩn bị từ `starter/data/books.txt`. Nguồn chính thức: <https://www.gutenberg.org/ebooks/6109>. File giữ thông tin Project Gutenberg License; việc gửi nội dung tới embedding API cần được đối chiếu với điều khoản hiện hành của provider và luật tại nơi chạy. Không có dữ liệu cá nhân trong corpus.
- **Quy mô và quy tắc tính:** 30 đơn vị nội dung, gồm Preface và 11 chapter. Các đơn vị được cắt tại ranh giới đoạn văn, mỗi unit giữ `unit_id`, section và khoảng dòng nguồn. Corpus đã loại wrapper, mục lục không dùng cho retrieval và phần license boilerplate khỏi text ingest.
- **Chuẩn hóa, lỗi và giới hạn:** Chuẩn hóa Unicode, khoảng trắng và dòng trống; giữ liên kết về source line. Không dùng OCR. Một số evidence ban đầu có dấu `...` và bị thay bằng đoạn trích liên tục có thật trong corpus. T04 được chỉnh để không phụ thuộc vào mục lục đã loại khỏi corpus. T07 và T20 được sửa section về Chapter IV theo vị trí thực tế của evidence.
- **Embedding và lưu trữ:** OpenAI-compatible Embeddings API, model `text-embedding-ada-002`, 1.536 chiều, dùng cùng model cho A/B/C. Endpoint lấy từ `BASE_URL`, khóa lấy từ `OPENAI_API_KEY` trong `.env`. Vector store là Chroma persistent 1.5.9, cosine distance, lưu tại `starter/results/chroma`. Chi phí API chưa được ghi lại trong log chạy.
- **Metadata:** Mỗi chunk có `document_id`, `source`, `page` (source line start), `unit_id`, `section`, `chapter` và `language`. Filter dùng `section` và `language`; các giá trị lấy từ corpus, không tự đoán.

## Cấu hình và benchmark

- **A — Fixed-size:** cửa sổ 1.200 ký tự, overlap 150 ký tự. Kết quả có 487 chunk.
- **B — Structure-aware:** gom theo paragraph, giới hạn 1.400 ký tự; paragraph dài hơn giới hạn được tách tiếp. Kết quả có 481 chunk.
- **C — Structure-aware + metadata filter:** dùng đúng 481 chunk và embedding của B, áp dụng filter của câu hỏi trước khi tìm kiếm. Khác biệt B–C chỉ là filter.
- **Benchmark:** 20 câu hỏi, chia trước thành 15 dev và 5 test. Có câu trực tiếp, paraphrase và câu cần filter theo `section`/`language`. Evidence được kiểm tra lại để là đoạn liên tục trong corpus; mỗi câu có `gold_page`, `evidence_quote` và khoảng ký tự chuẩn hóa.
- **Tiêu chí chọn:** ưu tiên Evidence Hit@3, sau đó Hit@1, rồi mới xét chi phí và thời gian. Kết quả test chỉ được dùng để đánh giá sau khi cấu hình đã cố định.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian ingest | Chi phí |
|---|---:|---:|---:|---:|---:|---|
| A | dev | 2/15 | 5/15 | 487 | 24,68 s | Chưa ghi |
| A | test | 3/5 | 3/5 | 487 | 24,68 s | Chưa ghi |
| B | dev | 0/15 | 0/15 | 481 | 45,12 s | Chưa ghi |
| B | test | 0/5 | 0/5 | 481 | 45,12 s | Chưa ghi |
| C | dev | 1/15 | 2/15 | 481 | 0,69 s* | Chưa ghi |
| C | test | 0/5 | 0/5 | 481 | 0,69 s* | Chưa ghi |

\* C dùng lại embedding đã tạo cho B nên thời gian chủ yếu là upsert collection và không đại diện cho một lần embed độc lập.

| Strategy | Coherence trung bình /2 | Metadata đủ và đúng | Filter tuân thủ | Grounding 0/1/2 |
|---|---|---|---|---|
| A | 1,2/2 | Đủ, nhất quán 60/60 hit | N/A — không dùng filter | N/A — trace không có câu trả lời |
| B | 1,6/2 | Đủ, nhất quán 60/60 hit | N/A — không dùng filter | N/A — trace không có câu trả lời |
| C | 2,0/2 | Đủ, nhất quán 59/59 hit | Đúng section trong top-3: dev 15/15, test 5/5 | N/A — trace không có câu trả lời |

Đường dẫn trace: [traces.json](../../starter/results/traces.json). Tổng hợp tự động: [summary.json](../../starter/results/summary.json). Cấu hình đã chọn: [DECISIONS.md](../../starter/DECISIONS.md).

**Ghi chú chấm độc lập:** Coherence được chấm trên chunk top-1 của 5 câu test (2 = ngữ cảnh trọn ý, 1 = còn hiểu được nhưng bị cắt, 0 = mảnh rời khó hiểu); đây là coherence của ngữ cảnh truy xuất, không phải câu trả lời. A bị trừ điểm vì cửa sổ ký tự cắt giữa từ/câu; B có một số chunk chạm giới hạn 1.400 ký tự; C trả về các chunk trọn đoạn hơn. Metadata được kiểm tra trên mọi hit trong trace: đủ `document_id`, `source`, `page`, `unit_id`, `section`, `chapter`, `language`; `section` nhất quán với `chapter`, ngôn ngữ là English. Grounding câu trả lời không thể chấm từ trace vì không lưu câu trả lời được sinh ra; chỉ số bằng chứng truy xuất tương ứng là Evidence Hit@3: A 8/20, B 0/20, C 2/20.

## Phân tích và kết luận

- **A–B:** A tốt hơn rõ rệt. A đạt 3/5 Hit@1 và 3/5 Evidence Hit@3 trên test. B không đạt câu nào; top-3 của B thường rơi vào Chapter VIII–XI dù câu hỏi thuộc Preface–Chapter V. Điều này cho thấy chunk theo paragraph hiện thiếu ngữ cảnh heading hoặc tạo các mảnh quá ngắn, khiến embedding khó định vị đúng phần tài liệu.
- **B–C:** Filter của C hoạt động đúng ở cấp section: 5/5 câu test đều trả về đúng chapter trong top-3. Tuy nhiên C vẫn đạt 0/5 Evidence Hit@3 vì việc giới hạn đúng chapter chưa đủ để tìm đúng đoạn bằng chứng bên trong chapter dài. Cải thiện metadata không tự động tạo ra retrieval chính xác hơn.
- **Ví dụ sai 1 — T17:** C trả về đúng Chapter II trong top-3 nhờ filter, nhưng không đưa đoạn evidence về thái độ của người học với tác giả vào top-3. A/B lại trả về các chapter khác hoặc không có evidence phù hợp.
- **Ví dụ sai 2 — T18:** A trả về các chunk thuộc Chapter VIII/V; B trả về Chapter VIII/IX/X; C giữ đúng Chapter III nhưng vẫn không lấy được đoạn nói về việc trẻ tự xác định mục tiêu học tập. Đây là lỗi định vị trong cùng phạm vi section, không phải lỗi metadata filter.
- **Chiến lược tạm chọn:** A là baseline tốt nhất theo kết quả hiện tại. Không chọn B hoặc C làm cấu hình cuối cùng cho đến khi bổ sung heading vào nội dung embedding và kiểm tra lại cách tách paragraph. C vẫn có giá trị làm thí nghiệm về tác động của metadata filter; grounding câu trả lời cần được audit khi trace có lưu output sinh.
- **Giới hạn:** Tập test chỉ có 5 câu; coherence được chấm trên top-1 của tập nhỏ này, còn grounding câu trả lời chưa thể chấm nếu không lưu output sinh. Chi phí API chưa được ghi lại. Evidence Hit@3 yêu cầu evidence nguyên văn nằm trong top-3; evidence bị tách qua nhiều chunk vẫn có thể cần người chấm xem lại.
- **Nếu làm lại:** thêm heading/chapter vào đầu text của chunk B/C; thêm metadata subsection; thử giới hạn chunk khác; giữ nguyên benchmark test; lưu câu trả lời sinh ra để có thể audit grounding độc lập.
