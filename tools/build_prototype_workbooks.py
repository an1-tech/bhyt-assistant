"""Build the three oncology-prototype workbooks (needs openpyxl).

    python tools/build_prototype_workbooks.py

Outputs to prototype/:
  01-danh-sach-thuoc-ung-buou-GIA-LAP.xlsx   mock tender list (real TT20 rows, fake brand/registration)
  02-mau-thu-ca-benh-an-danh.xlsx            anonymous case collection form
  03-mau-duyet-dieu-kien-thanh-toan.xlsx     draft condition branches for Pharmacy/BHYT review
Ingredient, route, hospital columns and notes are read from data/drugs_appendix_I.jsonl.
Branch proposals below are drafts quoted from the note; they are not reviewed rules.
"""
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "prototype"
FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="1F3A5F")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
MOCK_FILL = PatternFill("solid", fgColor="FCE4E4")
EXAMPLE_FILL = PatternFill("solid", fgColor="E8EEF7")
THIN = Side(style="thin", color="B7BEC8")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")

# Selected oncology drugs: STT in TT20 Appendix I -> why it is in the prototype.
SELECTION = {
    402: "Hai nhánh chỉ định, tỷ lệ khác nhau (60%/50%), cần HER2 dương tính, giới hạn hạng bệnh viện",
    394: "Chỉ định hẹp: UTP không tế bào nhỏ + EGFR dương tính",
    395: "Chỉ định hẹp: UTP không tế bào nhỏ + EGFR dương tính",
    391: "Chỉ ghi tỷ lệ 50%, không ghi chỉ định: dễ hiểu nhầm phạm vi",
    382: "Hai chỉ định: UTP không tế bào nhỏ, u trung biểu mô màng phổi",
    393: "Hai chỉ định, cần RAS tự nhiên (đại trực tràng), giới hạn hạng bệnh viện",
    392: "Chỉ có điều kiện hạng bệnh viện + tỷ lệ 50%",
    401: "Ba chỉ định với hai mức tỷ lệ (50%/30%)",
    396: "Hai chỉ định (CML, GIST), tỷ lệ 80%",
    397: "Chỉ khi không dung nạp/kháng Imatinib",
    400: "Cần u lympho không Hodgkin tế bào B CD20 dương tính; ghi chú không ghi tỷ lệ",
    347: "Hai chỉ định có điều kiện điều trị trước (Fludarabin, Rituximab)",
    385: "Chỉ ung thư dạ dày di căn, tỷ lệ 70%",
    403: "Cần thất bại điều trị nội tiết hoặc hóa trị trước, tỷ lệ 30%",
    409: "Chỉ ghi tỷ lệ 50%",
    362: "Tỷ lệ theo dạng bào chế (liposome 50%)",
    381: "Tỷ lệ theo dạng bào chế (liposome/polymeric micelle 50%)",
    365: "Tỷ lệ theo mục đích: điều trị ung thư 50%, trường hợp khác 100%",
}

