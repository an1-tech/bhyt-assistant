# Tra cứu xét nghiệm trong ô chat · v1.11

Câu hỏi của bác sĩ: “Xét nghiệm này, cho bệnh này, với mục đích này và ở thời điểm này, BHYT có thanh toán không?”

## Phạm vi

**41 dòng xét nghiệm có điều kiện thanh toán riêng**, là toàn bộ các dòng xét nghiệm trong hai danh mục của Thông tư 35/2016/TT-BYT đang áp dụng:

- 17 dòng đã được Thông tư 39/2024/TT-BYT sửa (hiệu lực 01/01/2025). Lấy từ lớp chữ của phụ lục TT39.
- 24 dòng TT39 không sửa. Các dòng này chỉ có trong bản hợp nhất 17/VBHN-BYT, là bản scan, nên được chép bằng cách đọc ảnh trang.

Bản đầu (10/11/2026) chỉ có HbA1c và EGFR. Khi đó HER2, KRAS, BRAF, CRP, Procalcitonin, HBV, HCV, SCC… nằm ngay trong cùng phụ lục nhưng chatbot trả lời “chưa có căn cứ”. Bản hoàn thiện (11/11/2026) nạp đủ.

Luồng thuốc không đổi. Không cần API key và không gọi mô hình ngoài.

### Chatbot tự đối chiếu ca bệnh đến đâu

| Nhóm | Dịch vụ | Chatbot làm gì |
|---|---|---|
| `hba1c` | Định lượng HbA1c | So mục đích, đã chẩn đoán xác định đái tháo đường hay chưa, và khoảng cách với lần trước. |
| `gene` | Đột biến gen EGFR, Her 2, BRAF, KRAS | So bệnh với phạm vi của dòng và mục đích “chẩn đoán đột biến gen trong điều trị”. |
| `scope` | Định lượng SCC | Chỉ so bệnh với danh sách của dòng. Mô bệnh học tế bào vảy và mục đích để người đọc đối chiếu. |
| không có luật | 35 dòng còn lại | Trích nguyên văn và nói rõ “chưa tự đối chiếu ca bệnh”. Không bao giờ kết luận “khớp”. |

Dòng chép từ bản scan không bao giờ có luật tự động, vì phần chữ chưa được máy kiểm lại.

## Nguồn

- [Phụ lục TT39/2024](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/11/39-byt-kem.pdf): Danh mục 1 và Danh mục 2. Bản công bố: [Cổng Chính phủ](https://vanban.chinhphu.vn/?docid=211771&pageid=27160).
- [17/VBHN-BYT](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/01/17-vbhn-byt.pdf): hợp nhất TT35/2016, TT50/2017, TT13/2020, TT39/2024. Lớp OCR của bản này không dùng được.
- [Nội dung TT39/2024](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/11/39-byt.pdf).

Tìm kiếm ngày 10/11/2026 chưa thấy văn bản sửa các dòng này sau TT39/2024. Trang lịch sử hiệu lực VBPL không truy cập được, nên không khẳng định đã rà soát mọi thay đổi. Chưa được Dược/BHYT bệnh viện thẩm định.

### Cách lấy dữ liệu (`tools/build_lab_sources.py`)

**Dòng TT39 (lớp chữ)**
- Công cụ đọc bảng trong PDF. Tên dịch vụ in trong PDF phải trùng tên khai trong công cụ, nếu không thì dừng.
- Điều kiện lấy thẳng từ ô của bảng. Chỉ nối các dòng bị ngắt do xuống hàng; các mục a), b), gạch đầu dòng giữ riêng.
- Dòng kéo sang trang sau được ghép lại. Mỗi đoạn được cắt thành một ảnh.
- Danh mục 1 có thêm cột “Tỷ lệ, mức giá thanh toán”, được lưu riêng trong `rate`.
- Hai dòng thí điểm (HbA1c, EGFR) vẫn so với bản đã gõ tay và kiểm bằng mắt.

