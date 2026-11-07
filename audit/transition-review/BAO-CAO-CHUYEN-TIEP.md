# Bổ sung quy định chuyển tiếp — bản 1.5
Ngày thực hiện: 07/11/2026. Dự án: D:/Vinmec/bhyt-chatbot.

## Kết quả đã hoàn thành
- Bổ sung toàn văn Điều 8 TT20/2022 từ trang 4–5 bản hợp nhất 15/VBHN-BYT. Giữ đủ khoản 1, khoản 2 và các điểm a, b, c, d, đ; bỏ phần chân trang của văn bản khác và phần Điều 9 bên ngoài điều được trích.
- Thêm khoản 1 Điều 7 xác định ngày hiệu lực 01/03/2023; ghi rõ đây chỉ là trích khoản 1, không gắn nhãn toàn Điều 7.
- Đối chiếu bằng ảnh PDF chính thức. Kiểm tra bổ sung toàn văn Điều 8 với bản chép do Bệnh viện Quảng Trị công bố: khớp sau chuẩn hóa khoảng trắng. Bản chép chỉ là kiểm tra chéo, không thay nguồn PDF.
- 3 đoạn bổ sung riêng; tổng đoạn hoạt động tăng từ 1.243 lên 1.246. Ba tệp JSONL gốc vẫn giữ nguyên mã SHA-256. Không thêm thuốc, không đổi tỷ lệ hoặc ghi chú danh mục.
- Gắn đúng 7 dòng hoạt chất bằng record_id, kiểm tra tên và đường dùng khi nạp để phát hiện sai lệch. Đây là liên kết cần đối chiếu, không phải luật tự động xác nhận đủ điều kiện.
- Khi tìm thấy một phần Điều 8, hệ thống trả cả hai trang và căn cứ ngày hiệu lực. Phần tiếp trang về tỷ lệ dẫn chiếu và ngoại lệ không bị bỏ rơi.
- Hỗ trợ các câu hỏi như “Quy định chuyển tiếp”, “Điều 8 TT20/2022”, “Nội trú trước ngày 01/03/2023 rồi tiếp tục điều trị”; hỗ trợ hỏi tiếp “từ năm 2014”, “tái phát”, “gián đoạn điều trị” sau một thuốc liên quan.
- 84/84 kiểm thử đạt. Gồm kiểm tra mốc thời gian, dạng thuốc, chỉ định, đường dùng sai, ngoại lệ, câu hỏi tiếp, nhiều thuốc độc lập, nguyên vẹn dữ liệu gốc và kiểm tra ngữ cảnh quá dài.
- Đã sửa một lỗi mới phát hiện khi chạy kiểm thử: tránh thay ngữ cảnh đưa vào bằng một bản ngắn hơn trước bước kiểm tra độ dài.
- Không bật AI, không tạo embedding, không dùng API key. Chỉ mục embedding tạo từ nguồn cũ sẽ không được dùng khi mã băm nội dung thay đổi.

## Thuốc đã liên kết
| Hoạt chất | Phạm vi cần đối chiếu trong Điều 8 |
|---|---|
| Doxorubicin | Đường tiêm, dạng liposome; mốc sử dụng trước 01/01/2015 |
| Erlotinib | Đường uống; mốc trước 01/01/2015; trường hợp chuyển sang/từ Gefitinib |
| Gefitinib | Đường uống; mốc trước 01/01/2015; trường hợp chuyển sang/từ Erlotinib |
| Everolimus | Điều trị ung thư, tiêm/uống; mốc trước 01/01/2019; dẫn chiếu tỷ lệ TT40/2014 |
| L-asparaginase | Chỉ dạng erwinia, đường tiêm; mốc trước 01/01/2019 |
| Paclitaxel | Tiêm, dạng liposome hoặc polymeric micelle; mốc trước 01/01/2019 |
| Sorafenib | Phân biệt nhánh gan/thận tiến triển trước 01/01/2015 và nhánh thận tiến triển sau mốc đó; không mở rộng tự động sang chỉ định tuyến giáp |

