# Chatbot tra cứu BHYT — Toàn bệnh viện · v1.11

**Người thực hiện: Đỗ Quốc An.** Nhánh `Ux/Ui` bổ sung giao diện xanh mint, linh vật sóc y tế và khung đọc nguồn ngay trong cuộc trò chuyện. Nút **Xem nguồn** mở nguyên văn có tô sáng; vẫn có liên kết tới đúng trang PDF hoặc dòng xét nghiệm. Điều kiện, xác nhận dữ kiện và nội dung sao chép đầy đủ được giữ lại. Chi tiết thiết kế và kiểm tra: [UI/UX 11/11/2026](docs/UI_UX_2026-11-11.md).

Giao diện chính là một khung chat để tra thuốc và xét nghiệm. Bác sĩ hỏi điều kiện chung thì bot trả ngay; khi chủ động hỏi một tình huống cụ thể, bot chỉ hỏi thêm dữ kiện cần đối chiếu, không yêu cầu điền hồ sơ bệnh nhân. Bản v1.11 bổ sung HbA1c và xét nghiệm đột biến gen EGFR, với nguồn riêng và nút mở đúng dòng tài liệu.

## Mở ứng dụng

Dự án: `D:/Vinmec/bhyt-chatbot`. Nhấp đúp `start-windows.bat`, hoặc mở **http://127.0.0.1:8766/?v=1.11#lookup** nếu ứng dụng đang chạy. Bản này dùng Python có sẵn trên máy, không cần khóa API hoặc cài thêm thư viện để chạy.

Tệp `.python-path.txt` ghi đường dẫn Python đang có trên máy; nếu chuyển máy, thay bằng Python 3.10+ thực tế. Lệnh `python` mặc định của Windows có thể là Store alias. Để dừng bản chạy nền, chạy `stop-windows.ps1` bằng PowerShell; script chỉ dừng đúng tiến trình của dự án.

## Dùng chatbot

- Thử “HbA1c theo dõi đái tháo đường có điều kiện BHYT gì?”, hoặc “HbA1c hôm nay để đánh giá kết quả điều trị đái tháo đường, lần trước cách 60 ngày”.
- Thử “Xét nghiệm EGFR trong điều trị ung thư phổi không tế bào nhỏ có BHYT không?” và “Cả xét nghiệm EGFR và thuốc Erlotinib trong ung thư phổi không tế bào nhỏ có BHYT không?”.
- Thử câu hỏi một lần của bác sĩ: “HbA1c hôm nay để đánh giá kết quả điều trị đái tháo đường, lần trước làm ngày 01/08/2026, BHYT có thanh toán không?”.
- Thử các xét nghiệm khác: “Xét nghiệm HER2 cho bệnh nhân ung thư vú đang điều trị hôm nay”, “Định lượng procalcitonin có điều kiện BHYT gì?”, “Định lượng BNP”.
- Có 41 dòng xét nghiệm có điều kiện riêng (TT39/2024 và 17/VBHN-BYT). Chỉ HbA1c, bốn xét nghiệm gen và SCC được đối chiếu với ca bệnh; các dòng khác chỉ trích nguyên văn.
- “Xem vị trí trích dẫn” mở ảnh trọn dòng dịch vụ (hoặc ảnh trang với dòng chép từ bản scan), bản chữ và liên kết PDF gốc. Xét nghiệm ngoài 41 dòng không được mượn quy tắc của dòng khác.

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

Câu trả lời chi tiết theo điều kiện thanh toán hiện có cho 18 thuốc ung bướu: 12 thuốc theo nhánh chỉ định (ví dụ Trastuzumab, Erlotinib, Gefitinib, Cetuximab, Rituximab), 3 thuốc theo dạng bào chế hoặc mục đích sử dụng (Doxorubicin, Paclitaxel, Everolimus) và 3 thuốc chỉ ghi tỷ lệ (Afatinib, Fulvestrant, Bevacizumab). 18 bảng này nằm trong `data/indication_rules.json`; mỗi nhánh phải trích nguyên văn ghi chú nguồn và tỷ lệ phải nằm trong đoạn trích. Về xét nghiệm có 41 dòng có điều kiện riêng, trong đó 6 dòng có đối chiếu theo ca bệnh (xem `docs/LAB_LOOKUP_V1.11.md`). Nhóm dự án xác nhận Dược/BHYT của bệnh viện đã thẩm định các bảng này ngày 11/11/2026; biên bản và tên người duyệt chưa lưu trong bộ nguồn (`data/review_attestation.json`). Thêm thuốc mới bằng cách thêm mục vào bảng (xem `docs/V1.9.md`). Các thuốc khác vẫn tra được danh mục/nguyên văn ghi chú, nhưng bot chưa tự kết luận đầy đủ theo mọi bệnh hoặc cách diễn đạt. Không suy ra thanh toán 100% từ ô trống.