# Draft branches quoted from each note. "info" = what the doctor would need to confirm.
BRANCHES = {
    402: [("Ung thư vú có HER2 dương tính", "HER2 dương tính", 60, "Bệnh viện hạng đặc biệt, hạng I, BV chuyên khoa ung bướu hạng II", "Nếu HER2 âm tính thì sao?"),
          ("Ung thư dạ dày tiến xa hoặc di căn có HER2 dương tính", "HER2 dương tính; giai đoạn tiến xa/di căn", 50, "Bệnh viện hạng đặc biệt, hạng I, BV chuyên khoa ung bướu hạng II", "Còn ung thư vú thì sao?")],
    394: [("Ung thư phổi thể không phải tế bào nhỏ có EGFR dương tính", "Thể không tế bào nhỏ; EGFR dương tính", 50, "", "Nếu EGFR âm tính thì sao?")],
    395: [("Ung thư phổi thể không phải tế bào nhỏ có EGFR dương tính", "Thể không tế bào nhỏ; EGFR dương tính", 50, "", "Nếu EGFR âm tính thì sao?")],
    391: [("Không ghi chỉ định riêng trong ghi chú", "Chỉ định theo nhãn/hướng dẫn điều trị (cần xác định)", 50, "", "Afatinib dùng cho bệnh nào thì được thanh toán?")],
    382: [("Ung thư phổi không tế bào nhỏ", "Thể không tế bào nhỏ", 50, "", "Còn u trung biểu mô màng phổi thì sao?"),
          ("Ung thư trung biểu mô màng phổi ác tính", "Chẩn đoán u trung biểu mô màng phổi ác tính", 50, "", "Còn ung thư phổi không tế bào nhỏ thì sao?")],
    393: [("Ung thư đại trực tràng di căn thuộc type RAS tự nhiên", "Di căn; RAS tự nhiên (wild-type)", 50, "Bệnh viện hạng đặc biệt, hạng I, BV chuyên khoa ung bướu hạng II", "Nếu RAS đột biến thì sao?"),
          ("Ung thư tế bào vảy vùng đầu, cổ", "Mô bệnh học tế bào vảy, vị trí đầu cổ", 50, "Bệnh viện hạng đặc biệt, hạng I, BV chuyên khoa ung bướu hạng II", "Còn ung thư đại trực tràng thì sao?")],
    392: [("Không ghi chỉ định riêng trong ghi chú", "Chỉ định theo nhãn/hướng dẫn điều trị (cần xác định)", 50, "Bệnh viện hạng đặc biệt, hạng I, BV chuyên khoa ung bướu hạng II", "Bevacizumab dùng ở bệnh viện hạng nào?")],
    401: [("Ung thư tế bào biểu mô gan", "Chẩn đoán ung thư biểu mô tế bào gan", 50, "", "Còn ung thư thận thì sao?"),
          ("Ung thư biểu mô tuyến giáp biệt hóa tiến triển tại chỗ hoặc di căn, đã thất bại với iod phóng xạ", "Tiến triển tại chỗ/di căn; đã thất bại iod phóng xạ", 50, "", "Nếu chưa điều trị iod phóng xạ thì sao?"),
          ("Ung thư tế bào biểu mô thận tiến triển", "Giai đoạn tiến triển", 30, "", "Còn ung thư gan thì sao?")],
    396: [("Bệnh bạch cầu tủy mạn (CML)", "Chẩn đoán CML", 80, "", "Còn GIST thì sao?"),
          ("U mô đệm dạ dày ruột (GIST)", "Chẩn đoán GIST", 80, "", "Còn bạch cầu tủy mạn thì sao?")],
    397: [("Bệnh bạch cầu tủy mạn (CML) không dung nạp hoặc kháng Imatinib", "CML; không dung nạp hoặc kháng Imatinib", 80, "", "Nếu chưa dùng Imatinib thì sao?")],
    400: [("U lympho không phải Hodgkin tế bào B có CD20 dương tính", "U lympho không Hodgkin tế bào B; CD20 dương tính", None, "", "Nếu CD20 âm tính thì sao?")],
    347: [("Bệnh bạch cầu lymphô mạn Binet B/C không phù hợp hóa trị với Fludarabin", "Binet B/C; không phù hợp Fludarabin", 50, "", "Còn u lympho không Hodgkin thì sao?"),
          ("U lymphô không Hodgkin diễn tiến chậm, tiến triển sau điều trị với Rituximab", "Diễn tiến chậm; tiến triển sau Rituximab", 50, "", "Nếu chưa dùng Rituximab thì sao?")],
    385: [("Ung thư dạ dày di căn", "Giai đoạn di căn", 70, "", "Nếu ung thư dạ dày chưa di căn thì sao?")],
    403: [("Ung thư tiền liệt tuyến sau thất bại điều trị nội tiết hoặc hóa trị", "Đã thất bại điều trị nội tiết hoặc hóa trị", 30, "", "Nếu chưa điều trị nội tiết thì sao?")],
    409: [("Không ghi chỉ định riêng trong ghi chú", "Chỉ định theo nhãn/hướng dẫn điều trị (cần xác định)", 50, "", "Fulvestrant dùng cho bệnh nào thì được thanh toán?")],
    362: [("Dạng liposome", "Đúng dạng bào chế liposome", 50, "", "Dạng thường thì sao?"),
          ("Các dạng khác", "Không phải liposome", 100, "", "Dạng liposome thì sao?")],
    381: [("Dạng liposome hoặc polymeric micelle", "Đúng dạng bào chế", 50, "", "Dạng thường thì sao?"),
          ("Các dạng khác", "Không phải liposome/polymeric micelle", 100, "", "Dạng liposome thì sao?")],
    365: [("Điều trị ung thư", "Mục đích điều trị ung thư", 50, "", "Dùng ngoài ung thư thì sao?"),
          ("Các trường hợp khác", "Mục đích khác điều trị ung thư", 100, "", "Dùng điều trị ung thư thì sao?")],
}

