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
- Phần chữ gõ trong công cụ, đọc từ ảnh trang (Đỗ Quốc An đọc), đánh dấu `scan_read`.
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

- 24 dòng bản scan do Đỗ Quốc An đọc ảnh, cần Dược/BHYT soát lại từng dòng.
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

- 24 dòng chép từ bản scan đã được Đỗ Quốc An đọc lại lần thứ hai, so từng chữ với ảnh trang phóng to: không có khác biệt. Vẫn cần Dược/BHYT thẩm định.
- Lượt đọc này cũng xác nhận không sót dòng xét nghiệm nào ở các trang 26–28 và 44–50. Dòng STT 81 (thu thập, chiết tách tế bào gốc) là dịch vụ xử lý tế bào, không phải xét nghiệm, nên không nạp.
- Quét 1.071 tên hoạt chất của danh mục thuốc qua bộ nhận diện xét nghiệm: không tên nào bị chuyển nhầm sang luồng xét nghiệm.

## Rà soát bên ngoài ngày 11/11/2026: 8 lỗi, đều xác nhận và đã sửa

Cả 8 điểm trong bản nhận xét đều tái hiện được. Ba lỗi đầu chung một nguyên nhân: phủ định và nghi ngờ được đọc theo từng cụm từ gõ sẵn, nên cụm nào chưa liệt kê thì bị hiểu ngược.

**Cách đọc mới (dùng cho mọi dữ kiện)**
- Câu hỏi được tách thành các vế. Mỗi từ khóa (insulin, lần đầu, tên bệnh, điều trị…) được xét trong vế của nó.
- “Không”: có từ phủ định chi phối từ khóa, ở giữa chỉ có từ đệm. Ví dụ “không còn dùng insulin”, “chưa có chỉ định dùng insulin”, “insulin nay đã ngưng”.
- “Chưa rõ”: dự kiến, có thể, câu hỏi, phủ định kép (“chưa loại trừ”, “không phải không”), hoặc phủ định ở gần nhưng không chắc chi phối. Trường hợp này chatbot hỏi lại, không đoán.
- “Có”: các trường hợp còn lại.
- “Không” nằm trong tên bệnh (“ung thư phổi không tế bào nhỏ”) không tính là phủ định.
- “Dừng” và “dùng” được phân biệt bằng dấu. Gõ không dấu “da dung insulin” thì hỏi lại.

**Từng lỗi**

| # | Lỗi | Sau khi sửa |
|---|---|---|
| 1 | “Không còn dùng insulin” bị hiểu là đang dùng | Hiểu là không dùng; “dự kiến dùng”, “có thể sẽ dùng” thì hỏi lại |
| 2 | “Không phải lần đầu” bị hiểu là lần đầu | Hiểu là đã có lần trước và hỏi ngày lần trước |
| 3 | Xét nghiệm gen: “chưa có chẩn đoán…”, “chưa loại trừ…”, “không nhằm chẩn đoán đột biến…” | Bệnh chưa xác định thì hỏi lại; mục đích bị phủ định thì không khớp; “chưa điều trị” thì hỏi mục đích |
| 4 | Nhắc “suy thận” làm câu hỏi đột biến gen EGFR chuyển sang eGFR thận | Có “đột biến/gen” hoặc có tên ung thư thì vẫn là xét nghiệm gen; chỉ “eGFR” kèm ung thư và bệnh thận mới hỏi lại |
| 5 | Trả lời câu hỏi bổ sung của bot bằng “Xét nghiệm để…” thì mất ngữ cảnh | Giữ xét nghiệm đang bàn; nêu tên xét nghiệm khác thì chuyển sang xét nghiệm đó |
| 6 | “Cả xét nghiệm HER2 và Trastuzumab” chỉ trả phần xét nghiệm | Thuốc và xét nghiệm nối bằng “và/cùng/lẫn” đều được trả, với bất kỳ thuốc nào |
| 7 | “HLA bằng NGS”, “HLA-B27” dẫn tới hai dòng PCR-SSP/PCR-SSO mà không nói rõ | Hai dòng ghi chú phạm vi kỹ thuật; nêu kỹ thuật khác thì trả “khác với dòng này, chưa có căn cứ” |
| 8 | Một ảnh nguồn hỏng làm ngừng cả phần xét nghiệm | Chỉ dòng dùng tệp hỏng bị dừng; server kiểm từng ảnh |