Các nhánh trên còn yêu cầu tiếp tục sử dụng sau ngày TT20 có hiệu lực và đối chiếu toàn bộ điều kiện trong nguyên văn. Không chuyển “trước/sau” thành “trước hoặc bằng/sau hoặc bằng”; không suy ra đủ điều kiện chỉ từ năm dùng thuốc. Tỷ lệ trong danh mục và tỷ lệ quyền lợi cá nhân không đồng nhất.

## Phạm vi kiểm tra hiệu lực
- [Bản hợp nhất 15/VBHN-BYT](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/12/15-vbhn-byt.pdf), trang 4–5: Điều 8 và căn cứ ngày hiệu lực.
- [TT37/2024](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/11/37-byt.pdf), Điều 20: phần bãi bỏ nêu các Điều 3–6 TT20; không coi “hết hiệu lực một phần” là hết hiệu lực toàn bộ Điều 8.
- [TT01/2025](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/01/01-byt.pdf), trang 15: khoản 4 Điều 13 bổ sung điểm d khoản 1 Điều 2 TT20. Đã xem ảnh phần liên quan.
- [TT18/2025 trên CSDL quốc gia](https://vbpl.moj.gov.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=179250&Keyword=): phần Điều 4 được máy tìm kiếm lập chỉ mục liên quan điểm d khoản 1 Điều 2 TT20. PDF trực tiếp trả HTTP 403, nên ghi nhận giới hạn, không tuyên bố đã kiểm tra toàn văn mới nhất.
- [TT06/2026](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/4/06-byt.pdf), trang 3: phần sửa đổi được xem liên quan chữ ký điện tử và mã ICD của TT01/2025.
- Các lượt tìm kiếm có giới hạn chưa xác định được văn bản đã ban hành sửa/bãi bỏ Điều 8 TT20. Đây không phải chứng nhận đã rà hết mọi văn bản đến ngày 07/11/2026. Bản dự thảo thay thế không được nhập vào nguồn có hiệu lực.
- Giữ mốc bộ nguồn gốc 06/11/2026; ghi ngày rà soát bổ sung 07/11/2026 riêng, không nâng ngày toàn bộ bộ nguồn.

## Phần còn cần làm
1. Nhánh Điều 8 dẫn chiếu TT40/2014 vẫn cần bản tỷ lệ lịch sử tương ứng và xác minh cách áp dụng. Bản 1.5 đã có đủ Điều 8 nhưng chưa có đầy đủ bảng tỷ lệ của văn bản được dẫn chiếu.
2. Cần bộ phận Dược/BHYT duyệt các tình huống cụ thể và dữ liệu tại cơ sở.
3. Các vấn đề nguồn đã ghi ở lần trước, gồm CV5079/CV3293 và rà soát hiệu lực toàn bộ, vẫn giữ trạng thái chờ xử lý.

Vì vậy, diễn giải tự do bằng AI đối với căn cứ chuyển tiếp vẫn tạm dừng. Chatbot trả nguyên văn, liên kết nguồn và các thông tin cần đối chiếu; không tự tính tỷ lệ hay xác nhận thanh toán. Đây không phải lỗi thiếu toàn văn Điều 8 như ở bản 1.4.

## Tệp kiểm tra
- data/rag_transition.jsonl: toàn văn Điều 8 theo hai trang và trích ngày hiệu lực.
- data/transition_rules.json: ánh xạ thuốc, phạm vi và mã băm.
- audit/transition-review/legal-review.json: hồ sơ kiểm tra hiệu lực và giới hạn nguồn.
- audit/transition-review/retrieval-validation.json: kiểm tra tính đầy đủ căn cứ.
- audit/transition-review/tests.json và tests.txt: kết quả 84 kiểm thử.
- audit/transition-review/live-validation.json: kiểm tra API sau khi khởi động bản 1.5.
- Bản trước thay đổi: D:/Vinmec/backups/transition-before-2026-11-07.zip.

Không thay đổi thiết kế giao diện trong bước này; chưa thực hiện kiểm tra hình ảnh giao diện ở đợt này. Kiểm tra chức năng qua bộ kiểm thử và API cục bộ.
