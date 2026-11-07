"""Compare the imported drug rows with a visual transcription of the official PDF.

Input: audit/official-crosscheck/oncology-visual-check.json (human/AI reading of page images).
Output: audit/official-crosscheck/oncology-visual-result.json and a printed summary.
Whitespace and hyphen variants (soft hyphen, '--') are normalised; every other
character difference is reported.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "audit/official-crosscheck"


def canon(s):
    s = str(s).replace("­", "").replace("‑", "-")
    s = re.sub(r"-{2,}", "-", s)
    return " ".join(s.split())


def main():
    check = json.loads((BASE / "oncology-visual-check.json").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in (ROOT / "data/drugs_appendix_I.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    by_stt = {}
    for r in rows:
        by_stt.setdefault(r["stt"], []).append(r)
    results = []
    for v in check["rows"]:
        found = by_stt.get(v["stt"], [])
        diffs = []
        if len(found) != 1:
            diffs.append(f"expected 1 data row, found {len(found)}")
        else:
            r = found[0]
            if r["ingredient"] != v["ingredient"]:
                diffs.append(f"ingredient: data={r['ingredient']!r} pdf={v['ingredient']!r}")
            if canon(r["route"]) != canon(v["route"]):
                diffs.append(f"route: data={r['route']!r} pdf={v['route']!r}")
            data_cols = [r.get(c, "") for c in check["columns"]]
            if data_cols != v["cols"]:
                diffs.append(f"hospital columns: data={data_cols} pdf={v['cols']}")
            if canon(r.get("conditions_verbatim", "")) != canon(v["note"]):
                diffs.append("note text differs")
        results.append({"stt": v["stt"], "ingredient": v["ingredient"], "page": v["page"],
                        "record_id": found[0]["record_id"] if len(found) == 1 else None,
                        "status": "match" if not diffs else "mismatch", "differences": diffs})
    summary = {"checked": len(results), "match": sum(x["status"] == "match" for x in results),
               "mismatch": sum(x["status"] == "mismatch" for x in results),
               "checked_as_of": check["checked_as_of"], "method": check["method"]}
    (BASE / "oncology-visual-result.json").write_text(json.dumps({"summary": summary, "rows": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for x in results:
        if x["differences"]:
            print(x["stt"], x["ingredient"], x["differences"])


if __name__ == "__main__":
    main()
