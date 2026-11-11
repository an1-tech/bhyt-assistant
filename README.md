# Chatbot tra cứu BHYT — Toàn bệnh viện · v1.11

Giao diện chính là một khung chat để tra thuốc và xét nghiệm. Bác sĩ hỏi điều kiện chung thì bot trả ngay; khi chủ động hỏi một tình huống cụ thể, bot chỉ hỏi thêm dữ kiện cần đối chiếu, không yêu cầu điền hồ sơ bệnh nhân. Bản v1.11 bổ sung HbA1c và xét nghiệm đột biến gen EGFR, với nguồn riêng và nút mở đúng dòng tài liệu.

## Mở ứng dụng

Dự án: `D:/Vinmec/bhyt-chatbot`. Nhấp đúp `start-windows.bat`, hoặc mở **http://127.0.0.1:8766/?v=1.11#lookup** nếu ứng dụng đang chạy. Bản này dùng Python có sẵn trên máy, không cần khóa API hoặc cài thêm thư viện để chạy.

Tệp `.python-path.txt` ghi đường dẫn Python đang có trên máy; nếu chuyển máy, thay bằng Python 3.10+ thực tế. Lệnh `python` mặc định của Windows có thể là Store alias. Để dừng bản chạy nền, chạy `stop-windows.ps1` bằng PowerShell; script chỉ dừng đúng tiến trình của dự án.

## Dùng chatbot

- Thử “HbA1c theo dõi đái tháo đường có điều kiện BHYT gì?”, hoặc “HbA1c hôm nay để đánh giá kết quả điều trị đái tháo đường, lần trước cách 60 ngày”.
- Thử “Xét nghiệm EGFR trong điều trị ung thư phổi không tế bào nhỏ có BHYT không?” và “Cả xét nghiệm EGFR và thuốc Erlotinib trong ung thư phổi không tế bào nhỏ có BHYT không?”.
- “Xem vị trí trích dẫn” ở câu trả lời xét nghiệm mở ảnh trọn dòng dịch vụ, bản chữ dễ đọc và liên kết PDF gốc. Không suy ra quy tắc cho xét nghiệm ngoài hai dịch vụ này.

- Gõ tên hoạt chất và bệnh/chỉ định trong một câu, bấm Gửi câu hỏi hoặc Enter. Shift + Enter xuống dòng.
- Câu trả lời nêu quy định tìm được, điều kiện áp dụng và nguồn. Thiếu dữ liệu để kết luận thì bot nói rõ giới hạn, không yêu cầu biểu mẫu ca bệnh.
- Có thể hỏi tiếp “Còn ung thư dạ dày thì sao?” hoặc “Nếu HER2 âm tính thì sao?” khi đang trao đổi về một thuốc, hoặc bấm các nút “Hỏi tiếp” bot gợi ý (ví dụ thông tin HER2/EGFR còn thiếu). Nêu tên thuốc mới để chuyển thuốc.
- Có thể gõ biệt dược đã được xác minh nguồn (Herceptin, Tarceva, Iressa); bot ghi rõ đã quy đổi sang hoạt chất nào và theo nguồn nào.
- Bấm phần căn cứ để đọc nguyên văn, mở PDF hoặc sao chép cả câu trả lời và nguồn.
- “Chat mới” xóa hội thoại trên trang. Hội thoại không được lưu xuống ổ đĩa. Không nhập thông tin định danh người bệnh.
- “Nguồn dữ liệu” cho xem bốn nhóm nguồn BHYT và sáu tài liệu lâm sàng bổ sung, với ngày ban hành và trạng thái từng bản.

## Phạm vi thật

Giữ nguyên dữ liệu gốc: 1.037 STT thuốc hóa dược/sinh phẩm (1.133 biến thể dòng), 59 STT thuốc phóng xạ/chất đánh dấu (61 biến thể dòng), 1.243 đoạn nguồn ban đầu. Cùng ba đoạn chuyển tiếp đã bổ sung trước đây, chỉ mục BHYT hiệu dụng có 1.246 đoạn.

Nguồn lâm sàng bổ sung: sáu PDF / 204 trang; chỉ 99 trang từ hai hướng dẫn được dùng trích đoạn tham khảo. Bản scan/sơ đồ và bản còn trống số/ngày ký được chỉ dẫn mở PDF hoặc chờ xác minh, không tự suy ra điều kiện chi trả.

Câu trả lời chi tiết theo nhánh chỉ định hiện được gắn nguồn cho Trastuzumab, Erlotinib, Gefitinib; Doxorubicin và Paclitaxel giữ điều kiện theo dạng bào chế. Năm bảng này nằm trong `data/indication_rules.json` (không còn viết cứng trong mã): được kiểm tra record_id, SHA-256 ghi chú và mỗi tỷ lệ phải nằm trong đoạn trích nguyên văn; chưa được Dược/BHYT bệnh viện thẩm định. Thêm thuốc mới bằng cách thêm mục vào bảng này (xem `docs/V1.9.md`). Các thuốc khác vẫn tra được danh mục/nguyên văn ghi chú, nhưng bot chưa tự kết luận đầy đủ theo mọi bệnh hoặc cách diễn đạt. Không suy ra thanh toán 100% từ ô trống.

Bộ nguồn BHYT chốt 06/11/2026; nguồn bổ sung được tìm kiếm/kiểm tra riêng ngày 07/11/2026. Không chứng minh đã rà soát mọi thay đổi mới nhất. Chưa đủ nhãn sản phẩm được phê duyệt, chuyên luận Dược thư và danh mục/hợp đồng nội bộ bệnh viện. Thông tin trong chatbot là quy định có điều kiện theo nguồn, không phải quyết định quyền lợi hoặc số tiền thanh toán cá nhân.

## Cách chạy và kiểm tra

Luồng `/api/chat` dùng `Corpus.converse()` và các nhánh trả lời có gắn nguồn, không gọi OpenAI ngay cả khi cấu hình AI cũ tồn tại. Phần tra cứu nội bộ `Corpus.chat()` và các API ca bệnh cũ còn giữ để tương thích; chúng không xuất hiện thành biểu mẫu trên giao diện. Mã AI cũ (tắt mặc định) nằm riêng trong `ai_explain.py`.

Chạy kiểm thử backend bằng Python thực tế: `python -B -m unittest discover -s tests -q`. Kiểm thử xét nghiệm riêng: `python -B -m unittest discover -s tests -p test_lab_lookup.py -q`. Chạy ứng dụng trước khi kiểm tra trình duyệt: `node tools/check-lab-ui.mjs http://127.0.0.1:8766` (cần Node 22+, Chrome/Edge và toolkit design-taste-frontend đã cài trên máy). Kết quả kiểm tra bản v1.11 và giới hạn được ghi trong `docs/LAB_LOOKUP_V1.11.md`. Các script giao diện của phiên bản cũ được giữ để tham khảo lịch sử.

Đã xem ảnh desktop, tablet và mobile. Bộ đo giao diện báo 0 FAIL / 1 WARN: cảnh báo `unused-canvas` do nhận nhầm thanh điều hướng ngang là sidebar; khung chat chủ ý rộng tối đa 840px, căn giữa với hai lề bằng nhau để đọc hội thoại. Đây là lựa chọn cho yêu cầu chỉ có một chatbot, không phải một dashboard nhiều cột.

Xem [tra cứu xét nghiệm v1.11](docs/LAB_LOOKUP_V1.11.md), [thay đổi v1.9](docs/V1.9.md), [thay đổi v1.8](docs/CHAT_ONLY_V1.8.md), [báo cáo nguồn](docs/SOURCE_UPDATE_2026-11-07.md).