**Dòng 17/VBHN-BYT (bản scan)**
- Phần chữ gõ trong công cụ, đọc từ ảnh trang (AI đọc), đánh dấu `scan_read`.
- Câu trả lời và trang nguồn luôn ghi “chép từ bản scan, chờ thẩm định” và hiện ảnh nguyên trang để so.
- Ở ba dòng Danh mục 1 (STT 8, 9, 13), mỗi điều kiện đi với ô tỷ lệ riêng (`rate_mode: paired`).

**Giữ nguyên văn**
- Lỗi in trong nguồn được giữ và ghi chú, ví dụ “viêm ban vi rút C”, “C.difficle”.
- STT trong phụ lục không phải mã thanh toán. `service_code` và `method` để null.

**Toàn vẹn**
- PDF và ảnh đều có SHA-256. Thiếu hoặc khác tệp thì chatbot dừng trả lời từ nguồn đó.

## Nhận diện câu hỏi

- Tên in trong nguồn và tên gọi tắt đều nhận được. Tên dài thắng tên nằm trong nó: “Pro-BNP” không bị hiểu thành “BNP”, “HIV kháng thuốc giải trình tự gene” không kéo theo dòng “giải trình tự gen” chung.
- Tên gần đúng có ghi chú phạm vi. Ví dụ “công thức máu” dẫn tới dòng “Tổng phân tích tế bào máu ngoại vi bằng hệ thống tự động hoàn toàn” kèm câu “không phải mọi xét nghiệm công thức máu”.
- **Dấu ấn là điều kiện của thuốc thì ở lại luồng thuốc.** “Trastuzumab ung thư vú HER2 dương tính” hay “Cetuximab … chưa có kết quả xét nghiệm KRAS” là câu hỏi về thuốc. Khi đã nêu tên thuốc, chỉ câu hỏi rõ về việc thanh toán xét nghiệm mới sang luồng xét nghiệm.
- **Giá trị xét nghiệm trong câu hỏi thuốc không phải yêu cầu chỉ định.** “Metformin đái tháo đường type 2 HbA1c 9%”, “HbA1c 8% thì dùng thuốc gì” đi luồng thuốc.
- Xét nghiệm không có trong 41 dòng (troponin, đường huyết…): trả lời “chưa thấy”, giải thích hai danh mục chỉ liệt kê dịch vụ có điều kiện riêng, và không mượn luật của dòng khác.
- Chẩn đoán hình ảnh, thủ thuật (PET/CT, siêu âm…): nói rõ chưa nạp và đưa liên kết hai tài liệu.
- eGFR mức lọc cầu thận được tách khỏi đột biến gen EGFR.

## Đọc dữ kiện ca bệnh

Chatbot chỉ hỏi dữ kiện còn thiếu, không cần thông tin định danh. Dữ kiện giữ trong trạng thái hội thoại có chữ ký, riêng từng dịch vụ; sang ca mới hoặc sang thuốc thì không thừa hưởng.

**HbA1c**
- Ngày: nhận “lần trước làm ngày 01/08/2026”, “cách 60 ngày”, “cách 6 tuần”.
- “2 tháng trước” được hiểu là 56–62 ngày. Chatbot chỉ kết luận khi cả khoảng nằm về một phía của mốc; “3 tháng trước” (84–93 ngày) thì hỏi ngày chính xác.
- “Ngày mai” không bị tính như hôm nay: ngày ở tương lai cần đối chiếu thêm.
- Chưa chẩn đoán xác định: “tiền đái tháo đường”, “nghi ngờ đái tháo đường”, “chưa có chẩn đoán”, “rối loạn dung nạp” đều không tính là đã chẩn đoán.
- Phủ định mục đích: “không phải để theo dõi mà để chẩn đoán” là mục đích chẩn đoán.
- Vùng 87–93 ngày: giữ nguyên “90 ± 3”, chuyển sang cần đối chiếu cách áp dụng sai số, không tự chốt. Đây là giới hạn tự động hóa, không phải điều kiện pháp luật thêm vào.
- Lần đầu để đánh giá điều trị: cần đối chiếu thêm, không áp máy móc “từ lần thứ 2”.

