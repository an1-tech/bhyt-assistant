"""Reproducible local retrieval audit; no network calls or API key required."""
import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Corpus, ROOT, read_jsonl
from source_review import apply_source_review
from retrieval import RETRIEVAL_VERSION, DRUG_KINDS

def audit():
    # This audit is intentionally offline even if the caller has AI enabled.
    previous = os.environ.get("BHYT_ENABLE_AI")
    os.environ["BHYT_ENABLE_AI"] = "0"
    try:
        c = Corpus()
        raw = read_jsonl(c.data / "rag_current.jsonl")
        baseline = json.loads((ROOT / "audit/CHUNKING_BASELINE.json").read_text(encoding="utf-8"))
        checks = {}
        for query, before in baseline["queries"].items():
            response = c.chat(query)
            after_ids = [x["id"] for x in response["citations"]]
            required = [x["id"] for x in c.chunks if x["document_id"] == "TT37_2024"
                        and x.get("article") in ([8, 10, 12, 20] if query == "Trastuzumab" else [8, 10, 20])]
            checks[query] = {"before": before, "after": {
                "ids": after_ids, "characters": sum(len(x["excerpt"]) for x in response["citations"]),
                "unique_citations": len(after_ids) == len(set(after_ids)),
                "all_selected_parents_complete": all(
                    {x["id"] for x in c.context_index.expand([c.by_chunk[id]])} <= set(after_ids)
                    for id in after_ids)}}
            if query in ("Paracetamol", "Trastuzumab"):
                checks[query]["mandatory_article_parts"] = {
                    "required": len(required), "before": len(set(required) & set(before["ids"])),
                    "after": len(set(required) & set(after_ids))}
        source = {x["id"]: x for x in raw if c.allowed(x)}
        expected={x["id"]:x for x in apply_source_review(raw,c.data/"source_review.json")+c.transition_chunks if c.allowed(x)}
        report = {
            "retrieval_version": RETRIEVAL_VERSION,
            "scope": "Completeness within supplied corpus; not clinical accuracy or source freshness validation",
            "raw_sha256": c.source_fingerprint,
            "effective_sha256": c.fingerprint,
            "raw_unchanged_from_baseline": baseline["raw_sha256"] == c.source_fingerprint,
            "source_chunks": len(raw), "active_chunks": len(c.chunks),
            "active_kinds": dict(Counter(x["kind"] for x in c.chunks)),
            "parent_groups": len(c.context_index.groups),
            "all_original_text_preserved": all(x["text"] == source[x["id"]]["text"] for x in c.chunks if x["id"] in source),
            "only_reviewed_text_changes": all(x["text"]==expected[x["id"]]["text"] for x in c.chunks),
            "supplemental_chunks": len(c.transition_chunks),
            "all_drug_chunks_unchanged": all(x == source[x["id"]] for x in c.chunks if x["kind"] in DRUG_KINDS),
            "metadata_corrections": [
                {key: x.get(key) for key in ("id", "source_locator", "locator", "page", "article", "appendix")}
                for x in c.chunks if x.get("metadata_correction")],
            "evaluation": checks,
            "policy_parents": [g for g in c.context_index.describe() if g["parent"][0] != "chunk"],
            "limitations": [
                "No source re-OCR or full rebuild of original chunks",
                "Inherited OCR errors and legal content remain unvalidated by hospital",
                "Guidance without section metadata expands to full document and may include historical context",
                "TF-IDF ranking unchanged; no semantic ranking quality claim",
                "All tests of AI use mocks; no paid API calls",
                "Article 8 was manually supplemented from the official PDF; other gaps remain",
            ],
        }
        return report
    finally:
        if previous is None:
            os.environ.pop("BHYT_ENABLE_AI", None)
        else:
            os.environ["BHYT_ENABLE_AI"] = previous

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"Audit saved: {args.output}")
    else:
        print(text, end="")