**Kiểm thử**
- `tests/test_lab_review6.py`: 21 kiểm thử hồi quy.
- Tổng cộng 381 kiểm thử backend, 111 và 67 kiểm tra giao diện đều đạt.
- Quét lại 1.071 tên thuốc: không tên nào bị chuyển nhầm sang xét nghiệm.

**Giới hạn còn lại (bản nhận xét nêu đúng)**
- Chat chạy bằng quy tắc và mẫu câu, không gọi mô hình ngôn ngữ. Cách đọc mới thu hẹp lỗi phủ định nhưng không bảo đảm hiểu mọi cách diễn đạt; khi không chắc thì chatbot hỏi lại.
- 24 dòng bản scan mở ảnh nguyên trang, chưa đánh dấu đúng dòng.
- Phần thuốc chỉ có số trang đã kiểm cho 60 dòng; các dòng khác mở PDF từ đầu.

## Rà soát bên ngoài lần 2 ngày 11/11/2026: thêm 8 lỗi, đổi nguyên tắc kết luận

Cả 8 điểm của lần rà soát thứ hai đều tái hiện được và đã sửa. Tự thử thêm 73 cách diễn đạt khác còn thấy 16 câu sai (“từ chối insulin”, “mẹ bệnh nhân bị đái tháo đường”, “kết quả bị hủy”…). Kết luận rút ra: đọc theo mẫu câu thì không bao giờ hết trường hợp sót, nên đổi nguyên tắc.

**Nguyên tắc mới**
- Chatbot chỉ kết luận “khớp” hoặc “không khớp” thẳng từ câu hỏi khi mọi từ trong câu đều thuộc danh sách từ đã biết (`ACCOUNTED` trong `lab_lookup.py`) và câu không có từ thể hiện sự chưa chắc.
- Nếu còn từ chưa hiểu chắc, chatbot nêu rõ các từ đó, trình bày “Chatbot hiểu dữ kiện như sau” và chờ bác sĩ bấm “Đúng, đối chiếu theo các dữ kiện này”. Bấm xong mới có kết luận, mở đầu bằng “Theo các dữ kiện bạn vừa xác nhận”.
- Nếu cách hiểu sai, bác sĩ gõ lại dữ kiện cần sửa thay vì bấm xác nhận.
- Lượt xác nhận không đọc lại câu chữ nào. Dữ kiện nằm trong trạng thái có chữ ký nên không sửa được từ trình duyệt.
- Danh sách từ đã biết giữ dấu tiếng Việt, để “hội” (hội chẩn) không bị coi là “hỏi”. Gõ không dấu thì so theo dạng không dấu.
- Phần “Chatbot hiểu dữ kiện như sau” hiện ở mọi câu trả lời có đối chiếu ca bệnh, kể cả khi kết luận thẳng.

**Tám lỗi của lần 2**

| # | Lỗi | Sau khi sửa |
|---|---|---|
| 1 | “Có thể nhằm chẩn đoán đột biến” vẫn kết luận khớp | Mục đích chỉ được ghi nhận khi mọi lần nhắc đều rõ ràng; còn lại hỏi lại |
| 2 | Phủ định dài (“chưa có đủ bằng chứng để chẩn đoán xác định…”) và chẩn đoán được đính chính | Xét cả vế câu thay vì 6 từ; một bệnh vừa được nêu vừa bị phủ định thì hỏi lại |
| 3 | “Chưa xác định có đái tháo đường thai kỳ” vẫn áp nhánh thai kỳ | Thai kỳ được đọc như mọi dữ kiện khác; chưa rõ thì hỏi |
| 4 | “Lần đầu tại bệnh viện này” bị hiểu là chưa từng làm | “Lần đầu” chỉ tính khi nói về chính xét nghiệm; kèm nơi chốn hoặc “khám lần đầu” thì hỏi ngày lần trước |
| 5 | “Không tầm soát mà…” vẫn bị ghi là tầm soát, kể cả khi sửa ở lượt sau | Tầm soát chỉ ghi khi nói rõ; lượt sau sửa lại thì thay mục đích cũ |
| 6 | “Cả xét nghiệm HER2 và Trastuzumab… chưa có kết quả” mất phần thuốc | Câu “cả… và…” luôn trả đủ hai phần |
| 7 | “Định type HLA-B bằng PCR-SSP” bị coi là kỹ thuật khác | Chỉ các xét nghiệm alen riêng (B27, B*5801, B*1502), NGS, flow… mới bị coi là khác dòng |
| 8 | Nguồn xét nghiệm hỏng bị bỏ qua không báo trong câu trả lời gộp | Câu trả lời gộp ghi rõ xét nghiệm nào chưa trả lời vì tệp nguồn hỏng |