**Xét nghiệm gen**
- “Không phải ung thư vú mà là ung thư dạ dày” được hiểu là ung thư dạ dày.
- “Nghi ngờ…”, “chưa xác định…” hoặc nêu nhiều bệnh không cùng phạm vi: hỏi lại.
- Dòng nêu nhiều bệnh (Her 2, BRAF) thì trả lời “Có” không đủ để xác định bệnh.
- Hỏi về phương pháp (NGS, PCR, FISH, hóa mô miễn dịch), bệnh phẩm, số lần làm lại, giá: dòng nguồn không nêu, nên trả “cần đối chiếu thêm”.

## Hiển thị

- Mỗi xét nghiệm có khối “Nguyên văn điều kiện trong nguồn”. Nhánh đang đối chiếu được tô đậm theo vị trí trong dữ liệu, không gõ lại.
- Dòng Danh mục 1 hiện thêm “Tỷ lệ, mức giá thanh toán (nguyên văn)”.
- “Xem vị trí trích dẫn” mở ảnh cắt trọn dòng (TT39) hoặc ảnh nguyên trang (bản scan), kèm bản chữ và liên kết PDF đúng trang.
- Tab “Nguồn dữ liệu” có danh sách 41 xét nghiệm và hai tài liệu.

## Giới hạn

- 24 dòng bản scan do AI đọc ảnh, cần Dược/BHYT soát lại từng dòng.
- Chỉ 6 dịch vụ có đối chiếu ca bệnh; 35 dòng còn lại chỉ trích nguyên văn.
- Chưa nạp các dòng không phải xét nghiệm (chẩn đoán hình ảnh, thăm dò chức năng, thủ thuật, phục hồi chức năng) của cùng hai danh mục.
- Mô-đun hiểu các mẫu tiếng Việt đã kiểm thử, không bảo đảm hiểu mọi cách diễn đạt.
- Chưa tích hợp HIS/LIS, lịch sử người bệnh, hợp đồng, giá hay mã dịch vụ của bệnh viện. “Khớp điều kiện trong nguồn” không phải quyết định thanh toán.
- Trường `as_of` của API vẫn theo ngày chốt nguồn thuốc. Nguồn xét nghiệm có ngày kiểm tra riêng.

## Tệp và vận hành

- `lab_lookup.py`: nhận diện, dữ kiện theo lượt, đối chiếu, trang nguồn.
- `engine.py`: gọi mô-đun sau khi kiểm tra dữ liệu định danh và chữ ký trạng thái; ghép hai phần khi hỏi cả thuốc lẫn xét nghiệm.
- `server.py`: chỉ phục vụ các PDF và ảnh có tên trong `data/lab_services.json`.
- `tools/build_lab_sources.py`: cần pdfplumber; ứng dụng chạy chỉ dùng thư viện chuẩn. Thay nguồn thì chạy lại công cụ và soát lại ảnh.
- `tests/test_lab_lookup.py` (37 kiểm thử của bản đầu) và `tests/test_lab_catalogue.py` (30 kiểm thử của bản hoàn thiện).
- `tools/check-lab-ui.mjs`: kiểm tra trên trình duyệt ở ba cỡ màn hình 1440/768/390.

Kết quả kiểm thử: `audit/LAB_V1.11_VALIDATION.json`.

## Soát lại ngày 11/11/2026

- 24 dòng chép từ bản scan đã được một lượt đọc độc lập thứ hai (cũng do AI) so từng chữ với ảnh trang phóng to: không có khác biệt. Vẫn cần Dược/BHYT thẩm định.
- Lượt đọc này cũng xác nhận không sót dòng xét nghiệm nào ở các trang 26–28 và 44–50. Dòng STT 81 (thu thập, chiết tách tế bào gốc) là dịch vụ xử lý tế bào, không phải xét nghiệm, nên không nạp.
- Quét 1.071 tên hoạt chất của danh mục thuốc qua bộ nhận diện xét nghiệm: không tên nào bị chuyển nhầm sang luồng xét nghiệm.
