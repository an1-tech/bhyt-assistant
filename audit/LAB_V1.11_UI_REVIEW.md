# Kiểm tra giao diện xét nghiệm · 10/11/2026

Giữ thiết kế Achromatic ledger và bố cục chat hiện có. Câu hỏi chính: thuốc hoặc xét nghiệm này có điều kiện BHYT gì? Điểm nhận diện là câu trả lời gắn ngay dòng nguồn, không thêm biểu mẫu bệnh nhân.

Đã xem ảnh màn hình desktop, tablet, mobile của trang chat, câu trả lời HbA1c, câu trả lời cả EGFR và Erlotinib, trang trích nguồn. Các ảnh kiểm tra nằm ở audit/lab-browser. Ảnh ghép toàn trang của inspector là các mảnh cuộn; phần xám bên ngoài là nền ghép ảnh, không phải giao diện. Bộ nguồn mới có đúng hai dịch vụ; câu hỏi kiểm tra là dữ liệu tình huống giả định.

- Bố cục: cột chat căn giữa, cùng lề; giữ thanh điều hướng và ô nhập. Nút mở nguồn xuất hiện sát định vị trang/dòng.
- Chữ: Geist hiện có, nội dung nguồn đọc được dạng chữ. Ảnh gốc được giữ đúng tỷ lệ, có bản chữ mở bằng bàn phím và PDF toàn trang.
- Tương tác: Enter gửi câu hỏi; Enter mở nguồn ở tab riêng; hỏi tiếp giữ đúng dịch vụ; Chat mới xóa bối cảnh; reduced-motion được tôn trọng. 75 kiểm tra tự động qua trình duyệt đều đạt.
- Trung thực dữ liệu: ba nhánh HbA1c giữ đầy đủ; xét nghiệm và thuốc có nguồn riêng; tình trạng chờ bệnh viện thẩm định hiện cạnh nguồn.
- Trước/sau: inspector đều 0 FAIL, 1 WARN. Cảnh báo unused-canvas là giả định sidebar của bộ đo, trong khi sản phẩm dùng chat 840px căn giữa theo DESIGN.md.

Đánh giá nội bộ: thiết kế 7.5/10; khả dụng 8/10; tính riêng 7/10; nội dung 8/10 (điểm có trọng số 7.6/10). Hạn chế còn lại: câu trả lời pháp lý dài trên điện thoại; ảnh tài liệu thu nhỏ cần mở bản chữ/PDF để đọc thoải mái; nội dung cần thẩm định nghiệp vụ. Không thêm hình trang trí hoặc chuyển động vì không phục vụ tra cứu.
