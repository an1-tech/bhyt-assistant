# Chatbot tra cứu thuốc BHYT — Toàn bệnh viện · v1.8

Giao diện chính là một khung chat. Bác sĩ hỏi: **“Thuốc X dùng điều trị bệnh Y có được BHYT chi trả không?”** Bot trả lời thông tin chi trả chung, điều kiện và căn cứ, không yêu cầu điền hồ sơ bệnh nhân.

## Mở ứng dụng

Dự án: `D:/Vinmec/bhyt-chatbot`. Nhấp đúp `start-windows.bat`, hoặc mở **http://127.0.0.1:8766/?v=1.8#lookup** nếu ứng dụng đang chạy. Bản này dùng Python có sẵn trên máy, không cần khóa API hoặc cài thêm thư viện để chạy.

Tệp `.python-path.txt` ghi đường dẫn Python đang có trên máy; nếu chuyển máy, thay bằng Python 3.10+ thực tế. Lệnh `python` mặc định của Windows có thể là Store alias. Để dừng bản chạy nền, chạy `stop-windows.ps1` bằng PowerShell; script chỉ dừng đúng tiến trình của dự án.

## Dùng chatbot

- Gõ tên hoạt chất và bệnh/chỉ định trong một câu, bấm Gửi câu hỏi hoặc Enter. Shift + Enter xuống dòng.
- Câu trả lời nêu quy định tìm được, điều kiện áp dụng và nguồn. Thiếu dữ liệu để kết luận thì bot nói rõ giới hạn, không yêu cầu biểu mẫu ca bệnh.
- Có thể hỏi tiếp “Còn ung thư dạ dày thì sao?” hoặc “Nếu HER2 âm tính thì sao?” khi đang trao đổi về một thuốc. Nêu tên thuốc mới để chuyển thuốc.
- Bấm phần căn cứ để đọc nguyên văn, mở PDF hoặc sao chép cả câu trả lời và nguồn.
- “Chat mới” xóa hội thoại trên trang. Hội thoại không được lưu xuống ổ đĩa. Không nhập thông tin định danh người bệnh.
- “Nguồn dữ liệu” cho xem bốn nhóm nguồn BHYT và sáu tài liệu lâm sàng bổ sung, với ngày ban hành và trạng thái từng bản.

## Phạm vi thật

Giữ nguyên dữ liệu gốc: 1.037 STT thuốc hóa dược/sinh phẩm (1.133 biến thể dòng), 59 STT thuốc phóng xạ/chất đánh dấu (61 biến thể dòng), 1.243 đoạn nguồn ban đầu. Cùng ba đoạn chuyển tiếp đã bổ sung trước đây, chỉ mục BHYT hiệu dụng có 1.246 đoạn.

Nguồn lâm sàng bổ sung: sáu PDF / 204 trang; chỉ 99 trang từ hai hướng dẫn được dùng trích đoạn tham khảo. Bản scan/sơ đồ và bản còn trống số/ngày ký được chỉ dẫn mở PDF hoặc chờ xác minh, không tự suy ra điều kiện chi trả.

Câu trả lời chi tiết theo nhánh chỉ định hiện được gắn nguồn cho Trastuzumab, Erlotinib, Gefitinib; Doxorubicin và Paclitaxel giữ điều kiện theo dạng bào chế. Năm bảng nguồn này được kiểm tra record_id và SHA-256 ghi chú; chưa được Dược/BHYT bệnh viện thẩm định. Các thuốc khác vẫn tra được danh mục/nguyên văn ghi chú, nhưng bot chưa tự kết luận đầy đủ theo mọi bệnh hoặc cách diễn đạt. Không suy ra thanh toán 100% từ ô trống.

Bộ nguồn BHYT chốt 06/11/2026; nguồn bổ sung được tìm kiếm/kiểm tra riêng ngày 07/11/2026. Không chứng minh đã rà soát mọi thay đổi mới nhất. Chưa đủ nhãn sản phẩm được phê duyệt, chuyên luận Dược thư và danh mục/hợp đồng nội bộ bệnh viện. Thông tin trong chatbot là quy định có điều kiện theo nguồn, không phải quyết định quyền lợi hoặc số tiền thanh toán cá nhân.

## Cách chạy và kiểm tra

Luồng `/api/chat` dùng `Corpus.converse()` và các nhánh trả lời có gắn nguồn, không gọi OpenAI ngay cả khi cấu hình AI cũ tồn tại. Phần tra cứu nội bộ `Corpus.chat()` và các API ca bệnh cũ còn giữ để tương thích; chúng không xuất hiện thành biểu mẫu trên giao diện v1.8.

Chạy kiểm thử backend bằng Python thực tế: `python -B -m unittest discover -s tests -q`. Bản này đạt 137 kiểm thử. Kiểm tra giao diện hiện tại: `node tools/check-chat-ui.mjs` (cần Node 22+ và Chrome/Edge cùng toolkit đã cài trên máy), đạt 67 kiểm tra ở 1440/768/390px. Những script browser của các bản 1.6/1.7 được giữ để tham khảo lịch sử, không phải bộ kiểm tra giao diện hiện tại.

Đã xem ảnh desktop, tablet và mobile. Bộ đo giao diện báo 0 FAIL / 1 WARN: cảnh báo `unused-canvas` do nhận nhầm thanh điều hướng ngang là sidebar; khung chat chủ ý rộng tối đa 840px, căn giữa với hai lề bằng nhau để đọc hội thoại. Đây là lựa chọn cho yêu cầu chỉ có một chatbot, không phải một dashboard nhiều cột.

Xem [thay đổi v1.8](docs/CHAT_ONLY_V1.8.md), [báo cáo nguồn](docs/SOURCE_UPDATE_2026-11-07.md), `audit/CHAT_ONLY_V1.8_VALIDATION.json` và `audit/SOURCE_SEARCH_2026-11-07.json`.