Bộ nguồn BHYT chốt 06/11/2026; nguồn bổ sung được tìm kiếm/kiểm tra riêng ngày 07/11/2026. Không chứng minh đã rà soát mọi thay đổi mới nhất. Chưa đủ nhãn sản phẩm được phê duyệt, chuyên luận Dược thư và danh mục/hợp đồng nội bộ bệnh viện. Thông tin trong chatbot là quy định có điều kiện theo nguồn, không phải quyết định quyền lợi hoặc số tiền thanh toán cá nhân.

## Cách chạy và kiểm tra

Luồng `/api/chat` dùng `ChatAssistant` bọc quanh `Corpus.converse()`. Mặc định lớp hỗ trợ AI tắt; chỉ bật khi có `BHYT_CHAT_AI=1`, key và model. Lõi `Corpus.converse()` tiếp tục đối chiếu hoàn toàn cục bộ. Công tắc AI cũ `BHYT_ENABLE_AI` không bật lớp chat mới; mã legacy trong `ai_explain.py` vẫn tắt mặc định.

## Bật hỗ trợ OpenAI cho ô chat

Người thực hiện: **Đỗ Quốc An**.

Chạy `python configure-openai.py` bằng Python của máy. Cửa sổ nhập key có che ký tự, lưu key vào `.env` đã được loại khỏi Git. Có thể chọn model tài khoản được phép dùng; gợi ý ban đầu là `gpt-4.1-mini`. Khởi động lại ứng dụng sau khi lưu. Không dán key vào ô chat hoặc ghi trong mã giao diện.

- AI đề xuất cách hiểu cho câu viết tắt hoặc thiếu chủ ngữ. Nếu cách hiểu thay đổi, bác sĩ xem lại rồi bấm **Đúng, tra cứu câu này**, gõ một câu xác nhận đầy đủ như “Đúng rồi”, hoặc sửa câu hỏi. Câu có thêm phần sửa dữ kiện không bị coi là xác nhận.
- AI chọn cách trình bày ngắn từ các câu đã được giới hạn sẵn, ưu tiên điều kiện sát câu hỏi và xếp nguồn liên quan. AI không được tự tạo điều kiện, số liệu hoặc kết luận thanh toán. Điều kiện thuốc còn lại có thể mở rộng; phần sao chép vẫn giữ đầy đủ.
- Chỉ nguồn trực tiếp và căn cứ phụ thuộc của câu trả lời được gửi để xếp thứ tự; các tài liệu tham khảo không liên quan không tự xuất hiện trở lại.
- Câu hỏi, ngữ cảnh hợp lệ và trích đoạn liên quan được gửi tới OpenAI khi bật. Yêu cầu dùng `store:false`; đây không phải cam kết không có lưu giữ dữ liệu ở cấp dịch vụ. Không nhập thông tin định danh người bệnh. Có thể phát sinh phí API.
- Không có key, tắt `BHYT_CHAT_AI`, lỗi mạng, hết hạn mức hoặc đầu ra không hợp lệ: chatbot tiếp tục dùng kết quả cục bộ. Tối đa hai lượt hỗ trợ AI đồng thời, không tự thử lại yêu cầu lỗi.

Chi tiết kiến trúc, giới hạn và kiểm tra: [Tích hợp OpenAI](docs/OPENAI_CHAT_2026-11-12.md).

Chạy kiểm thử backend bằng Python thực tế: `python -B -m unittest discover -s tests -q`. Kiểm thử xét nghiệm riêng: `python -B -m unittest discover -s tests -p "test_lab_*.py" -q`. Chạy ứng dụng trước khi kiểm tra trình duyệt: `node tools/check-lab-ui.mjs http://127.0.0.1:8766` (cần Node 22+, Chrome/Edge và toolkit design-taste-frontend đã cài trên máy). Kết quả kiểm tra bản v1.11 và giới hạn được ghi trong `docs/LAB_LOOKUP_V1.11.md`. Các script giao diện của phiên bản cũ được giữ để tham khảo lịch sử.

Đã xem ảnh desktop, tablet và mobile. Bộ đo giao diện báo 0 FAIL / 1 WARN: cảnh báo `unused-canvas` do nhận nhầm thanh điều hướng ngang là sidebar; khung chat chủ ý rộng tối đa 840px, căn giữa với hai lề bằng nhau để đọc hội thoại. Đây là lựa chọn cho yêu cầu chỉ có một chatbot, không phải một dashboard nhiều cột.

Xem [tra cứu xét nghiệm v1.11](docs/LAB_LOOKUP_V1.11.md), [thay đổi v1.9](docs/V1.9.md), [thay đổi v1.8](docs/CHAT_ONLY_V1.8.md), [báo cáo nguồn](docs/SOURCE_UPDATE_2026-11-07.md).
