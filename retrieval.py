"""Parent context for source chunks; never rewrite or synthesize evidence text."""
from __future__ import annotations
import re
import unicodedata

RETRIEVAL_VERSION = "parent-context-v1"
DRUG_KINDS = frozenset(("drug_row", "radiopharmaceutical_row"))


def _plain(text):
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in text if not unicodedata.combining(c))


def prepare_chunks(raw):
    """Repair inherited appendix labels in a derived view, preserving originals.

    Only TT37 PDF legal chunks are eligible. A heading at the start of a
    chunk establishes an appendix boundary; its following pages inherit it.
    Source bytes, IDs, text and page numbers remain unchanged.
    """
    chunks = [dict(c) for c in raw]
    appendix = None
    legal = [c for c in chunks if c.get("document_id") == "TT37_2024"
             and c.get("kind") == "legal_policy" and isinstance(c.get("page"), int)]
    def order(c):
        match = re.search(r"-S(\d+)-(\d+)$", c["id"])
        return (c["page"], *(map(int, match.groups()) if match else (0, 0)))
    for c in sorted(legal, key=order):
        start = _plain(c["text"].lstrip())
        heading = re.match(r"(?:\d+\s+)?phu\s+luc\s+(\d+)\b", start)
        if heading:
            appendix = int(heading.group(1))
        elif re.match(r"(?:\d+\s+)?dieu\s+\d+\.", start):
            appendix = None
        if appendix is not None:
            c["source_article"] = c.get("article")
            c["source_locator"] = c.get("locator")
            c["article"] = None
            c["appendix"] = appendix
            c["kind"] = "legal_annex"
            c["locator"] = f"Trang PDF {c['page']}, Phụ lục {appendix}"
            c["metadata_correction"] = "appendix_heading_boundary"
    return chunks


class ContextIndex:
    """Rank children, then return complete parent groups in source order.

    Articles are scoped by document and extraction URL. Guidance without
    reliable section metadata expands to its full document (only 3–4 chunks
    in this corpus). Drug rows and unmatched fragments remain independent.
    """
    def __init__(self, chunks):
        self.by_id = {c["id"]: c for c in chunks}
        if len(self.by_id) != len(chunks):
            raise ValueError("Duplicate evidence IDs")
        self.groups = {}
        self.parent = {}
        for c in chunks:
            key = self.key(c)
            self.parent[c["id"]] = key
            self.groups.setdefault(key, []).append(c)
        for group in self.groups.values():
            # JSONL order breaks ties and preserves unpaged guidance order.
            group.sort(key=lambda c: c.get("page") or 0)

    @staticmethod
    def key(c):
        scope = (c.get("document_id"), c.get("source_url"))
        if c.get("kind") == "legal_policy" and c.get("article") is not None:
            return scope + ("article", c["article"])
        if c.get("kind") == "legal_annex":
            return scope + ("annex", c["appendix"])
        if c.get("kind") in ("ministry_guidance", "annex_wastage"):
            return scope + (c["kind"],)
        return ("chunk", c["id"])

    def expand(self, seeds):
        result = {}
        for seed in seeds:
            key = self.parent.get(seed.get("id"))
            if key is None:
                continue  # Never reintroduce filtered or external evidence.
            for c in self.groups[key]:
                result.setdefault(c["id"], c)
        return list(result.values())

    def describe(self):
        return [{"parent": list(key), "child_ids": [c["id"] for c in group],
                 "characters": sum(len(c["text"]) for c in group)}
                for key, group in self.groups.items()]
