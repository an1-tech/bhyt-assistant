import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Corpus, read_jsonl
from source_review import apply_source_review
from retrieval import ContextIndex, prepare_chunks, DRUG_KINDS


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()
        cls.raw = read_jsonl(cls.c.data / "rag_current.jsonl")

    def test_every_article_child_expands_to_all_available_pages(self):
        for article in (2, 3, 5, 8, 10, 13, 15, 16, 17, 19):
            expected = [x for x in self.c.chunks if x.get("document_id") == "TT37_2024"
                        and x.get("article") == article]
            for seed in expected:
                with self.subTest(article=article, seed=seed["id"]):
                    actual = self.c.context_index.expand([seed])
                    self.assertEqual([x["id"] for x in actual], [x["id"] for x in expected])

    def test_drug_answer_contains_later_conditions_and_exclusions(self):
        result = self.c.chat("Paracetamol")
        ids = {x["id"] for x in result["citations"]}
        self.assertTrue({"TT37_2024-P5-S1754-1", "TT37_2024-P6-S0-1",
                         "TT37_2024-P7-S0-1", "TT37_2024-P7-S1670-1",
                         "TT37_2024-P8-S0-1", "TT37_2024-P16-S868-1"} <= ids)
        self.assertEqual(result["status"], "needs_info")

    def test_oncology_includes_full_guidance_not_only_question_fragment(self):
        result = self.c.chat("Trastuzumab")
        ids = {x["id"] for x in result["citations"]}
        self.assertTrue({f"CV3293_2025-UTF8-C{i}" for i in range(1, 5)} <= ids)
        self.assertIn("TT37_2024-P9-S41-1", ids)

    def test_guidance_expansion_reconnects_answer_across_boundary(self):
        for doc, count in (("CV3293_2025", 4), ("CV5079_2025", 3)):
            seeds = [x for x in self.c.chunks if x["document_id"] == doc]
            for seed in seeds:
                actual = self.c.context_index.expand([seed])
                self.assertEqual(len(actual), count)
                self.assertTrue(all(x["document_id"] == doc for x in actual))

    def test_appendix_boundaries_are_not_article_21(self):
        corrected = [x for x in self.c.chunks if x.get("metadata_correction")]
        self.assertEqual(len(corrected), 5)
        self.assertEqual({x["page"] for x in corrected}, {18, 19, 20, 21})
        for x in corrected:
            self.assertIsNone(x["article"])
            self.assertEqual(x["source_article"], 21)
            self.assertIn("Phụ lục", x["locator"])
        seed = self.c.by_chunk["TT37_2024-P16-S2187-1"]
        self.assertEqual([x["page"] for x in self.c.context_index.expand([seed])], [16, 17])

    def test_appendix_expansion_stays_in_its_own_appendix(self):
        seed = self.c.by_chunk["TT37_2024-P18-S0-2"]
        actual = self.c.context_index.expand([seed])
        self.assertEqual([x["page"] for x in actual], [18, 18, 19, 20])
        self.assertTrue(all(x["appendix"] == 1 for x in actual))

    def test_all_source_text_ids_urls_and_drug_records_preserved(self):
        source = {x["id"]: x for x in (apply_source_review(self.raw, self.c.data / "source_review.json") + self.c.transition_chunks) if self.c.allowed(x)}
        self.assertEqual(set(source), set(self.c.by_chunk))
        for id, derived in self.c.by_chunk.items():
            for key in ("text", "page", "source_url", "official_url"):
                self.assertEqual(derived.get(key), source[id].get(key), (id, key))
            if derived["kind"] in DRUG_KINDS:
                self.assertEqual(derived, source[id])

    def test_preparation_does_not_mutate_raw_and_is_deterministic(self):
        before = json.dumps(self.raw, ensure_ascii=False)
        first = prepare_chunks(self.raw)
        self.assertEqual(first, prepare_chunks(self.raw))
        self.assertEqual(before, json.dumps(self.raw, ensure_ascii=False))

    def test_no_expansion_to_other_drug_route(self):
        for c in self.c.chunks:
            if c["kind"] in DRUG_KINDS:
                self.assertEqual(self.c.context_index.expand([c]), [c])

    def test_expansion_cannot_reintroduce_filtered_or_forged_sources(self):
        removed = dict(self.c.by_chunk["TT37_2024-P6-S0-1"], id="excluded", default_retrieve=False)
        active = [c for c in [removed, self.c.by_chunk["TT37_2024-P5-S1754-1"]] if self.c.allowed(c)]
        index = ContextIndex(active)
        self.assertEqual(index.expand([removed]), [])
        self.assertEqual(len(index.expand(active)), 1)

    def test_parent_scope_separates_documents_and_extraction_versions(self):
        a = dict(self.c.by_chunk["TT37_2024-P6-S0-1"])
        b = dict(a, id="different-doc", document_id="DIFFERENT")
        d = dict(a, id="different-source", source_url="https://example.org/different-version")
        index = ContextIndex([a, b, d])
        self.assertEqual(index.expand([a]), [a])

    def test_search_limits_distinct_parents_not_duplicate_pages(self):
        query = "thanh toán thuốc vượt hạng bệnh viện"
        seeds = self.c.search(query, 4, True, distinct_parents=True)
        parents = {self.c.context_index.parent[c["id"]] for c in seeds}
        self.assertEqual(len(parents), 4)
        self.assertEqual(self.c.policy_search(query, 4), self.c.context_index.expand(seeds))
        self.assertEqual(self.c.search(query, 0), [])

    def test_policy_chat_returns_complete_selected_parent_context(self):
        result = self.c.chat("thuốc sử dụng khám chữa bệnh từ xa")
        self.assertEqual(result["status"], "policy_lookup")
        actual = {c["id"] for c in result["citations"]}
        for id in actual:
            parent_ids = {c["id"] for c in self.c.context_index.expand([self.c.by_chunk[id]])}
            self.assertTrue(parent_ids <= actual)
        self.assertEqual(len(actual), len(result["citations"]))

    def test_semantic_hits_expand_before_the_ai_receives_evidence(self):
        seed = self.c.by_chunk["TT37_2024-P10-S0-1"]
        fake = {"output": [{"type": "message", "content": [{"type": "output_text",
                "text": json.dumps({"summary": "Cần đối chiếu căn cứ.", "source_ids": [seed["id"]]})}]}]}
        with patch.dict(os.environ, {"BHYT_ENABLE_AI": "1", "OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"}), \
             patch.object(self.c, "semantic_search", return_value=[seed]), \
             patch("engine.api_post", return_value=fake) as api:
            result = self.c.chat("Paracetamol")
        supplied = json.loads(api.call_args.args[1]["input"])["evidence"]
        ids = {x["id"] for x in supplied}
        self.assertTrue({"TT37_2024-P9-S1407-1", "TT37_2024-P10-S0-1"} <= ids)
        self.assertEqual(result["mode"], "ai")
        self.assertEqual(result["status"], "needs_info")

    def test_oversize_ai_context_is_not_silently_truncated(self):
        evidence = [dict(self.c.chunks[0], text="x" * 60001)]
        with patch.dict(os.environ, {"BHYT_ENABLE_AI": "1", "OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"}), \
             patch.object(self.c, "semantic_search", return_value=[]), patch("engine.api_post") as api:
            result = self.c.add_ai({"state": {}}, "thuốc", evidence)
        api.assert_not_called()
        self.assertNotIn("ai_explanation", result)
        self.assertEqual(len(result["citations"][0]["excerpt"]), 60001)
        self.assertIn("quá dài", result["notice"])


if __name__ == "__main__":
    unittest.main()
