"""Read what a question says about each payment condition — conservatively.

Each requirement ends up "met", "not_met", "unknown" or None (not mentioned).
The bot only trusts plain statements; anything unclear becomes "unknown" and the
answer offers confirmation buttons (see indication_chat). A confirmed fact always
beats text reading.

Rules
- Turns are read oldest → newest; the latest turn that says something about a
  requirement wins (a follow-up can replace an earlier assumption).
- Inside a turn, clauses (commas, "nhưng"…) are combined: a definite statement
  beats "unknown"; two opposite definite statements make the requirement
  "unknown" (or "not_met" when the rule says not_met dominates, e.g. any RAS
  mutation excludes "RAS tự nhiên").
- A pattern match preceded (within three words) by "không/chưa/chẳng" that is not
  part of the pattern itself is ambiguous ("chưa thất bại nội tiết",
  "không tiến xa", "không phải Binet B", "không di căn não") and never counts as
  a statement; if nothing else is said, the requirement becomes "unknown".
- Yes/no question tags ("có được BHYT trả không") and disease names that contain
  "không" ("không tế bào nhỏ", "không Hodgkin") are removed before reading.
- "any_of" (A hoặc B): met if any part is met, not_met only when every part is
  not_met, otherwise unknown when anything was said.
"""
import re

UNKNOWN = r"(?:chua biet|khong ro|chua ro|chua xac dinh|chua lam|chua xet nghiem|chua co ket qua|dang cho(?: ket qua)?|khong (?:lam |co )?xet nghiem|khong co ket qua)"
UNKNOWN_NEAR = r"(?: tinh trang| ket qua| xet nghiem)?(?: gen)? "
# Markers whose "positive" in the source means a mutation (EGFR): read mutation wording too.
MUTATION_MARKERS = {"egfr"}
CLAUSE_SPLIT = re.compile(r"[,;.!?\n]|\b(?:nhưng|tuy nhiên|song|nhung|tuy nhien|ma la|mà là)\b", re.I)
NEGATION_WORDS = {"khong", "chua", "chang"}
QUESTION_TAG = re.compile(r"\b(?:co )?(?:duoc )?(?:(?:bhyt|bhxh|bao|hiem|y|te|quy|tra|chi|thanh|toan|huong|duoc) ){1,6}(?:khong|chua)\b")
VALID = ("met", "not_met", "unknown")


def _norm(text):
    from engine import normalize
    return normalize(text).replace("her 2", "her2")


def _strip(q):
    """Remove yes/no question tags and disease names that contain a negation word."""
    from indication_chat import TOPICS
    q = QUESTION_TAG.sub(" ", q)
    if re.search(r"\bco\b", q):
        q = re.sub(r"\s(?:khong|chua)$", "", q)
    for key in ("nsclc", "nhl"):
        q = re.sub(r"\b(?:" + TOPICS[key][1] + r")\b", " benhx ", q)
    return " ".join(q.split())


def clauses(turns):
    """Yield (normalized, raw) clauses in reading order across all turns."""
    for turn in turns:
        for raw in CLAUSE_SPLIT.split(turn or ""):
            q = _strip(_norm(raw))
            if q:
                yield q, raw


def negated_before(q, start, window=3):
    return any(w in NEGATION_WORDS for w in q[:start].split()[-window:])


def _scan(q, negative, positive):
    """Statuses from negative/positive patterns in one clause.
    - A positive match lying inside a negative match ("không có dấu hiệu di căn")
      belongs to the negative and is ignored.
    - A match negated just before it (not by its own pattern) is ambiguous."""
    out, neg_spans = set(), []
    for p in negative:
        for m in re.finditer(p, q):
            if negated_before(q, m.start()):
                out.add("ambiguous")
            else:
                out.add("not_met")
                if m.end() > m.start():
                    neg_spans.append((m.start(), m.end()))
    for p in positive:
        for m in re.finditer(p, q):
            if any(a <= m.start() < b for a, b in neg_spans):
                continue
            out.add("ambiguous" if negated_before(q, m.start()) else "met")
    return out


