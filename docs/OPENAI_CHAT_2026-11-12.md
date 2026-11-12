# Hỗ trợ ngôn ngữ OpenAI · 12/11/2026

Người thực hiện: **Đỗ Quốc An**.

## Luồng xử lý

1. Xác minh trạng thái hội thoại có chữ ký, kiểm tra câu hỏi và chặn các mẫu thông tin định danh đã được ứng dụng nhận biết trước khi gọi API. Đây không phải bộ khử định danh hoàn chỉnh; người dùng vẫn không được nhập thông tin định danh.
2. Lõi cục bộ tạo kết quả đối chiếu. Khi được bật, AI nhận câu hỏi, ngữ cảnh đã xác minh và ứng viên tên thuốc trong danh mục để nhận diện cách viết tự nhiên.
3. Nếu AI đề xuất câu hỏi khác, hiển thị cách hiểu và chờ bác sĩ xác nhận. Không tự đối chiếu một câu hỏi do AI viết lại. Đề xuất được ký cùng trạng thái, hết hạn sau 15 phút; việc sửa câu hỏi loại bỏ đề xuất cũ. Dữ kiện của ca trước không đưa vào ngữ cảnh AI khi chuyển bệnh nhân.
4. AI biên tập bằng kế hoạch có cấu trúc: chọn biến thể câu đã có, chỉ số điều kiện quan trọng và ID nguồn hợp lệ. Máy chủ xác minh toàn bộ kế hoạch. Không cho model xuất đoạn kết luận BHYT tự do. Tất cả điều kiện vẫn có trong bản đầy đủ và bản sao chép.
5. Nguồn bắt buộc của thuốc/xét nghiệm và căn cứ chuyển tiếp không được xóa dù AI không chọn. Không đưa các nguồn tham khảo rộng trở lại cuối câu trả lời.

## Cấu hình và giới hạn

`configure-openai.py` mở cửa sổ có trường key được che. Tệp `.env` và tệp ghi tạm key đã được loại khỏi Git. Không có endpoint trả key cho trình duyệt. Công tắc mới là `BHYT_CHAT_AI=1`; giữ `BHYT_ENABLE_AI=0` cho mã legacy.

Responses API sử dụng Structured Outputs (`text.format`, `strict:true`) và `store:false`. API được gọi phía máy chủ, không có công cụ web tự động hoặc tải tài liệu mới. Model mặc định của cửa sổ cấu hình là `gpt-4.1-mini`, đã thử thành công với tài khoản cấu hình trên máy; có thể đổi model có hỗ trợ schema tương ứng.

Tối đa hai yêu cầu hỗ trợ đồng thời; mỗi lượt thường có một lần chuẩn hóa và một lần biên tập. Một đề xuất cách hiểu dừng trước biên tập. Yêu cầu xác nhận lâm sàng bỏ qua chuẩn hóa. Timeout được giới hạn 3–20 giây mỗi lần gọi, không tự retry. Mọi lỗi provider, refusal, phản hồi chưa hoàn tất hoặc cấu trúc sai đều trả về kết quả cục bộ; không đưa nội dung lỗi provider hoặc key lên giao diện.

Đây là bước rút gọn có kiểm soát, không phải một model tự do viết lại quy định y khoa. Không tự tăng phạm vi dữ liệu, cập nhật thông tư hoặc đổi trạng thái thẩm định.

## Kiểm tra

- Bộ unittest đầy đủ cuối cùng: 463 test, 462 đạt và 1 bỏ qua; toàn bộ gọi AI trong test được giả lập.
- Kiểm thử riêng cho lớp AI: chặn dữ liệu định danh, không lộ key, chữ ký đề xuất, hết hạn, sửa dữ kiện, nhiều hội thoại, thiếu nguồn, bịa số liệu/ID, timeout và phản hồi từ chối; thêm kiểm tra endpoint HTTP thật với API giả lập.
- 42 kiểm tra trình duyệt ở 1440/768/390px bằng `tools/check-ai-ui.mjs` với `tools/serve-ai-fixture.py`, không gọi API trả phí. Đã xem ảnh giao diện xác nhận và câu trả lời; 67 kiểm tra chat cục bộ và 135 kiểm tra xét nghiệm với AI giả lập cũng đạt.
- API thật: câu hỏi đầy đủ về Trastuzumab, viết tắt “Trastu K vú BH trả ko?”, “XN HbA1c theo dõi ĐTĐ có BH không?” và hỏi tiếp “Nếu HER2 âm tính thì sao?” đã trả về luồng tương ứng. Lần thử viết tắt đầu chưa nhận diện đủ; sau khi bổ sung ứng viên từ danh mục, đề xuất được xác nhận và tra đúng Trastuzumab. Đây là kiểm tra mẫu, không chứng minh mọi cách diễn đạt đều đúng.

Tài liệu OpenAI đã đối chiếu: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [bảo vệ API key](https://developers.openai.com/api/reference/overview#authentication).
