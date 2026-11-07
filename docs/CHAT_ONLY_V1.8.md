# Chatbot thuốc + bệnh v1.8 — 07/11/2026

## Nghiệp vụ đã chỉnh

Một khung chat trả lời câu hỏi chung về chi trả BHYT cho thuốc dùng trong bệnh/chỉ định. Không có form ca bệnh, chọn khoa, giai đoạn hay kết quả xét nghiệm bắt buộc. Điều kiện trong nguồn được nêu trong câu trả lời để bác sĩ đọc, không biến thành yêu cầu điền hồ sơ.

Ví dụ người dùng gõ “Trastuzumab điều trị ung thư vú có được BHYT chi trả không?” thì bot dẫn nhánh ghi chú tương ứng, nêu HER2 dương tính và tỷ lệ có điều kiện theo nguồn, không đợi chọn HER2. Nếu câu hỏi đã nêu xét nghiệm âm tính, bot chỉ ra điều kiện không khớp; không biến thành quyết định từ chối toàn bộ quyền lợi.

## Mã và dữ liệu

- `indication_chat.py`: nhận biết một số chủ đề/cách hỏi và diễn đạt các nhánh nguồn đã có; xác minh hash của năm ghi chú. Không phải bộ suy luận cho mọi bệnh.
- `engine.py`: thêm `converse()` cho hội thoại chung, giữ tra cứu nền và chuỗi văn bản. Tên thuốc mới hoặc bệnh mới không kế thừa kết luận của bệnh cũ. Luồng mới không gọi OpenAI.
- `server.py`: `/api/chat` dùng `converse()`, phiên bản 1.8.
- `web/index.html`, `web/app.js`, `web/style.css`: một ô chat, hội thoại theo thứ tự gửi, câu hỏi tiếp, căn cứ mở rộng, sao chép, chat mới và thư viện nguồn. Gỡ biểu mẫu ca bệnh khỏi HTML và không tải case.js.
- Không đổi dữ liệu BHYT gốc, tỷ lệ ghi trong nguồn, tệp nguồn lâm sàng hoặc bảng thẩm định nguồn. Giữ API ca bệnh cũ cho tương thích nhưng không đưa lên màn hình chính.

## Trả lời trong phạm vi nguồn

Các nhánh Trastuzumab, Erlotinib và Gefitinib có câu trả lời theo chủ đề đã nhận biết; Doxorubicin và Paclitaxel giữ ghi chú dạng thuốc. Tất cả thuốc trong danh mục vẫn tra được. Với bệnh khác hoặc khi thiếu nhãn/hướng dẫn/Dược thư đủ căn cứ, câu trả lời chỉ ra phần chưa xác định thay vì khẳng định có/không chi trả. Không dùng AI để lấp phần nguồn thiếu. Bản hiện tại dùng nhận biết có giới hạn và mẫu câu gắn nguồn; chưa phải mô hình hiểu ngôn ngữ hay bộ điều kiện toàn diện.

Phần trăm là tỷ lệ trong nhánh nguồn, không phải số tiền quỹ chi trả hoặc mức hưởng cá nhân. Quy tắc chuyển tiếp không tự lấy tỷ lệ hiện tại thay tỷ lệ lịch sử. Ngày nguồn và giới hạn thẩm định vẫn hiển thị.

## Kiểm tra

137 kiểm thử backend đạt, gồm 21 ca mới cho luồng hội thoại/HTTP. Kiểm tra câu hỏi không có dữ kiện bệnh nhân, câu hỏi tiếp với từ “còn/nếu”, đổi bệnh, HER2/EGFR âm tính, các thể ung thư phổi, đường dùng không khớp, thuốc mới, bệnh chưa có quy tắc, nguồn thiếu, chuyển tiếp và không gọi API ngoài.

67 kiểm tra trình duyệt đạt ở 1440×900, 768×1024 và 390×844: chỉ một ô nhập, Enter/Shift+Enter, Tab, focus không bị khung soạn che, câu trả lời theo bệnh, ngữ cảnh hỏi tiếp, copy kèm nguồn, lưu hội thoại trong phiên, Chat mới, thư viện nguồn, reduced motion và không tràn ngang. Đã xem ảnh thật ở cả ba kích thước; không kiểm tra thiết bị vật lý hoặc đọc màn hình bằng âm thanh.

Inspector mặc định: 0 FAIL / 1 WARN `unused-canvas`. Khung chat 840px căn giữa có hai lề bằng nhau; heuristic nhận thanh điều hướng ngang là sidebar. Giữ khung đọc này theo yêu cầu chỉ một chatbot, không kéo hội thoại thành nhiều cột để triệt cảnh báo. Bản đo và ảnh: `.taste-skill/inspect-v1.8/`; ảnh tương tác: `.taste-skill/chat-v1.8/`.

Bản sao trước thay đổi: `D:/Vinmec/backups/before-chat-only-v1.8-2026-11-07.zip`. Chạy tại http://127.0.0.1:8766/?v=1.8#lookup. Không triển khai hoặc đẩy GitHub trong bước này.
