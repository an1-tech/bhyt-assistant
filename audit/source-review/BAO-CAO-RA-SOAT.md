# Rà soát nguồn và OCR — chatbot BHYT toàn viện
Ngày thực hiện: 06/11/2026. Phiên bản ứng dụng sau rà soát: 1.4.

## Kết quả
- Sàng lọc 1.133 dòng thuốc hóa dược/sinh phẩm, thuộc 1.037 STT.
- 217 dòng có ghi chú điều kiện: 216 khớp sau chuẩn hóa khoảng trắng với bản chép TT20 do Bệnh viện Quảng Trị công bố. Dòng STT 279 không khớp tự động do ngắt trang/cột, đã xem ảnh trang 22–23 của bản hợp nhất và xác nhận ghi chú đủ. Đây là sàng lọc bằng bản chép, không phải kiểm chứng ảnh gốc toàn bộ 217 dòng.
- Đã xem ảnh nguồn cho 59 dòng có ký hiệu phần trăm: các chuỗi tỷ lệ khớp dữ liệu. Đã chú ý các tỷ lệ khác nhau theo chỉ định, dạng thuốc, nhóm tuổi và các ghi chú nối qua trang. Chưa phát hiện tỷ lệ cần sửa. Bảng lưu từng dòng và trang ở rate-verification.json.
- Đã đối chiếu 61 dòng thuốc phóng xạ/chất đánh dấu (59 STT) với trang 72–74 bản hợp nhất về tên, đường dùng, dạng dùng và đơn vị; chưa thấy sai lệch cần sửa. Giữ chính tả tên thuốc như nguồn, chưa chuẩn hóa danh pháp.
- Sửa 39 vị trí OCR bằng 32 quy tắc trong 17 đoạn căn cứ; không thêm hoặc xóa đoạn. Sửa ký hiệu dấu sao (*), năm dẫn chiếu 20/2022, chữ BYT, lỗi dấu tiếng Việt, MIBI, phân số ¼ và các tỷ lệ bị lỗi trong ví dụ I-131.
- Tỷ lệ 100%, 50%, 25% của ví dụ phân rã I-131 là tỷ lệ sử dụng chất phóng xạ; KHÔNG phải tỷ lệ quyền lợi BHYT.
- Ba tệp JSONL gốc không thay đổi. Lớp hiệu đính được áp dụng khi nạp nguồn; mỗi đoạn có mã băm nội dung gốc, sửa đổi cụ thể và PDF/trang đối chiếu. Nếu văn bản gốc thay đổi, hiệu đính cũ bị từ chối để tránh sửa nhầm.
- Chỉ mục embedding cũ bị loại khi nội dung hiệu đính thay đổi. Không tạo embedding, không gọi OpenAI, không cần API key.
- Kiểm thử tự động: 69/69 đạt, gồm dữ liệu gốc, tìm thuốc, ghép điều khoản nhiều trang, hiệu đính, dấu vết nguồn, cảnh báo chuyển tiếp và từ chối chỉ mục cũ.

