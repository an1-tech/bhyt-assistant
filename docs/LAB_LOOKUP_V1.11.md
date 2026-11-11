# Tra cứu xét nghiệm trong ô chat · v1.11

## Phạm vi

Bổ sung hai dịch vụ: định lượng HbA1c [Máu] và xét nghiệm đột biến gen EGFR. Luồng thuốc hiện có vẫn được dùng cho câu hỏi như “Chưa có kết quả EGFR thì Erlotinib có được thanh toán không?”. Câu hỏi cả xét nghiệm và thuốc có hai phần và hai căn cứ độc lập. Không cần API key; không gọi mô hình ngoài để đưa ra kết luận.

Hỏi điều kiện chung được trả ngay. Khi hỏi đối chiếu một lần xét nghiệm cụ thể, chatbot hỏi theo dữ kiện còn thiếu: mục đích, bệnh liên quan hoặc ngày xét nghiệm gần nhất. Không cần thông tin định danh. Ngày tương đối được đổi thành ngày tuyệt đối tại lượt nhập, theo múi giờ UTC+7. Dữ kiện được giữ trong trạng thái hội thoại có chữ ký, riêng từng dịch vụ; câu hỏi ca mới hoặc đổi sang thuốc không thừa hưởng ngày của ca cũ.

## Nguồn và cách chia dữ liệu

