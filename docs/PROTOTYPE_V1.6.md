# Prototype đối chiếu ca bệnh v1.6
Ngày: 07/11/2026. Thư mục chạy: D:/Vinmec/bhyt-chatbot. Địa chỉ: http://127.0.0.1:8766.

## Dùng thử nhanh
- Mở trang, chọn “Trastuzumab · thiếu HER2”. Kết quả phải nêu HER2 chưa có thông tin và chưa hiển thị tỷ lệ.
- Chọn HER2 dương tính rồi đối chiếu lại. Bảng chỉ ra dữ kiện chọn khớp nhánh ghi chú; nhãn và cơ sở vẫn cần xác minh.
- Đổi sang chỉ định dạ dày: phải bổ sung mức độ tiến xa/di căn; không giữ tỷ lệ của nhánh vú.
- Thử Paclitaxel dạng liposome: thấy ghi chú theo dạng và phần chuyển tiếp cần xem lại.
- Thử Metformin: xem ghi chú/quy định chung và các nguồn còn thiếu, không tự suy ra 100% từ ô trống.
- Có thể tự tìm bất kỳ hoạt chất trong bộ dữ liệu và nhập bối cảnh khác; chọn đúng dòng thuốc nếu có nhiều đường dùng.

## Phạm vi nghiệp vụ
Đối chiếu theo dữ kiện có cấu trúc, từng thuốc độc lập, mỗi điều kiện có nguồn bên cạnh. Nhận dạng sản phẩm mới ở mức thông tin người dùng nhập; chưa có cơ sở xác minh nhãn theo sản phẩm. Văn bản tự do được giữ nguyên làm bối cảnh, không tự phân tích hoặc suy luận chẩn đoán từ đó.

Năm bảng sơ bộ được gắn với record_id và SHA-256 ghi chú nguồn. Nếu ghi chú nguồn thay đổi, bảng cũ bị từ chối để tránh áp dụng nhầm. Nguồn gốc: dữ liệu danh mục hiện có của bộ snapshot 06/11/2026; không phải thu thập mới hoặc xác nhận pháp luật hiện hành đầy đủ.

Trạng thái điều kiện gồm: khớp dữ kiện nhập, chưa khớp ghi chú, chưa có thông tin, cần xác minh, đã ghi nhận. Kết quả ca luôn requires_review; payment_eligibility luôn null. Tỷ lệ nhánh nguồn chỉ hiện khi các lựa chọn tương ứng đầy đủ/khớp. Không dùng trường này làm mức hưởng cá nhân hay số tiền thanh toán.

## Những nguồn còn thiếu
- Nhãn/tờ hướng dẫn đăng ký đã xác minh của từng sản phẩm.
- Hướng dẫn chẩn đoán và điều trị gắn đúng chỉ định.
- Mục thuốc trong Dược thư Quốc gia.
- Danh mục/hợp đồng và phạm vi nội bộ bệnh viện.
- Bộ tình huống và bảng điều kiện được Dược/BHYT duyệt.
- Tỷ lệ lịch sử TT40/2014 cho nhánh chuyển tiếp liên quan.

Các ví dụ “thuốc bổ gan”, “bộ ba âm tính” trong ghi âm không được đưa thành luật chi trả. Không tạo biệt dược từ phần tên nghe chưa rõ. Ba ca minh họa của giao diện có nhãn giả lập rõ ràng.

## Thay đổi chính
- case_workbench.py + data/case_profiles.json: dữ kiện, bảng đối chiếu và gắn nguồn.
- GET /api/case/drugs, GET /api/case/schema, POST /api/case/evaluate.
- web/case.js và màn hình Ca bệnh: tìm thuốc, dữ kiện động theo chỉ định, bảng căn cứ, nguồn còn thiếu và sao chép.
- Sửa lỗi hỏi tiếp nhiều thuốc, bối cảnh cùng thuốc và đường tiêm; bản sao kết quả giữ cảnh báo.
- AI không được dùng ở API ca bệnh. Phần diễn giải cũ từ chối tỷ lệ/kết luận thanh toán bằng văn bản tự do; không tuyên bố đây là bộ kiểm chứng y khoa hoàn chỉnh.
- Ba tệp JSONL gốc giữ nguyên. Không đổi số thuốc hoặc mốc snapshot.

## Kiểm tra
105/105 kiểm thử backend đạt, gồm API, luồng ca, chuyển tiếp, nguồn, dữ liệu gốc, quyền truy cập và các lỗi review.
43 kiểm tra trình duyệt đạt ở 1440×900, 768×1024, 390×844: bàn phím, gợi ý, nhánh chỉ định, thiếu xét nghiệm, dữ kiện sửa làm kết quả cũ hết hiệu lực, sao chép, lỗi nhập liệu, giảm chuyển động và không tràn ngang.
Bộ đo hình ảnh: 0 FAIL, 0 WARN. Đã xem ảnh desktop/tablet/mobile và các trạng thái kết quả; không kiểm tra thiết bị vật lý hoặc âm thanh trình đọc màn hình.

Giữ thiết kế Achromatic ledger/Geist của dự án, không đổi thương hiệu. Bảng điều kiện và căn cứ là phần nhận diện riêng của màn hình. Trên máy tính dùng hai cột 460+24+716 trong 1200px; tablet/điện thoại xếp thành một cột. Không có ngoại lệ inspector được miễn.
Ảnh và hồ sơ kiểm tra nằm ở .taste-skill/ và được loại khỏi gói ứng dụng.

## Sao lưu
Bản trước thay đổi: D:/Vinmec/backups/prototype-before-v1.6-2026-11-07.zip.
Không bật OpenAI, không triển khai dịch vụ mạng, không đẩy GitHub trong bước này.
