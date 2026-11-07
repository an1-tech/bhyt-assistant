import copy
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from engine import Corpus, normalize
from transitions import load_transition_bundle, transition_intent

class TransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=Corpus()
        cls.ids=set(cls.c.transition_rules["chunk_ids"])
        cls.article=set(cls.c.transition_rules["article8_ids"])

    def assert_complete(self,result):
        self.assertTrue(self.ids <= {c["id"] for c in result["citations"]})
        self.assertEqual(result["transition_review"]["status"],"source_available_requires_case_review")
        self.assertFalse(result["transition_review"]["eligibility_evaluated"])
        self.assertNotIn("chưa chứa đầy đủ",result["notice"])

    def test_each_linked_drug_gets_full_article_and_date(self):
        for rule in self.c.transition_rules["mapping"].values():
            with self.subTest(drug=rule["ingredient"]):
                result=self.c.chat(rule["ingredient"])
                self.assert_complete(result)
                self.assertEqual(len(result["transition_review"]["linked_drugs"]),1)

    def test_source_retains_every_exception_and_dates(self):
        text="\n".join(c["text"] for c in self.c.transition_chunks if c["article"]==8)
        for phrase in ("1. Trường hợp","2. Đối với","a) Sử dụng","b) Trường hợp","c) Người bệnh","d) Trong","đ) Trường hợp",
                       "trừ trường hợp điều trị ngoại trú trái tuyến","khi tái phát","điều trị thuốc không liên tục",
                       "trước ngày 01 tháng 01 năm 2015","trước ngày 01 tháng 01 năm 2019",
                       "sau ngày 01 tháng 01 năm 2015","40/2014/TT-BYT","và ngược lại"):
            self.assertIn(phrase,text)
        self.assertNotIn("Điều 9.",text)
        self.assertNotIn("Điều 20.",text)
        self.assertIn("01 tháng 3 năm 2023",self.c.transition_chunks[2]["text"])

    def test_either_child_expands_to_both_pages_and_effective_date(self):
        for id in self.article:
            actual=self.c.complete_context([self.c.by_chunk[id]])
            self.assertEqual({x["id"] for x in actual},self.ids)
            article=[x for x in actual if x["article"]==8]
            self.assertEqual([x["page"] for x in article],[4,5])

    def test_generic_transition_queries_without_drug_work(self):
        for q in ("Quy định chuyển tiếp","Điều 8 TT20/2022","Điều 8 thông tư 20",
                  "Nội trú trước ngày 01/03/2023 rồi tiếp tục điều trị"):
            with self.subTest(query=q):
                result=self.c.chat(q)
                self.assertEqual(result["status"],"policy_lookup")
                self.assert_complete(result)

    def test_unrelated_drug_not_linked_to_transition_rate(self):
        for q in ("Paracetamol","Trastuzumab","Amlodipin"):
            result=self.c.chat(q)
            self.assertFalse(result.get("transition_review",{}).get("linked_drugs"))
            self.assertEqual(result["status"],"needs_info")

    def test_original_conditions_are_not_replaced_by_transition_rates(self):
        for id,rule in self.c.transition_rules["mapping"].items():
            result=self.c.chat(rule["ingredient"])
            self.assertEqual(result["results"][0]["conditions"],[self.c.by_id[id]["conditions_verbatim"]])
            self.assertEqual(result["status"],"needs_info")
            self.assertEqual(result["results"][0]["status"],"listed_requires_context")

    def test_mapping_preserves_form_and_indication_boundaries(self):
        by={v["ingredient"]:v for v in self.c.transition_rules["mapping"].values()}
        self.assertIn("liposome",by["Doxorubicin"]["scope"])
        self.assertIn("erwinia",by["L-asparaginase"]["scope"])
        self.assertIn("polymeric micelle",by["Paclitaxel"]["scope"])
        sora=by["Sorafenib"]["branches"]
        self.assertEqual(len(sora),2)
        self.assertEqual(sora[0]["used_before"],"2015-01-01")
        self.assertEqual(sora[1]["used_after"],"2015-01-01")
        self.assertNotIn("gan",sora[1]["indication"])
        self.assertTrue(all(r["continued_after"]=="2023-03-01" for r in by.values()))

    def test_historical_rate_reference_not_invented(self):
        result=self.c.chat("Paclitaxel")
        self.assertIn("TT40/2014",result["notice"])
        self.assertIn("chưa có bảng tỷ lệ lịch sử",result["notice"])
        branches=result["transition_review"]["linked_drugs"][0]["branches"]
        self.assertEqual(branches[0]["rate_reference"],"TT40_2014_external_reference")
        self.assertNotIn("rate_percent",branches[0])

    def test_followup_retains_exact_drug_and_transition_sources(self):
        for q in ("từ năm 2014","tái phát","gián đoạn điều trị","chuyển cơ sở"):
            first=self.c.chat("Erlotinib")
            result=self.c.chat(q,first["state"])
            self.assertEqual(result["results"][0]["ingredient"],"Erlotinib")
            self.assertIn(q,result["state"]["context"])
            self.assert_complete(result)

    def test_multiple_drugs_have_independent_links(self):
        result=self.c.chat("Erlotinib và Paclitaxel và Paracetamol")
        self.assertEqual(len(result["results"]),3)
        linked=result["transition_review"]["linked_drugs"]
        self.assertEqual({r["ingredient"] for r in linked},{"Erlotinib","Paclitaxel"})
        self.assertEqual(len({c["id"] for c in result["citations"]}),len(result["citations"]))

    def test_wrong_route_does_not_claim_transition_match(self):
        result=self.c.chat("Erlotinib tiêm")
        self.assertEqual(result["results"][0]["status"],"route_unmatched")
        self.assertNotIn("transition_review",result)

    def test_transition_evidence_skips_ai_even_when_semantically_added(self):
        with patch.dict(os.environ,{"BHYT_ENABLE_AI":"1","OPENAI_API_KEY":"test-only","OPENAI_MODEL":"test"}):
            with patch("engine.api_post") as api:
                self.c.chat("Điều 8 TT20/2022")
                api.assert_not_called()
            with patch.object(self.c,"semantic_search",return_value=[self.c.by_chunk[next(iter(self.article))]]),patch("engine.api_post") as api:
                result=self.c.chat("Trastuzumab")
                self.assert_complete(result)
                api.assert_not_called()

    def test_changed_supplement_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=self.c.data.parent/"audit/transition-review") as tmp:
            data=Path(tmp)
            for name in ("transition_rules.json","rag_transition.jsonl"):
                shutil.copy2(self.c.data/name,data/name)
            with (data/"rag_transition.jsonl").open("a",encoding="utf8") as f:f.write(" ")
            with self.assertRaisesRegex(ValueError,"text checksum"):
                load_transition_bundle(data,self.c.rows)

    def test_changed_drug_mapping_is_rejected(self):
        rows=copy.deepcopy(self.c.rows)
        id=next(iter(self.c.transition_rules["mapping"]))
        next(r for r in rows if r["record_id"]==id)["ingredient"]="changed"
        with self.assertRaisesRegex(ValueError,"drug mapping"):
            load_transition_bundle(self.c.data,rows)

    def test_explicit_other_article_not_treated_as_tt20_transition(self):
        self.assertFalse(transition_intent(normalize("Điều 8 TT37/2024")))
        self.assertFalse(transition_intent(normalize("chuyển tiếp TT37/2024")))
        self.assertTrue(transition_intent(normalize("chuyển tiếp TT20/2022")))