## Các nguồn đã dùng và giới hạn
1. [15/VBHN-BYT trên Cổng thông tin Chính phủ](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/12/15-vbhn-byt.pdf): bản hợp nhất 75 trang. Đã xem ảnh các trang thuốc có tỷ lệ, các tên nghi vấn, Điều 8 và Phụ lục II; không tuyên bố đã soát từng ký tự của toàn bộ PDF.
2. [TT37/2024 trên Cổng thông tin Chính phủ](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/11/37-byt.pdf): chỉ sửa các chỗ đã đối chiếu ảnh, còn vấn đề bảng biểu trong danh sách chờ xử lý.
3. [Ảnh CV3293 có dấu/chữ ký](https://cdn.thuviennhadat.vn/upload/hinh-anh-bai-viet/NHDT/thang-8-2025/ngay-01/3293.pdf): xem cả 4 trang; bản tải từ máy chủ bên thứ ba, không phải xác thực chữ ký số hoặc bản phát hành từ cơ quan ban hành.
4. [CV5079 do Bệnh viện Đa khoa Bạc Liêu công bố](https://bvdkbaclieu.gov.vn/van-ban-phap-quy/cong-van-5079-byt-bh-2025-cua-bo-y-te-ve-viec-giai-quyet-vuo.html): xem cả 3 trang PDF đính kèm. Nội dung chính không thấy sai lệch trọng yếu với dữ liệu; PDF để trống số/ngày, không có chữ ký. Tên tệp lưu “cv5079-official.pdf” không chứng nhận đó là bản gốc ký.
5. [Bản chép TT20 tại Bệnh viện Quảng Trị](https://quangtrihospital.vn/uploads/news/2023_02/20_2022_tt-byt_ban-hanh-danh-muc-va-ty-le-dieu-kien-thanh-toan-doi-voi-thuoc-hoa.pdf): chỉ dùng sàng lọc tự động, sau đó xem ảnh gốc ở các điểm cần thiết.

Các lượt tải HTML từ cơ sở dữ liệu pháp luật trả trang chủ thay vì văn bản; không dùng làm bằng chứng. Truy cập trực tiếp bản HTML Thư Viện Pháp Luật bị từ chối, không dùng phần HTML lỗi. Các bài tin và dự thảo 2026 chỉ dùng tìm đầu mối, không nhập dự thảo vào quy định có hiệu lực.

## Điểm cần xử lý tiếp

### GAP-01 — high
Chưa nhập Điều 8 TT20/2022 về chuyển tiếp; có thể ảnh hưởng đối chiếu tỷ lệ một số thuốc ung thư.

Xử lý: Cảnh báo tại kết quả thuốc liên quan và tạm không gọi AI diễn giải; cần bổ sung đầy đủ điều và đối chiếu chuỗi hiệu lực.

### SOURCE-02 — high
PDF CV5079 từ trang bệnh viện để trống số/ngày, không có chữ ký.

Xử lý: Giữ dữ liệu hiện có với trạng thái bản gốc ký chưa xác minh; cần bản ký từ cơ quan ban hành.

### SOURCE-03 — medium
CV3293 là ảnh có dấu/chữ ký nhưng tải từ máy chủ bên thứ ba.

Xử lý: Dùng đối chiếu lỗi OCR có ghi rõ nguồn; cần đối chiếu bản phát hành chính thức.

### OCR-04 — medium
Bảng biểu TT37 trang 18/21 và nhãn annex_wastage còn vấn đề cấu trúc/khả năng trùng nội dung.

Xử lý: Chưa coi bảng là dữ liệu tính toán; cần tái trích xuất theo ô/bảng.

### NAME-05 — medium
STT 697: bản hợp nhất nhìn như Alverin cifrat; dữ liệu là Alverin citrat. STT 430 chữ trong tên nguồn khó đọc.

Xử lý: Giữ nguyên dữ liệu, không sửa tên thuốc theo suy đoán; chuyển Dược xác minh.

### TEXT-06 — medium
Bản gốc TT37 trang 9 ghi cấp có thẩm phê duyệt; CV3293 trang 3 ghi điểm b khoản Điều 14 thiếu số khoản.

Xử lý: Không tự thêm chữ/số không có trên ảnh; cần nguồn đính chính hoặc thẩm định.

### CURRENCY-07 — high
Chưa kiểm tra toàn bộ chuỗi sửa đổi/thay thế và văn bản liên quan tới 06/11/2026.

Xử lý: Không coi ngày snapshot là chứng nhận hiện hành. Tin/bản dự thảo 2026 chỉ dùng tìm đầu mối, không nhập làm quy định.

### LOCAL-08 — high
Chưa có thẩm định Dược/BHYT, danh mục hợp đồng và điều kiện áp dụng tại bệnh viện.

Xử lý: Duy trì kết quả cần đối chiếu; chưa xác nhận quyền lợi người bệnh.

## Phạm vi cảnh báo đã áp dụng
Khi tra Doxorubicin, Erlotinib, Gefitinib, Sorafenib, Everolimus, Paclitaxel hoặc nhóm tên có Asparaginase, kết quả nhắc đối chiếu Điều 8 TT20/2022 và tạm không gọi AI diễn giải. Đây là cảnh báo thiếu căn cứ, không phải kết luận từng trường hợp đủ điều kiện chuyển tiếp. Dữ liệu tra cứu và ghi chú danh mục vẫn được hiển thị.

Đối với CV3293/CV5079 và các câu có chỗ thiếu ngay trên ảnh nguồn, API trích dẫn có thêm cờ phạm vi xác minh. Chưa thiết kế thêm màn hình duyệt nguồn.

## Nhật ký hiệu đính

### TT37_2024-P3-S0-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 3.
- “Thuốc hiếm thuốc Danh mua” → “Thuốc hiếm thuộc Danh mục” (1 vị trí).

### TT37_2024-P7-S0-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 7.
- “20/2022/TT-BVT” → “20/2022/TT-BYT” (1 vị trí).

### TT37_2024-P7-S552-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 7.
- “55/2017/TT-BVT” → “55/2017/TT-BYT” (1 vị trí).

### TT37_2024-P8-S0-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 8.
- “dấu sao ($)” → “dấu sao (*)” (1 vị trí).
- “dấu sao (#)” → “dấu sao (*)” (1 vị trí).
- “y tế chí thanh toán” → “y tế chỉ thanh toán” (1 vị trí).

### TT37_2024-P9-S41-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 9.
- “kiên như sau:” → “kiện như sau:” (1 vị trí).

### TT37_2024-P10-S0-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 10.
- “quy didI tại” → “quy định tại” (1 vị trí).

### TT37_2024-P11-S43-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 11.
- “TT-BVT” → “TT-BYT” (4 vị trí).

### TT37_2024-P12-S0-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 12.
- “TT-BVT” → “TT-BYT” (1 vị trí).

### TT37_2024-P13-S833-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 13.
- “điều tri thì hôi chẩn với bác sĩ đủ điều kiên” → “điều trị thì hội chẩn với bác sĩ đủ điều kiện” (1 vị trí).

### TT37_2024-P14-S704-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 14.
- “ĐIỂU KHOẢN THI HÀ NH” → “ĐIỀU KHOẢN THI HÀNH” (1 vị trí).

### TT37_2024-P14-S1283-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 14.
- “khám bênh, chữa bênh” → “khám bệnh, chữa bệnh” (1 vị trí).
- “cơ sở kinh doanh dươc” → “cơ sở kinh doanh dược” (1 vị trí).
- “kinh tế được” → “kinh tế dược” (1 vị trí).

### TT37_2024-P15-S0-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 15.
- “TIung tâm Quốc” → “Trung tâm Quốc” (1 vị trí).

### TT37_2024-P16-S868-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 16.
- “TT-BVT” → “TT-BYT” (2 vị trí).

### TT37_2024-P19-S0-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 19.
- “(MInI)” → “(MIBI)” (1 vị trí).
- “1 kit MIDI” → “1 kít MIBI” (1 vị trí).
- “HCĐD là 1/â” → “HCĐD là ¼” (1 vị trí).

### TT37_2024-P20-S0-1
Nguồn: data/sources/37-2024-tt-byt.pdf, trang 20.
- “1-131” → “I-131” (3 vị trí).
- “TI/2” → “T1/2” (1 vị trí).
- “1009,Ủ” → “100%” (1 vị trí).
- “509’b” → “50%” (2 vị trí).
- “509/,” → “50%” (1 vị trí).
- “5€)t%” → “50%” (1 vị trí).
- “Với I-131” → “với I-131” (1 vị trí).

### CV3293_2025-UTF8-C2
Nguồn: audit/source-review/cv3293-signed-copy.pdf, trang 2.
- “hướng dẫn lại Thông tư” → “hướng dẫn tại Thông tư” (1 vị trí).
- “từ xa lại Thông tư” → “từ xa tại Thông tư” (1 vị trí).

### CV3293_2025-UTF8-C3
Nguồn: audit/source-review/cv3293-signed-copy.pdf, trang 3.
- “sử dụng thuốc phát đáp ứng” → “sử dụng thuốc phải đáp ứng” (1 vị trí).
- “được hướng của” → “được hưởng của” (1 vị trí).
- “20/2021/TT-BYT” → “20/2022/TT-BYT” (1 vị trí).

## Tệp bàn giao
- data/source_review.json: danh sách hiệu đính và cờ nguồn.
- audit/source-review/sources.json: URL, mức độ nguồn và SHA-256 PDF.
- audit/source-review/drug-screening.json: sàng lọc 1.133 dòng. Trường official_page_candidates chỉ là gợi ý tự động, có thể sai khi OCR hỏng, không dùng làm trang đã xác nhận.
- audit/source-review/rate-verification.json: 59 dòng tỷ lệ đã xem ảnh.
- audit/source-review/radio-verification.json: 61 dòng Phụ lục II.
- audit/source-review/issues.json: 8 vấn đề chưa đóng.
- audit/source-review/pages/: ảnh trang đã dựng; không phải ảnh nào đã dựng cũng được kiểm tra.
- audit/source-review/validation.json: kết quả kiểm thử và kiểm tra API sau khởi động.

Mốc 06/11/2026 của bộ dữ liệu không chứng nhận đã rà hết pháp luật có hiệu lực đến ngày đó. Đây là rà soát kỹ thuật nguồn/OCR, chưa phải thẩm định chuyên môn Dược/BHYT và chưa xác nhận quyền lợi của người bệnh. Chưa kiểm thử giao diện bằng trình duyệt trong đợt này vì không thay đổi giao diện.
