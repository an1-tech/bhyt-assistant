# Danh sách thuốc công khai của bệnh viện (website Vinmec)

Nguồn: `Doc1.docx` do người dùng cung cấp ngày 08/11/2026. File gồm 24 ảnh chụp mục "Danh sách thuốc" trên website, không có chữ, nên danh sách được chép tay từ ảnh.

- Bản gốc nằm ở `data/hospital/raw/`. Thư mục này có trong .gitignore và chỉ để ở máy này.
- SHA-256 của bản gốc được ghi trong file JSON.

## File

| File | Nội dung |
|---|---|
| `tools/build_hospital_list.py` | Bản chép 24 ảnh (giữ nguyên chính tả và các dòng trùng). Script tách đường dùng, ghi chú trong ngoặc và các thành phần ngăn bởi "/". |
| `data/hospital/hospital_drug_list.json` | 192 dòng. Mỗi dòng có mã `HL-ảnh-vị trí`, chữ cái, trang, ảnh nguồn. |
| `tools/match_hospital_list.py` | Đối chiếu từng dòng với TT20 (Phụ lục I/II). |
| `data/hospital/hospital_tt20_match.json` | Kết quả đối chiếu. Mỗi dòng có mức khớp, dòng TT20 tương ứng và kết quả kiểm tra đường dùng. |

## Thống kê

**Số dòng**
- Danh sách có 192 dòng, tương ứng 188 tên khác nhau.
- 4 tên bị trùng: Abobotulinum Toxin A, Alendronate, Fluconazole, Zopiclon.

**Theo chữ cái**
- A: 44 dòng (2 trang)
- M: 47 dòng (2 trang)
- N: 13 dòng
- C và L: mỗi chữ 10 dòng
- F: 8 dòng
- B: 7 dòng
- D, E, G, P: mỗi chữ 6 dòng
- I, R, Z: mỗi chữ 4 dòng
- H, O, V: mỗi chữ 3 dòng
- S, T, X: mỗi chữ 2 dòng
- K và W: mỗi chữ 1 dòng
- Không có thuốc nào bắt đầu bằng chữ J, Q, U, Y; 24 ảnh là toàn bộ danh sách công khai (người cung cấp xác nhận ngày 11/11/2026).

**Theo loại, tính trên 188 tên**
- 163 hoạt chất đơn.
- 10 phối hợp có dấu "/".
- 15 tên sản phẩm: Alvesin, Aminosteril N-Hepa 8%, Bernevit, Broncho Vacxom, Cerebrolysin, Fleet Enema, Gaviscon, Lipofundin MCT/LCT, Maxitrol, Moriamin Forte, Morihepamin, Neoamyu, Neopeptin, Neopeptin syrup, Neuroaid.

**Ghi chú in kèm tên**
- 17 tên ghi kèm đường dùng, ví dụ "(Tiêm)", "(Nhỏ Mắt)".
- 3 tên ghi kèm tên đồng nghĩa: Phytonadione, rhEGF, Menatetrenone.

**Tên có vẻ viết sai**
Các tên này được giữ nguyên như bản in:
- Perindorpil
- Mildagliptin/Metformin
- Minagliptin
- Mytomycin C
- Methycobalamin

### Kết quả đối chiếu với TT20 (188 tên)

| Mức | Số tên | Chatbot dùng? | Ví dụ |
|---|---:|---|---|
| exact: khớp đúng tên | 80 | có | Bevacizumab, Metformin |
| spelling: khác cách viết theo quy tắc cố định | 55 | có, và ghi rõ đã quy đổi | Hydroxychloroquine → Hydroxy cloroquin, Mannitol → Manitol, Adrenaline → Epinephrin |
| salt: khác muối hoặc ester | 10 | có, và ghi rõ đã quy đổi | Montelukast → Natri montelukast, Mometasone → Mometason furoat |
| combination: TT20 có dòng phối hợp tương ứng | 6 | có, khi các thành phần được nối bằng "/", "+" hoặc "phối hợp" | Amoxicillin/ Clavulanic Acid → Amoxicilin + acid clavulanic |
| ambiguous: khớp nhiều dòng | 1 | không | Acetylcysteine (TT20 có cả Acetylcystein và N-acetylcystein) |
| parts: TT20 không có dòng phối hợp | 3 | không, chỉ báo thành phần nào có riêng | Metronidazole/ Chlorhexidine |
| review: chỉ có tên gần giống, cần Dược xem | 9 | không, chỉ hiện gợi ý | Perindorpil → Perindopril?, Cerebrolysin → Peptid (Cerebrolysin concentrate) |
| none: không thấy trong TT20 | 24 | không | 10 hoạt chất và 14 tên sản phẩm |