**Sửa thêm ngoài tám lỗi**
- Khoảng cách ước lượng (“gần 100 ngày”, “chưa đến 3 tháng”, “khoảng…”) không được so với mốc ngày; chatbot hỏi ngày chính xác.
- “Từng dùng”, “trước đây”, “đã điều trị xong” được hiểu là chuyện đã qua, không phải hiện tại.
- “Chắc là”, “hình như”, “gia đình”, “người nhà” đi trước một dữ kiện thì dữ kiện đó chưa được khẳng định.
- “Insulin tạm ngưng”, “mới ngưng”, “chưa cần đến insulin” được hiểu là không dùng.

**Kiểm thử**
- `tests/test_lab_review7.py`: 15 kiểm thử, gồm 33 câu “không được kết luận nếu chưa xác nhận hoặc hỏi lại”.
- 396 kiểm thử backend; 123 và 67 kiểm tra giao diện.

**Hệ quả cần biết**
- Câu hỏi có thêm chi tiết lâm sàng ngoài danh sách từ đã biết (ví dụ “bước 2”, “thuốc viên”, “suy thận”) sẽ cần thêm một lần bấm xác nhận. Đây là đánh đổi có chủ ý: thà hỏi thêm còn hơn kết luận sai.
- Lớp chặn này chỉ bảo đảm chatbot không kết luận khi gặp từ lạ. Một câu chỉ gồm từ đã biết nhưng ghép theo cách chưa lường tới vẫn có thể bị hiểu sai; khi đó phần “Chatbot hiểu dữ kiện như sau” là chỗ để bác sĩ phát hiện.

## Rà soát lần 3 ngày 11/11/2026: 4 lỗi, đã sửa

| # | Lỗi | Sau khi sửa |
|---|---|---|
| 1 | Dữ kiện đã xác nhận của bệnh nhân trước vẫn được dùng khi hỏi "bệnh nhân khác" (cả thuốc lẫn xét nghiệm) | Câu có "bệnh nhân khác", "ca mới", "trường hợp khác"… thì xóa mọi dữ kiện, chỉ giữ thuốc hoặc xét nghiệm đang bàn |
| 2 | Trả lời câu hỏi tiếp theo là bỏ qua được bước xác nhận | Từ chưa hiểu chắc và ý chưa chắc chắn được lưu cùng ca bệnh qua các lượt; chỉ bấm xác nhận mới xóa |
| 3 | "Dùng insulin trong năm trước" bị hiểu là đang dùng; "để sàng lọc hoặc theo dõi" bị chốt một mục đích | Từ chỉ thời gian chỉ được tính khi nằm trong cụm ngày tháng đã biết; "hoặc", "hay", "nếu", "sau", "trước" luôn cần xác nhận; nêu hai mục đích thì hỏi lại |
| 4 | Đang chờ xác nhận mà vẫn hiện "Áp dụng nhánh…" | Phần lý do và phần tô đậm chỉ hiện sau khi xác nhận |

Kiểm thử: `tests/test_lab_review8.py` (12 kiểm thử); tổng 408 kiểm thử backend, 123 và 67 kiểm tra giao diện.

Giới hạn vẫn còn: một câu chỉ gồm từ đã biết, ghép theo cách chưa lường tới, vẫn có thể bị hiểu sai. Phần "Chatbot hiểu dữ kiện như sau" là chỗ để bác sĩ kiểm tra trước khi tin kết luận.

## Rà soát lần 4 ngày 11/11/2026: 2 lỗi, đã sửa

