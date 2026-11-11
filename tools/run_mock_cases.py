"""Run the mock case set (data/mock_cases.json) through the chatbot and compare outcomes.

The cases are synthetic. The expected outcome of each was read from the legal text, so the
score says whether the chatbot is consistent with the text; it says nothing about what the
insurer actually paid. Writes audit/MOCK_CASES_RESULT.json and, when openpyxl is available,
prototype/04-ca-thu-GIA-LAP.xlsx in the layout of the case form (02).

    python tools/run_mock_cases.py
"""
import datetime as dt
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TODAY = dt.date(2026, 11, 10)      # fixed, so "cách 90 ngày" is the same on every run


def outcome(reply):
    """One of the outcome words of the case set, from a chatbot reply."""
    labs = reply.get("lab_results") or []
    if labs:
        return {"source_conditions_match": "khớp", "source_condition_not_met": "không khớp", "needs_review": "cần đối chiếu thêm",
                "needs_confirmation": "cần xác nhận", "needs_info": "cần xác nhận"}.get(labs[0]["status"], "chỉ nêu điều kiện/tỷ lệ")
    results = reply.get("results") or []
    if not results:
        return "ngoài danh mục" if reply.get("domain") == "lab" else "chưa có căn cứ"
    answer = results[0].get("question_answer") or {}
    status = answer.get("status")
    if status == "source_condition_not_met":
        return "không khớp"
    if status == "conditional_coverage":
        if answer.get("all_requirements_met"):
            return "khớp"
        return "cần xác nhận" if answer.get("requirements") else "khớp"
    if status == "source_conditions":
        return "chỉ nêu điều kiện/tỷ lệ"
    return "chưa có căn cứ"


def run(corpus=None):
    from engine import Corpus
    corpus = corpus or Corpus()
    bundle = json.loads((ROOT / "data/mock_cases.json").read_text(encoding="utf-8"))
    rows = []
    for case in bundle["cases"]:
        with patch("lab_lookup.local_today", return_value=TODAY):
            reply = corpus.converse(case["question"])
        got = outcome(reply)
        rows.append({**case, "got": got, "ok": got == case["expected"], "answer": (reply.get("answer") or "")[:400]})
    return bundle, rows


def write_workbook(bundle, rows):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        return None
    wb = Workbook()
    ws = wb.active
    ws.title = "Ca thử giả lập"
    titles = ["Mã ca", "Nguồn ca", "Thời điểm (quý/năm)", "Thuốc / xét nghiệm", "Biệt dược / số đăng ký (nếu biết)", "Đường dùng", "Chẩn đoán (mô tả)", "Mã ICD-10",
              "Giai đoạn / mức độ", "Xét nghiệm / dấu ấn liên quan", "Bối cảnh điều trị", "Kết quả thanh toán", "Lý do / căn cứ", "Bác sĩ thắc mắc điều gì",
              "Người cung cấp", "Ghi chú", "Câu hỏi gõ vào chatbot", "Kết quả mong đợi (theo văn bản)", "Chatbot trả lời", "Đạt"]
    ws.append(["GIẢ LẬP — không ca nào là ca thật. Kết quả mong đợi suy ra từ nguyên văn văn bản, không phải quyết định của BHXH."])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(titles))
    ws["A1"].fill = PatternFill("solid", fgColor="FDE9D9"); ws["A1"].font = Font(name="Arial", bold=True)
    ws.append([])
    ws.append(titles)
    for cell in ws[3]:
        cell.font = Font(name="Arial", bold=True); cell.fill = PatternFill("solid", fgColor="D9E1F2")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for r in rows:
        ws.append([r["id"], "Giả lập", "Q4/2026", r["item"], "", r["route"], r["diagnosis"], r["icd10"], r["stage"], r["markers"], r["context"],
                   "Giả lập — chưa có quyết định BHXH", r["basis"], r["doctor_question"], "Nhóm dự án", "CA GIẢ LẬP", r["question"], r["expected"], r["got"],
                   "Đạt" if r["ok"] else "Chưa đạt"])
    for row in ws.iter_rows(min_row=4):
        for cell in row:
            cell.font = Font(name="Arial"); cell.alignment = Alignment(wrap_text=True, vertical="top")
    for i, width in enumerate([9, 10, 10, 26, 14, 10, 28, 9, 16, 28, 24, 22, 44, 34, 12, 12, 54, 20, 20, 9], 1):
        ws.column_dimensions[ws.cell(row=3, column=i).column_letter].width = width
    ws.freeze_panes = "B4"
    out = ROOT / "prototype/04-ca-thu-GIA-LAP.xlsx"
    wb.save(out)
    return out


def main():
    bundle, rows = run()
    passed = sum(r["ok"] for r in rows)
    result = {"date": dt.date.today().isoformat(), "nature": bundle["nature"], "cases": len(rows), "consistent_with_text": passed,
              "by_expected": {o: [sum(r["expected"] == o for r in rows), sum(r["expected"] == o and r["ok"] for r in rows)] for o in bundle["outcomes"]},
              "rows": [{k: r[k] for k in ("id", "kind", "item", "question", "expected", "got", "ok")} for r in rows]}
    (ROOT / "audit/MOCK_CASES_RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for r in rows:
        print(("OK  " if r["ok"] else "SAI ") + f'{r["id"]}  mong đợi: {r["expected"]:<24} chatbot: {r["got"]:<24} {r["question"][:70]}')
    print(f"{passed}/{len(rows)} ca giả lập nhất quán với văn bản.")
    book = write_workbook(bundle, rows)
    if book:
        print("Đã ghi", book)
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