- [Bản công bố TT39/2024/TT-BYT trên Cổng Chính phủ](https://vanban.chinhphu.vn/?docid=211771&pageid=27160): ngày ban hành 17/11/2024, có hiệu lực 01/01/2025.
- [Phụ lục chính thức](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/11/39-byt-kem.pdf): Danh mục 2, HbA1c STT 38 (STT 84 theo TT35), trang PDF 20; EGFR STT 43 (STT 98), trang PDF 21.
- [Nội dung thông tư](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/11/39-byt.pdf).
- [17/VBHN-BYT, bản hợp nhất lưu tại Cổng Chính phủ](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/01/17-vbhn-byt.pdf): chuỗi TT35/2016, TT50/2017, TT13/2020, TT39/2024; đối chiếu ảnh HbA1c trang 47–48, EGFR trang 50. OCR bản hợp nhất kém nên không lấy OCR đó làm quy tắc.

Tìm kiếm nguồn ngày 10/11/2026 chưa tìm thấy văn bản sửa hai dòng này sau TT39/2024. Kết quả VBPL được lập chỉ mục thể hiện TT39 còn hiệu lực, nhưng trang lịch sử/thuộc tính trực tiếp bị chặn/không truy cập được. Ngày kiểm tra không chứng minh đã rà soát mọi thay đổi mới nhất. Chưa được bộ phận Dược/BHYT bệnh viện thẩm định.

`data/lab_services.json` lưu tên chính thức, tên gọi tắt, bệnh/mục đích theo nhánh, điều kiện thời gian, nguyên văn, trang/dòng/vùng ảnh, nguồn và ngày hiệu lực. Mỗi **dòng dịch vụ trọn vẹn là một chunk**, giữ tất cả ngoại lệ cùng điều kiện; không chia cố định theo số ký tự và không trộn vào các đoạn điều kiện thuốc. Tra tên dịch vụ xác định rồi đối chiếu quy tắc, không dùng tìm kiếm gần đúng để tự xác nhận một dịch vụ khác.

STT trong phụ lục không phải mã thanh toán. `service_code` và `method` để null khi dòng nguồn không nêu; không tự điền mã nội bộ hoặc phương pháp xét nghiệm. Bản PDF và ảnh cắt dòng có SHA-256; thiếu/thay nguồn thì dừng trả lời từ nguồn đó. Công cụ xây dựng kiểm tra nguyên văn ô điều kiện khớp hoàn toàn với dữ liệu nhập, chỉ chuẩn hóa xuống dòng/khoảng trắng.

## Các giới hạn có chủ đích

- HbA1c giữ nguyên “90 ± 3 ngày”. Prototype chuyển **toàn vùng 87–93 ngày** sang cần đối chiếu cách áp dụng sai số, không tự chốt đạt/không đạt. Đây là giới hạn tự động hóa, không phải thêm điều kiện pháp luật. Dưới 87 ngày: chưa khớp thời gian nhánh thường; trên 93 ngày: khớp phần thời gian nếu các điều kiện khác đã nêu phù hợp. Nhánh thai kỳ có insulin đối chiếu mốc 30 ngày riêng.
- Không coi mọi HbA1c là theo dõi điều trị: sàng lọc/chẩn đoán ban đầu không tự áp nhánh xác định phác đồ/đánh giá điều trị. Lần đầu để đánh giá điều trị được yêu cầu đối chiếu thêm, không áp máy móc điều kiện “từ lần thứ 2”.
- EGFR phải tách xét nghiệm đột biến gen với eGFR mức lọc cầu thận. Không tự áp quy định cho panel NGS, bệnh phẩm/phương pháp, giá/tỷ lệ hoặc số lần làm lại không nêu trong dòng nguồn. Kết quả EGFR dương tính không phải điều kiện được tự thêm cho thanh toán chính xét nghiệm EGFR.
- Câu hỏi đồng thời nhiều xét nghiệm trả điều kiện chung riêng từng dịch vụ, không gán một ngày/mục đích cho cả hai. Câu hỏi phương pháp hoặc dữ kiện chưa nhận diện rõ cần đối chiếu thêm.
- Mô-đun hiểu các mẫu tiếng Việt đã kiểm thử, không bảo đảm hiểu mọi cách diễn đạt. Chưa tích hợp HIS/LIS, lịch sử bệnh nhân, hợp đồng hoặc giá/mã dịch vụ của bệnh viện. “Khớp điều kiện trong nguồn” không phải quyết định quyền lợi hoặc thanh toán cá nhân.
- Trường `as_of` của API vẫn giữ hợp đồng snapshot thuốc cũ; mô-đun xét nghiệm không tự nhận có đầy đủ lịch sử pháp lý ở ngày bất kỳ. Nguồn xét nghiệm công bố ngày kiểm tra riêng, không thay ngày snapshot thuốc.

## Tệp và vận hành

- `lab_lookup.py`: nhận diện ý hỏi, quản lý dữ kiện theo lượt, đối chiếu và hiển thị nguồn.
- `engine.py`: gọi mô-đun sau kiểm tra dữ liệu định danh và chữ ký trạng thái; kết hợp hai nhánh khi hỏi cả thuốc lẫn xét nghiệm.
- `server.py`, `catalog.py`, `web/`: nguồn riêng, metadata, câu trả lời và ví dụ trong chat.
- `tools/build_lab_sources.py`: công cụ build cần pdfplumber; ứng dụng chạy chỉ dùng thư viện chuẩn Python. Thay nguồn cần chạy lại công cụ và đối chiếu ảnh, không chỉ đổi văn bản JSON.
- `tests/test_lab_lookup.py`: quy tắc, biên ngày, phủ định, đổi chủ đề, trạng thái giả mạo, yêu cầu đồng thời, lỗi nguồn, endpoint.
- `tools/check-lab-ui.mjs`: kiểm tra trong trình duyệt, ba kích thước 1440/768/390, bàn phím, giảm chuyển động và nguồn.

Kiểm thử cuối cùng được lưu ở `audit/LAB_V1.11_VALIDATION.json`. Bộ kiểm tra backend gồm cả kiểm thử thuốc hiện có; kiểm tra trình duyệt chạy tương tác thực qua ô chat và mở nguồn bằng Enter. Inspector trước/sau đều không có lỗi đo được; một cảnh báo unused-canvas có từ bản cũ do cột chat 840px cố ý căn giữa.
