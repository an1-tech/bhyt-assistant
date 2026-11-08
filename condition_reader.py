"""Read what a question says about each payment condition.

Each requirement gets one of: "met", "not_met", "unknown" or None (not mentioned).
- The question is split into turns (earlier follow-ups first) and each turn into
  clauses (commas, semicolons, "nhưng"…). The LAST clause that says something
  about a requirement wins, so "Nếu RAS tự nhiên thì sao?" overrides an earlier
  "RAS đột biến".
- Inside a clause the order is unknown → not_met → met. Negation is scoped by the
  patterns themselves ("không có đột biến RAS" is met, "đột biến RAS" is not_met).
- "any_of" requirements (A hoặc B) are met if any part is met and not_met only
  when every part is not_met.
"""
import re

UNKNOWN = r"(?:chua biet|khong ro|chua ro|chua xac dinh|chua lam|chua xet nghiem|chua co ket qua|dang cho ket qua)"
CLAUSE_SPLIT = re.compile(r"[,;.!?\n]|\b(?:nhưng|tuy nhiên|song|nhung|tuy nhien)\b", re.I)


def _norm(text):
    from engine import normalize
    return normalize(text).replace("her 2", "her2")


def clauses(turns):
    """Yield (normalized, raw) clauses in reading order across all turns."""
    for turn in turns:
        for raw in CLAUSE_SPLIT.split(turn or ""):
            q = _norm(raw)
            if q:
                yield q, raw


def _marker_status(q, raw, m):
    """Default reader for biomarker markers (HER2, EGFR, CD20)."""
    if (re.search(UNKNOWN + r"[a-z0-9 ]{0,30}\b" + m + r"\b", q)
            or re.search(r"\b" + m + r"\b[a-z0-9 ]{0,20}" + UNKNOWN, q)
            or re.search(r"\b" + m + r"\b[a-z0-9 ]{0,30}\b(?:hay|hoac)\b", q)
            or re.search(r"\b" + m + r" (?:ihc )?2\b", q)):
        return "unknown"
    negative = [
        r"\b" + m + r" (?:la |co |ket qua |xet nghiem |ihc |fish )*(?:am tinh|am|negative|khong duong tinh|0|1)\b",
        r"\bkhong (?:co |phai |bieu lo |bieu hien |thay |ghi nhan )*(?:xet nghiem |ket qua )?" + m + r"\b",
        r"\b" + m + r" (?:khong|khong co) (?:duong tinh|bieu lo|bieu hien)\b",
    ]
    if m == "her2":
        negative += [r"\bbo ba am tinh\b", r"\btam am\b", r"\btriple negative\b"]
    if any(re.search(p, q) for p in negative) or re.search(m + r"\s*\(\s*-\s*\)|\b" + m + r"\s*-(?![\w-])", raw, re.I):
        return "not_met"
    positive = [r"\b" + m + r" (?:la |co |ket qua |xet nghiem |ihc |fish )*(?:duong tinh|positive|3)\b"]
    if m == "her2":
        positive.append(r"\bfish (?:duong tinh|co khuech dai|khuech dai)\b")
    if any(re.search(p, q) for p in positive) or re.search(m + r"\s*\(\s*\+\s*\)|\b" + m + r"\s*\+", raw, re.I):
        return "met"
    return None


def _pattern_status(q, req):
    unknown = req.get("unknown_patterns") or []
    if any(re.search(p, q) for p in unknown):
        return "unknown"
    if any(re.search(p, q) for p in req.get("negative_patterns", [])):
        return "not_met"
    if any(re.search(p, q) for p in req.get("positive_patterns", [])):
        return "met"
    return None


def _single_status(turns, req):
    status = None
    for q, raw in clauses(turns):
        s = _pattern_status(q, req) if (req.get("negative_patterns") or req.get("positive_patterns")) else _marker_status(q, raw, req["marker"])
        if s:
            status = s
    return status


def requirement_status(turns, req):
    if "any_of" in req:
        parts = [_single_status(turns, sub) for sub in req["any_of"]]
        if "met" in parts:
            return "met"
        if parts and all(p == "not_met" for p in parts):
            return "not_met"
        if any(p in ("unknown", "not_met") for p in parts):
            return "unknown"
        return None
    return _single_status(turns, req)


def choose_formulation(turns, formulations):
    """Return the formulation/purpose branches the question points to (latest clause wins)."""
    chosen = None
    for q, _ in clauses(turns):
        hits = [f for f in formulations
                if any(re.search(p, q) for p in f.get("context_patterns", []))
                and not any(re.search(p, q) for p in f.get("exclude_patterns", []))]
        if hits:
            chosen = hits
    return chosen or []
