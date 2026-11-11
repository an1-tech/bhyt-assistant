# Tình trạng dữ liệu ngày 11/11/2026

## Rà soát hiệu lực văn bản (tìm trên mạng ngày 11/11/2026)

| Câu hỏi | Kết quả | Nguồn |
|---|---|---|
| Có văn bản nào sửa danh mục dịch vụ kỹ thuật (xét nghiệm) sau Thông tư 39/2024 không? | Không tìm thấy. Thông tư 39/2024 vẫn được ghi "đang có hiệu lực". Thông tư 18/2025 được một trang liệt kê là văn bản sửa Thông tư 35/2016, nhưng nội dung là phân định thẩm quyền địa phương hai cấp, không sửa các dòng trong hai danh mục. | luatvietnam.vn, caselaw.vn, thuvienphapluat.vn |
| Có thông tư mới thay Thông tư 20/2022 về danh mục thuốc không? | Chưa ban hành. Bộ Y tế đang hoàn thiện dự thảo, dự kiến ban hành trong năm 2026 (báo Thanh Niên 02/07/2026; họp báo 01/10/2026). Dự thảo dự kiến thêm 84 thuốc và sửa điều kiện, tỷ lệ của 52 thuốc đang có. | thanhnien.vn, vietnamplus.vn, baohiemxahoi.gov.vn |
| Có hướng dẫn cách tính mốc "90 ± 3 ngày" của HbA1c không? | Không tìm thấy công văn nào của BHXH hay Bộ Y tế hướng dẫn riêng. Các bài tổng hợp chỉ nhắc mốc 90 ngày của Thông tư 13/2020; cụm "± 3" là của Thông tư 39/2024. | chinhsachonline.chinhphu.vn, baohiemxahoi.gov.vn |

Giới hạn của lượt tìm này:
- Chỉ tìm được trên các trang công khai; không mở được trang lịch sử hiệu lực của vbpl.vn và một số trang của thuvienphapluat.vn.
- Không tìm thấy không có nghĩa là không tồn tại. Bộ phận BHYT của bệnh viện là nơi xác nhận cuối cùng.

Hệ quả cho chatbot:
- Giữ nguyên bộ nguồn hiện tại.
- Vùng 87–93 ngày của HbA1c vẫn là "cần đối chiếu thêm".
- Khi thông tư mới về danh mục thuốc được ban hành, phải nạp lại toàn bộ danh mục thuốc và soát lại 18 thuốc ung bướu.

## Thông tin do nhóm cung cấp

- Danh sách thuốc công khai: 24 ảnh là toàn bộ; không có thuốc bắt đầu bằng J, Q, U, Y.
- Cơ sở: Hệ thống Y tế Vinmec, bệnh viện tư nhân, nhóm ghi nhận là tương đương hạng I. Lưu ở `data/hospital/facility.json` và hiện kèm câu "chưa có văn bản xếp hạng trong bộ nguồn" ở những thuốc có điều kiện về hạng bệnh viện. Các xếp hạng quốc tế (Newsweek, JCI) không phải căn cứ thanh toán BHYT nên không dùng.
- Bác sĩ xác nhận ô chat một câu hỏi là đúng nhu cầu.
- Thời gian tra cứu (nhóm cung cấp):
  - Cách hiện tại: mở tab mới, tìm tên thuốc và nguồn theo thông tư mới nhất, mỗi thuốc khoảng 5–10 phút.
  - Bằng chatbot: bấm giờ 10 lượt, trung bình khoảng 1 phút mỗi lượt.
  - Hai con số do nhóm tự đo; chưa có số liệu xuất toán của bệnh viện.

## Bộ ca thử giả lập

- `data/mock_cases.json`: 24 ca (12 thuốc, 12 xét nghiệm), phủ đủ 7 loại kết quả.
- Chạy bằng `python tools/run_mock_cases.py`; kết quả ở `audit/MOCK_CASES_RESULT.json` và `prototype/04-ca-thu-GIA-LAP.xlsx`.
- Kết quả hiện tại: 24/24 ca nhất quán với văn bản.
- Đây là ca giả lập. Kết quả mong đợi suy ra từ nguyên văn văn bản, nên con số này đo việc chatbot có làm đúng theo văn bản hay không, không đo độ chính xác so với quyết định thanh toán thật.

## Thẩm định của Dược/BHYT

- Nhóm dự án xác nhận bộ phận Dược/BHYT của bệnh viện đã thẩm định ngày 11/11/2026: 28 nhánh điều kiện của 18 thuốc ung bướu, 24 dòng xét nghiệm chép từ bản hợp nhất và 60 số trang PDF.
- Ghi ở `data/review_attestation.json`. Chatbot hiện đúng câu này, kèm "theo xác nhận của nhóm dự án; chưa lưu biên bản thẩm định và tên người duyệt trong bộ nguồn".
- Cần bổ sung khi có: tên người duyệt, đơn vị và biên bản. Khi đó sửa file trên và chạy lại `tools/build_lab_sources.py`.

## Việc còn chờ

- Tên người duyệt và biên bản thẩm định của Dược/BHYT.
- Danh mục xét nghiệm nội bộ của bệnh viện (tên gọi và mã dịch vụ).
- Văn bản xác nhận hạng tương đương của cơ sở.
