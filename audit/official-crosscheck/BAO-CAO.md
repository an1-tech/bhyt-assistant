# Đối chiếu danh mục TT20 với bản PDF chính thức — 07/11/2026

**Kết luận:** 18/18 thuốc ung bướu chọn cho prototype khớp hoàn toàn với bản hợp nhất chính thức 15/VBHN-BYT (đường dùng, 4 cột hạng bệnh viện, nguyên văn ghi chú). Toàn bộ 1.133 dòng chỉ được dò thô vì PDF chính thức là bản scan.

## Nguồn
- Dữ liệu chatbot: `data/drugs_appendix_I.jsonl`, chữ lấy từ thuvienphapluat.vn.
- Bản chính thức: `data/sources/15-vbhn-byt-2024.pdf` (15/VBHN-BYT, datafiles.chinhphu.vn), 75 trang, bản scan có lớp chữ OCR nhiễu.

## Tầng 1 — dò thô toàn bộ (`tools/crosscheck_official_pdf.py`)
| Chỉ số | Kết quả |
|---|---|
| Dòng thuốc | 1.133 |
| Tên hoạt chất tìm thấy gần đúng trong lớp OCR | 812 |
| Dòng có tỷ lệ % trong ghi chú | 59 |
| … tỷ lệ % tìm thấy trên trang tương ứng | 51 |
| Dòng bị đánh dấu xem lại | 325 |

Các dòng bị đánh dấu phần lớn do OCR làm hỏng chữ (ví dụ "ICandesartan", "bndapamid"), chưa phải bằng chứng dữ liệu sai. Chi tiết: `coarse-results.json`.

## Tầng 2 — đọc bằng mắt 18 thuốc ung bướu (`tools/verify_visual_check.py`)
Trang 30–34 được dựng thành ảnh, chép lại từng trường vào `oncology-visual-check.json`, rồi so tự động với dữ liệu (chỉ chuẩn hóa khoảng trắng và gạch nối). Kết quả `oncology-visual-result.json`: **18 khớp, 0 lệch**. Lỗi chính tả có sẵn trong văn bản gốc (Cetuximab "vùng đầu. cổ") cũng trùng khớp.

## Giới hạn
- Người đọc ảnh là Đỗ Quốc An; cần Dược/BHYT xác nhận lại.
- 1.115 dòng còn lại chưa được đọc bằng mắt. Khi mở rộng sang thuốc khác, lặp lại tầng 2 cho nhóm đó.
