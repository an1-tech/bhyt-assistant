"""Coarse cross-check of the imported TT20 drug list against the official consolidated PDF.

The official PDF (15/VBHN-BYT, datafiles.chinhphu.vn) is a scan with a noisy OCR
text layer, so this check can only flag rows for visual review; it cannot prove a
row correct. Usage (needs pypdf):

    python tools/crosscheck_official_pdf.py [pages.json]

Writes audit/official-crosscheck/coarse-results.json.
"""
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "audit/official-crosscheck"


def plain(s):
    s = unicodedata.normalize("NFD", str(s).lower().replace("đ", "d"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9%+]+", " ", s).split())


def load_pages(arg):
    if arg:
        return json.loads(Path(arg).read_text(encoding="utf-8"))
    from pypdf import PdfReader
    return [p.extract_text() or "" for p in PdfReader(ROOT / "data/sources/15-vbhn-byt-2024.pdf").pages]


def best_line_score(name, lines):
    target = plain(name)
    best = 0.0
    for line in lines:
        cand = plain(line)
        if not cand:
            continue
        # OCR often damages the first letter; compare with and without it.
        for c in (cand, cand[1:]):
            r = difflib.SequenceMatcher(None, target, c).ratio()
            if r > best:
                best = r
    return best


def main():
    pages = load_pages(sys.argv[1] if len(sys.argv) > 1 else None)
    rows = [json.loads(l) for l in (ROOT / "data/drugs_appendix_I.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    page_lines = [p.splitlines() for p in pages]
    # Locate the page of each STT using the printed STT column (pages are in STT order).
    stt_pages = {}
    for i, p in enumerate(pages):
        for m in re.finditer(r"(?m)^\s*(\d{1,4})\s*$", p):
            stt_pages.setdefault(int(m.group(1)), set()).add(i)
    results = []
    for r in rows:
        candidates = set()
        for s in (r["stt"] - 1, r["stt"], r["stt"] + 1):
            candidates |= stt_pages.get(s, set())
        window = sorted({j for i in candidates for j in (i - 1, i, i + 1) if 0 <= j < len(pages)}) or list(range(len(pages)))
        lines = [l for j in window for l in page_lines[j]]
        name_score = best_line_score(r["ingredient"], lines)
        rates = re.findall(r"\d+\s*%", r.get("conditions_verbatim", ""))
        text = plain(" ".join(pages[j] for j in window)).replace(" %", "%")
        rates_found = [x for x in rates if x.replace(" ", "") in text]
        results.append({
            "record_id": r["record_id"], "stt": r["stt"], "ingredient": r["ingredient"],
            "group": r["group"][:60], "pages_checked": [j + 1 for j in window][:6],
            "name_score": round(name_score, 2),
            "note_rates": rates, "rates_found_on_page": rates_found,
            "flag": ("name_not_found" if name_score < 0.75 else "")
                    + (" rate_not_found" if rates and len(rates_found) < len(set(rates)) else ""),
        })
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {
        "source_pdf": "data/sources/15-vbhn-byt-2024.pdf (15/VBHN-BYT, datafiles.chinhphu.vn)",
        "method": "Scan PDF với lớp chữ OCR nhiễu: so tên hoạt chất gần đúng (difflib) và tìm tỷ lệ % của ghi chú trên trang có STT tương ứng ±1 trang. Chỉ để khoanh vùng xem lại bằng mắt; không chứng minh dòng đúng.",
        "rows": len(results),
        "name_found": sum(1 for x in results if x["name_score"] >= 0.75),
        "rows_with_rates": sum(1 for x in results if x["note_rates"]),
        "rates_all_found": sum(1 for x in results if x["note_rates"] and "rate_not_found" not in x["flag"]),
        "flagged": sum(1 for x in results if x["flag"]),
    }
    (OUT / "coarse-results.json").write_text(json.dumps({"summary": summary, "rows": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