def _marker_clause(q, raw, m):
    """Default reader for biomarker markers (HER2, EGFR, CD20) in one clause."""
    if not re.search(r"\b" + m + r"\b", q) and not (m == "her2" and re.search(r"\b(?:fish|bo ba am tinh|tam am|triple negative)\b", q)):
        return set()
    if (re.search(UNKNOWN + UNKNOWN_NEAR + m + r"\b", q)
            or re.search(r"\b" + m + r" (?:la |co |ket qua )?" + UNKNOWN, q)
            # "HER2 âm tính hay dương tính", "EGFR có hay không": the result itself is in doubt.
            or re.search(r"\b" + m + r" (?:la |co )?(?:am tinh |duong tinh |co )?(?:hay|hoac) (?:am tinh|duong tinh|khong)\b", q)):
        return {"unknown"}
    if m == "her2":
        # FISH decides an equivocal IHC 2+.
        if re.search(r"\bfish (?:la |co |ket qua )*(?:am tinh|am|negative|khong khuech dai)\b", q):
            return {"not_met"}
        if re.search(r"\bfish (?:la |co |ket qua )*(?:duong tinh|positive|co khuech dai|khuech dai)\b", q):
            return {"met"}
        if re.search(r"\b" + m + r" (?:ihc )?2\b", q):
            return {"unknown"}
    negative = [
        r"\b" + m + r" (?:la |co |ket qua |xet nghiem |ihc |fish )*(?:am tinh|am|negative|khong duong tinh|0|1)\b",
        r"\b(?:khong|chua) (?:co |bieu lo |bieu hien |thay |ghi nhan |phat hien )+(?:xet nghiem |ket qua )?" + m + r"\b",
        r"\b" + m + r" (?:khong|khong co) (?:duong tinh|bieu lo|bieu hien)\b",
    ]
    if m == "her2":
        negative += [r"\bbo ba am tinh\b", r"\btam am\b", r"\btriple negative\b"]
    if m in MUTATION_MARKERS:
        negative += [r"\b" + m + r" (?:tu nhien|hoang da|wild ?type|khong (?:co )?dot bien|binh thuong)\b",
                     r"\b(?:khong|chua) (?:co |phat hien |thay |ghi nhan )*dot bien (?:gen )?" + m + r"\b"]
    positive = [r"\b" + m + r" (?:la |co |ket qua |xet nghiem |ihc |fish )*(?:duong tinh|positive|3)\b"]
    if m in MUTATION_MARKERS:
        positive += [r"\b(?:co )?dot bien (?:gen )?" + m + r"\b", r"\b" + m + r" (?:co )?dot bien\b",
                     r"\b" + m + r" (?:exon |ex )?(?:19|21|l858r|del ?19)\b", r"\b(?:l858r|del ?19|exon 19|exon 21)\b"]
    out = _scan(q, negative, positive)
    if re.search(m + r"\s*\(\s*-\s*\)|\b" + m + r"\s*-(?![\w-])", raw, re.I):
        out.add("not_met")
    if re.search(m + r"\s*\(\s*\+\s*\)|\b" + m + r"\s*\+", raw, re.I):
        out.add("met")
    # "không có đột biến EGFR" also contains the positive "đột biến EGFR": keep the negation.
    if "not_met" in out and "ambiguous" in out:
        out.discard("ambiguous")
    return out


def _pattern_clause(q, req):
    out = set()
    if any(re.search(p, q) for p in req.get("unknown_patterns", [])):
        out.add("unknown")
    out |= _scan(q, req.get("negative_patterns", []), req.get("positive_patterns", []))
    # A negative pattern that embeds the negation ("không di căn") also makes the
    # positive "di căn" inside it look ambiguous; the explicit negative wins.
    if "not_met" in out:
        out.discard("ambiguous")
    if not out and any(re.search(p, q) for p in req.get("weak_negative_patterns", [])):
        out.add("weak")
    return out


def _is_pattern_req(req):
    return bool(req.get("negative_patterns") or req.get("positive_patterns") or req.get("weak_negative_patterns"))


def _turn_single(turn, req):
    found = set()
    for q, raw in clauses([turn]):
        found |= _pattern_clause(q, req) if _is_pattern_req(req) else _marker_clause(q, raw, req["marker"])
    definite = found & {"met", "not_met"}
    if definite == {"met", "not_met"}:
        return "not_met" if req.get("not_met_dominates") else "unknown"
    if definite:
        return definite.pop()
    if found & {"unknown", "ambiguous"}:
        return "unknown"
    if "weak" in found:
        return "not_met"
    return None


def _turn_status(turn, req):
    if "any_of" in req:
        parts = [_turn_single(turn, sub) for sub in req["any_of"]]
        if "met" in parts:
            return "met"
        if parts and all(p == "not_met" for p in parts):
            return "not_met"
        if any(parts):
            return "unknown"
        return None
    return _turn_single(turn, req)


def requirement_status(turns, req, fact=None):
    """Status of one requirement; a confirmed fact (button) wins over text."""
    if fact in VALID:
        return fact
    status = None
    for turn in turns:
        s = _turn_status(turn, req)
        if s:
            status = s
    return status


def choose_formulation(turns, formulations, fact=None):
    """(chosen formulations, state): state is "confirmed", "chosen", "unclear" or None."""
    if fact:
        chosen = [f for f in formulations if f["value"] == fact]
        return chosen, ("confirmed" if chosen else None)
    result, state = [], None
    for turn in turns:
        hits, unclear = [], False
        for q, _ in clauses([turn]):
            if re.search(UNKNOWN + r"|\bhay khong\b|\bhoac khong\b|\bco phai\b.*\bkhong\b", q):
                unclear = True
            for f in formulations:
                if f in hits or any(re.search(p, q) for p in f.get("exclude_patterns", [])):
                    continue
                for p in f.get("context_patterns", []):
                    m = re.search(p, q)
                    if m and not negated_before(q, m.start()):
                        hits.append(f)
                        break
        if hits or unclear:
            result, state = hits, ("unclear" if unclear or len(hits) > 1 else "chosen")
    return (result if state == "chosen" else []), state
