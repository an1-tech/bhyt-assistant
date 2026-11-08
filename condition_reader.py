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

UNKNOWN = r"(?:chua biet|khong ro|chua ro|chua xac dinh|chua lam|chua xet nghiem|chua co ket qua|dang cho(?: ket qua)?|khong (?:lam |co )?xet nghiem|khong co ket qua)"
# Markers whose "positive" in the source means a mutation (EGFR): read mutation wording too.
MUTATION_MARKERS = {"egfr"}
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
    if not re.search(r"\b" + m + r"\b", q) and not (m == "her2" and re.search(r"\b(?:fish|bo ba am tinh|tam am|triple negative)\b", q)):
        return None
    if (re.search(UNKNOWN + r"[a-z0-9 ]{0,30}\b" + m + r"\b", q)
            or re.search(r"\b" + m + r"\b[a-z0-9 ]{0,20}" + UNKNOWN, q)
            # "HER2 âm tính hay dương tính", "EGFR có hay không": the result itself is in doubt.
            or re.search(r"\b" + m + r" (?:la |co )?(?:am tinh |duong tinh |co )?(?:hay|hoac) (?:am tinh|duong tinh|khong)\b", q)):
        return "unknown"
    if m == "her2":
        # FISH decides an equivocal IHC 2+.
        if re.search(r"\bfish (?:la |co |ket qua )*(?:am tinh|am|negative|khong khuech dai)\b", q):
            return "not_met"
        if re.search(r"\bfish (?:la |co |ket qua )*(?:duong tinh|positive|co khuech dai|khuech dai)\b", q):
            return "met"
        if re.search(r"\b" + m + r" (?:ihc )?2\b", q):
            return "unknown"
    # Double negative: "không phải HER2 âm tính".
    if re.search(r"\bkhong phai " + m + r" (?:la )?(?:am tinh|am|negative)\b", q):
        return "met"
    negative = [
        r"\b" + m + r" (?:la |co |ket qua |xet nghiem |ihc |fish )*(?:am tinh|am|negative|khong duong tinh|0|1)\b",
        # Explicit negation only ("không có", "không biểu lộ"); a bare "không" may close a yes/no question.
        r"\b(?:khong|chua) (?:co |bieu lo |bieu hien |thay |ghi nhan |phat hien )+(?:xet nghiem |ket qua )?" + m + r"\b",
        r"\b" + m + r" (?:khong|khong co) (?:duong tinh|bieu lo|bieu hien)\b",
    ]
    if m == "her2":
        negative += [r"\bbo ba am tinh\b", r"\btam am\b", r"\btriple negative\b"]
    if m in MUTATION_MARKERS:
        negative += [r"\b" + m + r" (?:tu nhien|hoang da|wild ?type|khong (?:co )?dot bien|binh thuong)\b",
                     r"\b(?:khong|chua) (?:co |phat hien |thay |ghi nhan )*dot bien (?:gen )?" + m + r"\b"]
    if any(re.search(p, q) for p in negative) or re.search(m + r"\s*\(\s*-\s*\)|\b" + m + r"\s*-(?![\w-])", raw, re.I):
        return "not_met"
    positive = [r"\b" + m + r" (?:la |co |ket qua |xet nghiem |ihc |fish )*(?:duong tinh|positive|3)\b"]
    if m in MUTATION_MARKERS:
        positive += [r"\b(?:co )?dot bien (?:gen )?" + m + r"\b", r"\b" + m + r" (?:co )?dot bien\b",
                     r"\b" + m + r" (?:exon |ex )?(?:19|21|l858r|del ?19)\b", r"\b(?:l858r|del ?19|exon 19|exon 21)\b"]
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
    # Weak cues ("đầu tay", "lần đầu") count only when nothing explicit was said.
    if any(re.search(p, q) for p in req.get("weak_negative_patterns", [])):
        return "weak_not_met"
    return None


def _single_status(turns, req):
    status = weak = None
    for q, raw in clauses(turns):
        s = _pattern_status(q, req) if (req.get("negative_patterns") or req.get("positive_patterns") or req.get("weak_negative_patterns")) else _marker_status(q, raw, req["marker"])
        if s == "weak_not_met":
            weak = "not_met"
        elif s:
            status = s
    # An explicit statement anywhere beats a weak cue in another clause.
    return status or weak


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