| # | Lỗi | Sau khi sửa |
|---|---|---|
| 1 | Câu bắt đầu bằng "Đúng" hoặc "Ok" bị coi là xác nhận, phần còn lại bị bỏ qua ("Đúng nhưng bệnh nhân không dùng insulin", "Ok, hỏi Trastuzumab…") | Chỉ khi cả câu là lời xác nhận thì mới tính. Câu có sửa dữ kiện được đọc và hiện lại cách hiểu mới; câu chuyển chủ đề thì chuyển |
| 2 | Hai yêu cầu chạy xen kẽ có thể làm mất bước chờ xác nhận, vì trạng thái của một yêu cầu bị lưu trên đối tượng dùng chung | Trạng thái của từng yêu cầu chỉ nằm trong biến cục bộ, cả ở phần xét nghiệm (`_same_case`) lẫn phần thuốc (`_new_turn`) |

Kiểm thử: `tests/test_lab_review9.py` (8 kiểm thử), có ca tái hiện đúng tình huống yêu cầu B chạy chen giữa yêu cầu A; tổng 422 kiểm thử backend.


## Đồng bộ trạng thái thẩm định (11/11/2026)

Người rà soát chỉ ra: ghi chú nói "đã thẩm định" nhưng chân câu trả lời ghi "Chờ bệnh viện thẩm định" và phần sao chép ghi "chưa được bệnh viện thẩm định". Nhận xét đúng.

**Cách làm mới**
- Mỗi phần của câu trả lời tự nêu trạng thái thẩm định của đúng nội dung nó hiển thị (`review` của từng thuốc, từng xét nghiệm).
- Chân câu trả lời (`review_label`) và phần sao chép (`review_note`) được ghép từ các trạng thái đó, không còn câu viết sẵn.
- Bốn nhãn:

| Nhãn ở chân câu trả lời | Khi nào |
|---|---|
| Dược/BHYT đã thẩm định điều kiện (theo xác nhận của nhóm dự án) | Thuốc có bảng điều kiện đã thẩm định; xét nghiệm chép từ bản scan |
| Phần đối chiếu chưa được Dược/BHYT thẩm định | HbA1c, xét nghiệm gen, SCC: nguyên văn lấy từ lớp chữ, phần đối chiếu ca bệnh do nhóm xây dựng |
| Trích nguyên văn nguồn | Thuốc không có bảng điều kiện riêng; xét nghiệm TT39 không có đối chiếu ca bệnh |
| Thẩm định một phần, xem ghi chú từng mục | Câu trả lời gồm cả hai loại |

**Sửa kèm theo**
- Câu trả lời về thuốc trước đây ghi nhầm "Nguồn xét nghiệm kiểm tra…" ở chân; nay ghi "Theo bộ nguồn BHYT 06/11/2026".
- Server đọc hết nội dung yêu cầu trước khi từ chối (403/404/413/415). Trước đây thỉnh thoảng máy khách bị ngắt kết nối thay vì nhận mã lỗi; đây là nguyên nhân 1–2 kiểm thử HTTP lúc đạt lúc lỗi.

Kiểm thử: `tests/test_review_status.py` (7 kiểm thử); tổng 429 kiểm thử backend, chạy 6 lượt liên tiếp đều đạt; 132 và 67 kiểm tra giao diện.

## Rà soát lần 5 ngày 11/11/2026: 2 điểm, đã sửa

| # | Điểm nêu | Sau khi sửa |
|---|---|---|
| 1 | Yêu cầu quá lớn (khoảng 0,5 MB trở lên) bị từ chối vẫn có lượt bị ngắt kết nối, vì server chỉ đọc 20 KB đầu | Phần còn lại được đọc và bỏ đi, tối đa 16 MB, rồi mới trả 403 hoặc 413. Lớn hơn mức đó thì server trả lời xong mới đóng kết nối từ từ. Mỗi kết nối có giới hạn chờ 30 giây |
| 2 | Phần sao chép của câu trả lời về thuốc vẫn ghi "Nguồn xét nghiệm kiểm tra…" | Chân câu trả lời và phần sao chép dùng chung một hàm (`sourceStamp`), chỉ nêu nguồn xét nghiệm khi câu trả lời có xét nghiệm |

Kiểm thử: thêm 5 kiểm thử vào `tests/test_review_status.py` (yêu cầu 0,5 MB, 3 MB và 20 MB bị từ chối đều nhận đúng mã lỗi); tổng 434 kiểm thử backend, 135 và 67 kiểm tra giao diện.