PAGES = {347: "30", 362: "30–31", 365: "31", 381: "31", 382: "31–32", 385: "32", 391: "32", 392: "32", 393: "32",
         394: "32–33", 395: "33", 396: "33", 397: "33", 400: "33", 401: "33", 402: "34", 403: "34", 409: "34"}
EMA = {"Trastuzumab": "Herceptin", "Erlotinib": "Tarceva", "Gefitinib": "Iressa"}


def load_rows():
    rows = [json.loads(l) for l in (ROOT / "data/drugs_appendix_I.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    by_stt = {r["stt"]: r for r in rows if r["stt"] in SELECTION}
    assert set(by_stt) == set(SELECTION), "Missing selected TT20 rows"
    for stt, branches in BRANCHES.items():
        note = by_stt[stt]["conditions_verbatim"]
        for b in branches:
            if b[2] is not None:
                assert f"{b[2]}%" in note, f"Rate {b[2]}% not in note for STT {stt}"
    order = [402, 394, 395, 391, 382, 393, 392, 401, 396, 397, 400, 347, 385, 403, 409, 362, 381, 365]
    return [by_stt[s] for s in order]


def hospital_text(r):
    labels = [("hospital_special_I", "Đặc biệt/I"), ("hospital_II", "II"), ("hospital_III_IV", "III/IV"), ("commune", "Xã")]
    return ", ".join(l for k, l in labels if r.get(k) == "+") or "(trống)"


def base_font(ws):
    for row in ws.iter_rows():
        for c in row:
            if c.value is not None and (c.font is None or c.font.name != FONT):
                c.font = Font(name=FONT, size=c.font.size or 10, bold=c.font.bold, color=c.font.color, italic=c.font.italic)


def header(ws, row, titles, widths):
    for i, (t, w) in enumerate(zip(titles, widths), 1):
        c = ws.cell(row=row, column=i, value=t)
        c.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
        c.fill = HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = BORDER
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = 42
    ws.freeze_panes = ws.cell(row=row + 1, column=3)


def banner(ws, text, ncols, fill, row=1):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(name=FONT, bold=True, size=11, color="7A1F1F" if fill is MOCK_FILL else "1F3A5F")
    c.fill = fill
    c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[row].height = 36


def cells(ws, row, values, fill=None):
    for i, v in enumerate(values, 1):
        c = ws.cell(row=row, column=i, value=v)
        c.font = Font(name=FONT, size=10)
        c.alignment = WRAP
        c.border = BORDER
        if fill:
            c.fill = fill


def instructions(ws, title, lines):
    ws.column_dimensions["A"].width = 110
    ws["A1"] = title
    ws["A1"].font = Font(name=FONT, bold=True, size=14, color="1F3A5F")
    for i, line in enumerate(lines, 3):
        c = ws.cell(row=i, column=1, value=line)
        bold = line.isupper() or line.endswith(":")
        c.font = Font(name=FONT, size=10, bold=bold)
        c.alignment = Alignment(wrap_text=True, vertical="top")


def build_drug_list(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Danh sách thuốc"
    titles = ["STT", "Hoạt chất (TT20)", "Biệt dược (GIẢ LẬP)", "Số đăng ký (GIẢ LẬP)", "Đường dùng", "Nhóm",
              "STT Phụ lục I TT20", "Hạng BV có dấu + (cột gốc TT20)", "Ghi chú thanh toán TT20 (nguyên văn)",
              "Lý do đưa vào prototype", "Đối chiếu PDF chính thức", "Biệt dược đã xác minh nguồn"]
    widths = [6, 24, 20, 18, 12, 18, 10, 16, 60, 40, 22, 22]
    banner(ws, "DỮ LIỆU GIẢ LẬP — cột Biệt dược và Số đăng ký là giả, chỉ để chạy thử. Hoạt chất, đường dùng, hạng bệnh viện và ghi chú là dữ liệu thật từ Phụ lục I TT20/2022 (bản hợp nhất 15/VBHN-BYT). Thay bằng danh mục trúng thầu thật của khoa Dược khi có.", len(titles), MOCK_FILL)
    header(ws, 3, titles, widths)
    for i, r in enumerate(rows, 1):
        values = [i, r["ingredient"], f"Biệt dược mẫu {i:02d}", f"GIA-LAP-UB-{i:03d}", r["route"], r["subgroup"],
                  r["stt"], hospital_text(r), r["conditions_verbatim"], SELECTION[r["stt"]],
                  f"Khớp — trang {PAGES[r['stt']]}",
                  (EMA[r["ingredient"]] + " (EMA EPAR)") if r["ingredient"] in EMA else ""]
        cells(ws, 3 + i, values)
        for col in (3, 4):
            ws.cell(row=3 + i, column=col).fill = MOCK_FILL
    ws.cell(row=5 + len(rows), column=1, value="Nguồn: data/drugs_appendix_I.jsonl; đối chiếu bằng mắt với data/sources/15-vbhn-byt-2024.pdf ngày 07/11/2026 (audit/official-crosscheck/oncology-visual-result.json). Biệt dược thật chỉ ghi khi đã xác minh trên trang EMA; chưa xác minh số đăng ký Việt Nam.").font = Font(name=FONT, size=9, italic=True)
    ws.auto_filter.ref = f"A3:{get_column_letter(len(titles))}{3 + len(rows)}"
    base_font(ws)
    wb.save(OUT / "01-danh-sach-thuoc-ung-buou-GIA-LAP.xlsx")


def build_case_form(rows):
    wb = Workbook()
    guide = wb.active
    guide.title = "Hướng dẫn"
    instructions(guide, "Mẫu thu ca bệnh ẩn danh — Prototype chatbot BHYT, khoa Ung bướu", [
        "MỤC ĐÍCH:",
        "Thu 5–10 ca thực tế (ca bị BHXH xuất toán hoặc ca bác sĩ từng phân vân) để kiểm tra chatbot có trả lời đúng như cách Dược/BHYT đã xử lý không. Dữ liệu chỉ dùng làm ca kiểm thử, không đưa vào chatbot để trả lời người khác.",
        "",
        "TUYỆT ĐỐI KHÔNG GHI:",
        "• Họ tên, ngày sinh, địa chỉ, số điện thoại người bệnh.",
        "• Mã bệnh án, mã người bệnh, số thẻ BHYT, số CCCD.",
        "• Ngày khám/ngày ra viện cụ thể (chỉ ghi quý/năm, ví dụ Q2/2025).",
        "• Tên bác sĩ điều trị hoặc tên người bệnh trong phần mô tả.",
        "",
        "CÁCH ĐIỀN:",
        "• Mỗi ca một dòng ở sheet \"Ca bệnh\". Ô nền vàng là ô cần điền; ô có mũi tên là danh sách chọn.",
        "• Mã ca tự đặt theo thứ tự: UB-001, UB-002…",
        "• Hoạt chất: chọn trong danh sách 18 thuốc của prototype, hoặc gõ tên khác nếu cần.",
        "• Xét nghiệm/dấu ấn: ghi đúng kết quả liên quan điều kiện thanh toán (HER2, EGFR, RAS, CD20, Binet…); ghi \"Chưa làm\" nếu chưa có.",
        "• Kết quả thanh toán và lý do: ghi đúng như biên bản giám định BHXH hoặc kết luận của phòng BHYT.",
        "• Dòng 5 (nền xanh) là VÍ DỤ GIẢ LẬP để tham khảo cách ghi. Xóa dòng này trước khi gửi lại.",
        "",
        "TRƯỚC KHI GỬI LẠI, KIỂM TRA:",
        "☐ Đã xóa dòng ví dụ.   ☐ Không còn tên, mã, số thẻ, ngày cụ thể.   ☐ Đã được trưởng khoa / phòng BHYT đồng ý chia sẻ dữ liệu ẩn danh.",
        "",
        "Liên hệ: (điền tên người phụ trách prototype)",
    ])
    ws = wb.create_sheet("Ca bệnh")
    titles = ["Mã ca", "Nguồn ca", "Thời điểm (quý/năm)", "Hoạt chất", "Biệt dược / số đăng ký (nếu biết)", "Đường dùng",
              "Chẩn đoán (mô tả)", "Mã ICD-10", "Giai đoạn / mức độ", "Xét nghiệm / dấu ấn liên quan",
              "Bối cảnh điều trị (tuyến, thuốc đã dùng trước)", "Kết quả thanh toán", "Lý do / căn cứ BHXH hoặc BHYT nêu",
              "Bác sĩ thắc mắc điều gì", "Người cung cấp (khoa / vai trò)", "Ghi chú"]
    widths = [9, 18, 12, 22, 22, 12, 30, 10, 18, 26, 30, 20, 36, 30, 20, 20]
    banner(ws, "Không ghi tên, mã bệnh án, số thẻ BHYT hay ngày cụ thể. Ô nền vàng cần điền; dòng 5 là ví dụ giả lập — xóa trước khi gửi.", len(titles), EXAMPLE_FILL)
    header(ws, 4, titles, widths)
    example = ["UB-000 (ví dụ)", "Bác sĩ phân vân", "Q1/2026", "Trastuzumab", "", "Tiêm", "Ung thư vú, đã phẫu thuật",
               "C50.9", "Giai đoạn II", "HER2 IHC 2+, FISH chưa làm", "Điều trị bổ trợ sau phẫu thuật",
               "Chưa rõ", "Chưa nộp hồ sơ; phân vân vì HER2 chưa khẳng định dương tính",
               "IHC 2+ chưa có FISH có được coi là HER2 dương tính để BHYT thanh toán 60% không?", "Ung bướu / bác sĩ điều trị",
               "VÍ DỤ GIẢ LẬP — xóa dòng này"]
    cells(ws, 5, example, EXAMPLE_FILL)
    for r in range(6, 26):
        cells(ws, r, [""] * len(titles), INPUT_FILL)
    lists = wb.create_sheet("Danh mục chọn")
    lists["A1"] = "Hoạt chất prototype"
    lists["B1"] = "Nguồn ca"
    lists["C1"] = "Kết quả thanh toán"
    lists["D1"] = "Đường dùng"
    for i, r in enumerate(rows, 2):
        lists.cell(row=i, column=1, value=r["ingredient"])
    for i, v in enumerate(["Xuất toán BHXH", "Bác sĩ phân vân", "Dược/BHYT tư vấn", "Khác"], 2):
        lists.cell(row=i, column=2, value=v)
    for i, v in enumerate(["Được thanh toán", "Xuất toán toàn bộ", "Xuất toán một phần", "Chưa nộp / chưa rõ"], 2):
        lists.cell(row=i, column=3, value=v)
    for i, v in enumerate(["Tiêm", "Tiêm truyền", "Uống", "Khác"], 2):
        lists.cell(row=i, column=4, value=v)
    for col in "ABCD":
        lists[f"{col}1"].font = Font(name=FONT, bold=True)
        lists.column_dimensions[col].width = 30
    lists.sheet_state = "hidden"
    n = len(rows) + 1
    for col, ref, strict in (("D", f"'Danh mục chọn'!$A$2:$A${n}", False), ("B", "'Danh mục chọn'!$B$2:$B$5", True),
                             ("L", "'Danh mục chọn'!$C$2:$C$5", True), ("F", "'Danh mục chọn'!$D$2:$D$5", False)):
        dv = DataValidation(type="list", formula1=ref, allow_blank=True)
        dv.errorStyle = "stop" if strict else "warning"
        dv.error = "Chọn trong danh sách." if strict else "Giá trị ngoài danh sách — vẫn có thể giữ nếu đúng."
        dv.showErrorMessage = True
        ws.add_data_validation(dv)
        dv.add(f"{col}6:{col}200")
    ws["C4"].comment = Comment("Chỉ ghi quý/năm (ví dụ Q2/2025), không ghi ngày cụ thể để tránh nhận diện người bệnh.", "Prototype")
    ws["J4"].comment = Comment("Ghi kết quả liên quan điều kiện thanh toán: HER2, EGFR, RAS, CD20, Binet… Ghi 'Chưa làm' nếu chưa có.", "Prototype")
    base_font(ws)
    base_font(guide)
    wb.save(OUT / "02-mau-thu-ca-benh-an-danh.xlsx")


def build_review(rows):
    wb = Workbook()
    guide = wb.active
    guide.title = "Hướng dẫn"
    instructions(guide, "Bảng duyệt điều kiện thanh toán BHYT — 18 thuốc khoa Ung bướu (prototype)", [
        "AI SOẠN, AI DUYỆT:",
        "Các nhánh điều kiện trong sheet \"Duyệt điều kiện\" do nhóm prototype soạn bằng cách tách nguyên văn ghi chú Phụ lục I TT20/2022. Mỗi tỷ lệ % đều có trong nguyên văn; chatbot chỉ dùng nhánh đã được Dược/BHYT đồng ý.",
        "",
        "NGUỒN ĐÃ ĐỐI CHIẾU:",
        "Ghi chú, đường dùng và cột hạng bệnh viện của 18 thuốc đã được so bằng mắt với bản hợp nhất chính thức 15/VBHN-BYT (datafiles.chinhphu.vn), trang 30–34: 18/18 khớp. Việc đối chiếu do Đỗ Quốc An thực hiện, cần Dược/BHYT xác nhận lại.",
        "",
        "CÁCH DUYỆT (chỉ điền các cột nền vàng, từ cột N):",
        "• Kết luận: chọn Đồng ý / Cần sửa / Không đồng ý.",
        "• Nếu Cần sửa: ghi nội dung đúng vào cột \"Sửa thành\" (chỉ định, điều kiện, tỷ lệ hoặc câu gợi ý).",
        "• Ghi chú người duyệt: căn cứ bổ sung (công văn, hướng dẫn BHXH, thực tế giám định tại bệnh viện).",
        "• Ghi họ tên/chức danh người duyệt và ngày duyệt cho từng dòng.",
        "",
        "CẦN ĐẶC BIỆT LƯU Ý:",
        "• Ô \"Tỷ lệ\" để trống nghĩa là ghi chú KHÔNG ghi tỷ lệ (ví dụ Rituximab). Chatbot sẽ không tự hiểu là 100%; xin người duyệt nêu cách hiểu đúng.",
        "• Thuốc chỉ ghi \"thanh toán 50%\" mà không ghi chỉ định (Afatinib, Bevacizumab, Fulvestrant): xin xác định phạm vi chỉ định được chấp nhận (theo nhãn? theo hướng dẫn BYT?).",
        "• Cột hạng bệnh viện là dữ liệu gốc TT20; phải đọc cùng TT37/2024 và hướng dẫn áp dụng, không dùng riêng dấu +.",
        "• Tỷ lệ là tỷ lệ thanh toán của thuốc, không phải mức hưởng BHYT của người bệnh.",
    ])
    ws = wb.create_sheet("Duyệt điều kiện")
    titles = ["Mã nhánh", "Hoạt chất", "STT TT20", "Đường dùng", "Hạng BV có dấu +", "Ghi chú TT20 (nguyên văn)",
              "Trang PDF chính thức", "Nhánh: chỉ định / phạm vi (đề xuất)", "Thông tin bác sĩ cần xác nhận",
              "Tỷ lệ ghi trong nguồn (%)", "Điều kiện cơ sở", "Câu hỏi gợi ý cho chatbot", "Trạng thái",
              "Kết luận duyệt", "Sửa thành", "Ghi chú người duyệt", "Người duyệt (họ tên, chức danh)", "Ngày duyệt"]
    widths = [10, 20, 8, 11, 14, 50, 9, 36, 30, 10, 26, 28, 14, 14, 30, 30, 22, 12]
    banner(ws, "Bản nháp do Đỗ Quốc An tách từ nguyên văn TT20 — chưa có giá trị áp dụng cho đến khi Dược/BHYT duyệt. Chỉ điền các cột nền vàng (N–R).", len(titles), MOCK_FILL)
    header(ws, 3, titles, widths)
    row = 4
    for r in rows:
        for j, (scope, info, rate, facility, suggestion) in enumerate(BRANCHES[r["stt"]], 1):
            values = [f"{r['stt']}-{j}", r["ingredient"], r["stt"], r["route"], hospital_text(r), r["conditions_verbatim"],
                      PAGES[r["stt"]], scope, info, rate if rate is not None else None, facility or "—", suggestion,
                      "Chờ duyệt", "", "", "", "", ""]
            cells(ws, row, values)
            if rate is None:
                ws.cell(row=row, column=10).comment = Comment("Ghi chú nguồn không ghi tỷ lệ. Không suy ra 100%.", "Prototype")
            for col in range(14, 19):
                ws.cell(row=row, column=col).fill = INPUT_FILL
            row += 1
    dv = DataValidation(type="list", formula1='"Đồng ý,Cần sửa,Không đồng ý"', allow_blank=True)
    dv.error = "Chọn Đồng ý, Cần sửa hoặc Không đồng ý."
    dv.showErrorMessage = True
    ws.add_data_validation(dv)
    dv.add(f"N4:N{row - 1}")
    date_dv = DataValidation(type="date", operator="greaterThan", formula1="45000", allow_blank=True)
    date_dv.error = "Nhập ngày (dd/mm/yyyy)."
    date_dv.showErrorMessage = True
    ws.add_data_validation(date_dv)
    date_dv.add(f"R4:R{row - 1}")
    for rr in range(4, row):
        ws.cell(row=rr, column=18).number_format = "dd/mm/yyyy"
    ws.auto_filter.ref = f"A3:{get_column_letter(len(titles))}{row - 1}"
    ws.cell(row=row + 1, column=1, value="Nguồn: Phụ lục I TT20/2022 theo bản hợp nhất 15/VBHN-BYT (data/sources/15-vbhn-byt-2024.pdf). Tỷ lệ % được kiểm tự động là có trong nguyên văn ghi chú khi tạo file.").font = Font(name=FONT, size=9, italic=True)
    base_font(ws)
    base_font(guide)
    wb.save(OUT / "03-mau-duyet-dieu-kien-thanh-toan.xlsx")
    return row - 4


def main():
    OUT.mkdir(exist_ok=True)
    rows = load_rows()
    build_drug_list(rows)
    build_case_form(rows)
    n = build_review(rows)
    print(f"Built 3 workbooks: {len(rows)} drugs, {n} draft branches -> {OUT}")


if __name__ == "__main__":
    main()
