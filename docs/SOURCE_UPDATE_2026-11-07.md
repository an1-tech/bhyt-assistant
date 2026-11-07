# Bổ sung nguồn prototype v1.7 — kiểm tra ngày 07/11/2026

Đã lưu 6 PDF / 204 trang thuộc bốn chủ đề. 99 bản ghi trang của hướng dẫn ung thư vú và dạ dày đủ để dẫn trích đoạn tham khảo; 105 trang còn lại chỉ lưu để kiểm tra và dẫn mở PDF. Chưa phủ đủ nguồn toàn viện, nhãn sản phẩm hay Dược thư.

## Tài liệu và trạng thái

| Tài liệu | Ngày ban hành theo quyết định/trang công bố | Số trang PDF | Trạng thái |
|---|---|---:|---|
| [3128/QĐ-BYT — Hướng dẫn chẩn đoán và điều trị ung thư vú](https://kcb.vn/upload/2005611/20210723/3128_QD-BYT_Huong-dan-chan-doan-va-dieu-tri-ung-thu-vu.pdf) | 2020-07-17 | 60 | Có trích đoạn tham khảo, không tự xét điều kiện |
| [3127/QĐ-BYT — Hướng dẫn chẩn đoán và điều trị ung thư dạ dày](https://benhvienquynhon.gov.vn/wp-content/uploads/2023/05/copy-of-21-qd.3127.pdf) | 2020-07-17 | 39 | Có trích đoạn tham khảo, không tự xét điều kiện |
| [4825/QĐ-BYT — Hướng dẫn chẩn đoán và điều trị ung thư phổi không tế bào nhỏ](https://syt.dongnai.gov.vn/vi/van-ban/detail/V-v-trien-khai-Quyet-dinh-so-4825-QD-BYT-ngay-06-8-2018-cua-Bo-Y-te-ve-viec-ban-hanh-tai-lieu-chuye-1527/?download=1&id=0) | 2018-08-06 | 25 | Chỉ mở PDF; không suy luận từ OCR/sơ đồ |
| [1248/QĐ-BYT — Sửa đổi sơ đồ xét nghiệm T790M của hướng dẫn ung thư phổi](https://benhvienhatrung.vn/wp-content/uploads/2022/06/1248-2019-sua-doi-4825-ung-thu-phoi-te-bao-nho.pdf) | 2019-04-04 | 2 | Chỉ mở PDF; không suy luận từ OCR/sơ đồ |
| [5481/QĐ-BYT — Hướng dẫn chẩn đoán và điều trị đái tháo đường típ 2](https://syt.dongnai.gov.vn/vi/van-ban/detail/V-v-trien-khai-thuc-hien-Quyet-dinh-so-5481-QD-BYT-ngay-30-12-2020-cua-Bo-truong-Bo-Y-te-4905/?download=1&id=0) | 2020-12-30 | 77 | Chờ xác minh bản ký; chưa dùng nội dung đối chiếu |
| [1353/QĐ-BYT — Sửa đổi hướng dẫn chẩn đoán và điều trị đái tháo đường típ 2](https://syt.gialai.gov.vn/vi/van-ban-chi-dao-dieu-hanh/detail/Quyet-dinh-so-1353-QD-BYT-23-02-2021-cua-Bo-Y-te-Ve-viec-sua-doi-bo-sung-mot-so-noi-dung-cua-Huong-dan-chan-doan-va-dieu-tri-dai-thao-duong-tip-2-1188/?download=1&id=0) | 2021-02-23 | 1 | Chờ xác minh bản ký; chưa dùng nội dung đối chiếu |

Số/ngày của 5481 và 1353 được tra từ trang công bố của Cục KCB/Sở Y tế; bản PDF tải được còn trống các trường này, đã kiểm tra bằng ảnh trang đầu. Không tự điền số/ngày vào PDF hay coi tên tệp có chữ signed là chứng minh bản ký. 4825/2018 được lưu cùng công văn triển khai của Sở Y tế; quyết định Bộ Y tế ở trang PDF 2. QĐ 1248 ngày 04/04/2019 là sửa đổi sơ đồ T790M, không phải hướng dẫn thay thế toàn bộ.

## Cách nhập và truy xuất

- Giữ nguyên PDF, ghi URL tải, cơ quan đăng, ngày kiểm tra, SHA-256 và giới hạn từng tài liệu trong data/supplemental_sources.json. Bản ghi trang có hash lớp chữ gốc; các bản trích xuất thô được lưu tại audit/extracted-*.json.
- Chia theo trang PDF, không cắt tùy tiện mỗi N token. Lưu 204 bản ghi trang; chỉ 99 trang thuộc hai tài liệu reference_only được cấp quyền trích đoạn. Chuẩn hóa hai ký tự do font ƣ → ư và Ƣ → Ư, có dấu vết trong từng bản ghi; không tự sửa số, liều hoặc bảng.
- Truy xuất theo các cụm trang gắn rõ hoạt chất/chủ đề trong registry, giữ trang liền kề đã chọn để đọc ngữ cảnh; không tuyên bố là semantic chunking hoặc đã tạo embedding. Đây là tra cứu theo trang và liên kết định trước cho prototype.
- Chỉ định ung thư vú và dạ dày của Trastuzumab dẫn hai bộ nguồn khác nhau. Thuốc chưa có trường chỉ định dùng bộ chọn “Hướng dẫn cần tham khảo”; trường này không tự xác nhận chẩn đoán.
- Bản scan/sơ đồ chỉ sinh chỉ dẫn mở PDF; bản còn trống số/ngày chỉ sinh chỉ dẫn chờ xác minh. QĐ 1248 luôn đi kèm 4825, QĐ 1353 luôn đi kèm 5481. Không dùng lớp chữ hỏng để suy ra quy tắc.
- Kho này tách khỏi chỉ mục BHYT, vector/AI context và tỷ lệ thanh toán. Bộ nguồn BHYT gốc, 1037/59 STT và 1246 đoạn hiệu dụng không đổi. Chưa thêm quy tắc BHYT mới từ dự thảo 2026.
- Tệp PDF mới chỉ được server phục vụ theo danh sách cho phép. Khởi động kiểm tra SHA-256 PDF/lớp chữ, đường dẫn và đủ chuỗi sửa đổi; không khởi động nếu sai hash.

## Cách xem

Mở http://127.0.0.1:8766/#sources để xem sáu tài liệu mới và bản lưu. Trong Ca bệnh, chọn Trastuzumab rồi chọn ung thư vú hoặc dạ dày; phần Hướng dẫn Bộ Y tế có căn cứ theo trang. Với Metformin, chọn hướng dẫn đái tháo đường típ 2 để thấy trạng thái chờ xác minh bản ký và cả văn bản sửa đổi. Nhãn và Dược thư vẫn báo thiếu đúng thực trạng.

## Giới hạn và lần cập nhật sau

Ngày kiểm tra 07/11/2026 không phải ngày ban hành và không chứng minh đã tìm hết mọi bản thay thế. Chưa có nhãn Việt Nam đúng sản phẩm/hàm lượng/dạng bào chế đã kiểm chứng, toàn văn chuyên luận Dược thư chính thức, danh mục nội bộ/hợp đồng BHYT hay bản thẩm định Dược/BHYT của bệnh viện. Không suy ra chỉ định hoặc điều kiện thanh toán từ bản đăng ký thuốc, tên biệt dược nhập tay, ghi âm hay tài liệu quảng cáo.

Khi bổ sung hoặc thay nguồn: kiểm tra quyết định ban hành và chuỗi sửa đổi; lưu bản mới với định danh riêng; kiểm tra ảnh các bảng/sơ đồ; cập nhật trạng thái và các trang liên quan; kiểm thử việc dẫn đúng chỉ định, đường dùng và phạm vi. Không tự kích hoạt tài liệu chỉ vì có năm mới hơn. Nhật ký tìm kiếm và tài liệu bị loại: audit/SOURCE_SEARCH_2026-11-07.json.

## Kiểm tra

- 116 kiểm thử backend đạt, gồm 11 kiểm thử mới về nguồn, hash, chỉ định, bản scan/bản chưa ký, sửa đổi và đường dẫn PDF. Lần đầu một kết nối localhost bị Windows ngắt; lần chạy lại đầy đủ đạt.
- 43 kiểm tra trình duyệt luồng ca bệnh và 36 kiểm tra giao diện nguồn đạt ở 1440/768/390px; kiểm tra keyboard và reduced motion trong bộ ca bệnh.
- Đã xem ảnh trang nguồn, căn cứ ca bệnh và trang PDF mẫu. Bộ đo giao diện mặc định: 0 FAIL / 0 WARN. Không coi việc kiểm tra phần mềm là thẩm định lâm sàng hoặc pháp lý.