**Tổng hợp**
- Chatbot dùng được 151 trên 188 tên. Tất cả nằm ở Phụ lục I.
- 34 tên trong số đó có điều kiện thanh toán ghi trong TT20.

**10 hoạt chất không thấy trong TT20 theo tên**
Adenosine, Alprostadil, Febuxostat, Menotrophin, Mepivacaine, Mifepristone, Minoxidil, Mucopolysaccharide Polysulfate, Natri sulphacetamide, Sildenafil.

Không thấy ở đây chưa đủ để kết luận BHYT không thanh toán. Cần Dược hoặc BHYT kiểm tra.

**Đường dùng bệnh viện ghi không có trong dòng TT20**
- Alpha Chymotrypsine (Tiêm): TT20 chỉ có đường Uống.
- Glyceryl Trinitrate (Uống): TT20 có Tiêm, phun mù, dán ngoài da và đặt dưới lưỡi.

## Chatbot dùng danh sách này như thế nào

**1. Nhận tên theo cách viết của bệnh viện**
- Bác sĩ gõ tên theo cách viết trên danh sách, ví dụ "Hydroxychloroquine", chatbot tìm được dòng TT20 tương ứng.
- Câu trả lời ghi rõ đã quy đổi cách viết.
- Chỉ áp dụng cho các mức exact, spelling, salt và combination.
- Không bao giờ quy đổi theo tên gần giống. Ví dụ "Maxitrol" không được hiểu thành "Manitol".

**2. Báo thuốc có trong danh sách**
- Câu trả lời có thêm dòng "Danh sách thuốc công khai trên website Vinmec có: …".
- Kèm lưu ý rằng danh sách không ghi biệt dược, hàm lượng hay số đăng ký, nên không xác nhận thuốc đang được cung ứng hay được BHYT thanh toán.
- Thuốc không có trong danh sách thì chatbot không ghi gì, vì vắng mặt trong danh sách không mang ý nghĩa gì.

**3. Tên có trong danh sách nhưng không tìm được trong TT20**
Chatbot nói rõ đó là trường hợp nào:
- tên sản phẩm chưa có ánh xạ sang hoạt chất đã kiểm chứng;
- phối hợp mà TT20 không có dòng tương ứng;
- tên chỉ gần giống một tên trong TT20;
- hoạt chất không có trong TT20.

Câu trả lời vẫn giữ câu "chưa đủ để kết luận thuốc không được BHYT thanh toán".

**4. Đường dùng không khớp**
Nếu đường dùng bệnh viện ghi không có trong dòng TT20, chatbot báo rõ.

**5. Nhập thông tin định danh**
Câu hỏi có thông tin định danh người bệnh thì không kèm ghi chú nào.

## Giới hạn

**Bản chất danh sách**
- Đây là danh sách tra cứu thông tin thuốc trên website, không phải danh mục trúng thầu.
- Các mức spelling, salt và combination là quy tắc do mình đặt, chưa được Dược duyệt. Test kiểm lại từng cặp tên bằng chính quy tắc đó.

**Việc cần Dược hoặc BHYT xem tiếp**
- 9 tên ở mức review.
- 14 tên sản phẩm chưa ánh xạ.
- 10 hoạt chất không thấy trong TT20.
- 2 trường hợp đường dùng không khớp.
- Tên trùng Acetylcysteine.

**Cập nhật khi có ảnh mới**
1. Bổ sung ảnh vào `PAGES`.
2. Chạy `tools/build_hospital_list.py`.
3. Chạy `tools/match_hospital_list.py`.
4. Chạy test.
