"""PDF page of each TT20 row, only where the page was checked by eye.

Inputs (visual checks of data/sources/15-vbhn-byt-2024.pdf, the official 15/VBHN-BYT):
  audit/source-review/rate-verification.json         rows whose note states a rate
  audit/official-crosscheck/oncology-visual-check.json 18 oncology rows (+ visual result)
The coarse OCR scan (audit/official-crosscheck/coarse-results.json) is NOT used: it only
narrows where to look and proves nothing. Rows without a checked page get no page.

    python tools/build_source_pages.py
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = "data/sources/15-vbhn-byt-2024.pdf"


def main():
    rows = [json.loads(l) for l in (ROOT / "data/drugs_appendix_I.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    by_id = {r["record_id"]: r for r in rows}
    pages = {}

    def put(rid, pp, how):
        pp = sorted({int(p) for p in pp})
        old = pages.get(rid)
        if old and old["pages"] != pp:
            raise SystemExit(f"Page conflict for {rid}: {old['pages']} vs {pp}")
        entry = old or {"pages": pp, "checked_by": []}
        entry["checked_by"] = sorted(set(entry["checked_by"]) | {how})
        pages[rid] = entry

    for x in json.loads((ROOT / "audit/source-review/rate-verification.json").read_text(encoding="utf-8")):
        if x.get("status") == "matches_visual_check" and x.get("pdf_pages") and x["record_id"] in by_id:
            put(x["record_id"], x["pdf_pages"], "rate-verification")
    check = json.loads((ROOT / "audit/official-crosscheck/oncology-visual-check.json").read_text(encoding="utf-8"))
    result = json.loads((ROOT / "audit/official-crosscheck/oncology-visual-result.json").read_text(encoding="utf-8"))
    if result["summary"]["mismatch"] != 0:
        raise SystemExit("Oncology visual check has mismatches; fix before using its pages.")
    for x in check["rows"]:
        ids = [r["record_id"] for r in rows if r["stt"] == x["stt"] and r.get("appendix", "I") == "I" and r["route"] == x["route"]]
        if len(ids) != 1:
            raise SystemExit(f"STT {x['stt']} ({x['route']}) does not identify one row: {ids}")
        a, _, b = str(x["page"]).replace("–", "-").partition("-")   # "30–31": the row spans two pages
        put(ids[0], range(int(a), int(b or a) + 1), "oncology-visual-check")
    out = {"version": 1, "pdf": "/sources/15-vbhn-byt-2024.pdf", "pdf_sha256": hashlib.sha256((ROOT / PDF).read_bytes()).hexdigest(),
           "document": "Văn bản hợp nhất 15/VBHN-BYT (TT20/2022 và các lần sửa đổi), bản chính thức datafiles.chinhphu.vn",
           "rule": "Chỉ ghi số trang đã đối chiếu bằng mắt với ảnh trang PDF; dòng chưa đối chiếu thì không có số trang.",
           "pages": dict(sorted(pages.items(), key=lambda kv: by_id[kv[0]]["stt"]))}
    (ROOT / "data/source_pages.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(pages), "rows with a checked page")


if __name__ == "__main__":
    main()
