"""Source-bound indication rules kept as data, not code.

Every branch must quote the drug-row note verbatim, and its percentage must
appear inside that quotation. A changed source note invalidates the rule.
"""
import hashlib
import json

KINDS = ("indication_branches", "formulation_note")


def _check_quotes(rule_id, note, items, require_rate=True):
    for item in items:
        quotes = item.get("verbatim") or []
        if not quotes or not all(isinstance(q, str) and q and q in note for q in quotes):
            raise ValueError("Rule text not found in source note: " + rule_id)
        if require_rate and f"{item['rate']}%" not in "".join(quotes):
            raise ValueError("Rule rate not quoted from source note: " + rule_id)


def load_indication_rules(data, by_id, topics):
    raw = json.loads((data / "indication_rules.json").read_text(encoding="utf-8"))
    if raw.get("version") != 1:
        raise ValueError("Unsupported indication rules")
    rules = {}
    for rule in raw["rules"]:
        id = rule["record_id"]
        row = by_id.get(id)
        note = row.get("conditions_verbatim", "") if row else ""
        if not row or row["ingredient"] != rule["ingredient"] or hashlib.sha256(note.encode()).hexdigest() != rule["note_sha256"]:
            raise ValueError("Stale indication rule: " + id)
        if id in rules or rule.get("kind") not in KINDS:
            raise ValueError("Invalid indication rule: " + id)
        if rule["kind"] == "indication_branches":
            branches = rule.get("branches") or []
            if not branches or len({b["topic"] for b in branches}) != len(branches):
                raise ValueError("Invalid indication branches: " + id)
            for b in branches:
                if b["topic"] not in topics or not isinstance(b["rate"], int):
                    raise ValueError("Unknown indication topic: " + id)
                for req in b.get("requirements", []):
                    if not req.get("marker", "").isalnum():
                        raise ValueError("Invalid requirement marker: " + id)
            if any(t not in topics for t in rule.get("parent_topics", {})):
                raise ValueError("Unknown parent topic: " + id)
            _check_quotes(id, note, branches)
            for q in rule.get("common_verbatim", []):
                if q not in note:
                    raise ValueError("Rule text not found in source note: " + id)
        else:
            formulations = rule.get("formulations") or []
            if not formulations:
                raise ValueError("Invalid formulation rule: " + id)
            _check_quotes(id, note, formulations)
        rules[id] = rule
    return raw, rules


def branch_for(rule, topic):
    return next((b for b in rule.get("branches", []) if b["topic"] == topic), None)


def formulation_for(rule, value):
    return next((f for f in rule.get("formulations", []) if f["value"] == value), None)
