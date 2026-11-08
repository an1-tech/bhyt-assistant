"""Source-bound indication rules kept as data, not code.

Every branch must quote the drug-row note verbatim, and its percentage must
appear inside that quotation. A changed source note invalidates the rule.
Kinds:
  indication_branches  one branch per indication (topic), optional requirements
  formulation_note     rate depends on formulation / purpose (axis)
  rate_only            note states a rate (and maybe a facility) but no indication
"""
import hashlib
import json
import re

KINDS = ("indication_branches", "formulation_note", "rate_only")


def _check_quotes(rule_id, note, items):
    for item in items:
        quotes = item.get("verbatim") or []
        if not quotes or not all(isinstance(q, str) and q and q in note for q in quotes):
            raise ValueError("Rule text not found in source note: " + rule_id)
        if item.get("rate") is None:
            # Only allowed when the source itself states no rate; never default to 100%.
            if item.get("rate_stated") is not False or re.search(r"\d+\s*%", note):
                raise ValueError("Rule rate missing: " + rule_id)
            continue
        if not isinstance(item["rate"], int) or f"{item['rate']}%" not in "".join(quotes):
            raise ValueError("Rule rate not quoted from source note: " + rule_id)


def _check_requirement(rule_id, req):
    if not str(req.get("marker", "")).isalnum() or not req.get("label"):
        raise ValueError("Invalid requirement marker: " + rule_id)
    for key in ("negative_patterns", "positive_patterns", "unknown_patterns", "weak_negative_patterns"):
        for pattern in req.get(key, []):
            re.compile(pattern)
    if "any_of" in req:
        if len(req["any_of"]) < 2:
            raise ValueError("any_of needs at least two parts: " + rule_id)
        for sub in req["any_of"]:
            if not (sub.get("negative_patterns") or sub.get("positive_patterns") or sub.get("weak_negative_patterns")):
                raise ValueError("any_of part needs patterns: " + rule_id)
            _check_requirement(rule_id, sub)


def _check_branch_topic(rule_id, note, branch, topics):
    """The quoted text must name the branch's own disease; with several rates in
    the note, disease and rate must sit in the same quoted fragment."""
    from engine import normalize
    pattern = re.compile(r"\b(?:" + topics[branch["topic"]][1] + r")\b")
    quotes = branch["verbatim"]
    if not any(pattern.search(normalize(q)) for q in quotes):
        raise ValueError("Quoted text does not name the branch disease: " + rule_id + " / " + branch["topic"])
    rates = set(re.findall(r"\d+\s*%", note))
    if branch.get("rate") is not None and len(rates) > 1:
        if not any(f"{branch['rate']}%" in q and pattern.search(normalize(q)) for q in quotes):
            raise ValueError("Rate and disease not quoted together: " + rule_id + " / " + branch["topic"])


def load_indication_rules(data, by_id, topics):
    raw = json.loads((data / "indication_rules.json").read_text(encoding="utf-8"))
    if raw.get("version") != 1:
        raise ValueError("Unsupported indication rules")
    names = {r["ingredient"] for r in by_id.values()}
    rules = {}
    for rule in raw["rules"]:
        id = rule["record_id"]
        row = by_id.get(id)
        note = row.get("conditions_verbatim", "") if row else ""
        if not row or row["ingredient"] != rule["ingredient"] or hashlib.sha256(note.encode()).hexdigest() != rule["note_sha256"]:
            raise ValueError("Stale indication rule: " + id)
        if id in rules or rule.get("kind") not in KINDS:
            raise ValueError("Invalid indication rule: " + id)
        if any(d not in names or d not in note for d in rule.get("related_drugs", [])):
            raise ValueError("Related drug must be listed and named in the note: " + id)
        for q in rule.get("common_verbatim", []):
            if q not in note:
                raise ValueError("Rule text not found in source note: " + id)
        if rule["kind"] == "indication_branches":
            branches = rule.get("branches") or []
            if not branches or len({b["topic"] for b in branches}) != len(branches):
                raise ValueError("Invalid indication branches: " + id)
            for b in branches:
                if b["topic"] not in topics:
                    raise ValueError("Unknown indication topic: " + id)
                for req in b.get("requirements", []):
                    _check_requirement(id, req)
            if any(t not in topics for t in rule.get("parent_topics", {})):
                raise ValueError("Unknown parent topic: " + id)
            _check_quotes(id, note, branches)
            for b in branches:
                _check_branch_topic(id, note, b, topics)
        elif rule["kind"] == "formulation_note":
            formulations = rule.get("formulations") or []
            if not formulations:
                raise ValueError("Invalid formulation rule: " + id)
            _check_quotes(id, note, formulations)
        else:
            _check_quotes(id, note, [rule])
        rules[id] = rule
    return raw, rules


def branch_for(rule, topic):
    return next((b for b in rule.get("branches", []) if b["topic"] == topic), None)


def formulation_for(rule, value):
    return next((f for f in rule.get("formulations", []) if f["value"] == value), None)
