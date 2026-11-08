import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from engine import Corpus
from indication_chat import TOPICS
from indication_rules import load_indication_rules


class IndicationRuleDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=Corpus()
        cls.raw=json.loads((cls.c.data/"indication_rules.json").read_text(encoding="utf-8"))

    def load_variant(self,mutate):
        raw=copy.deepcopy(self.raw);mutate(raw)
        with tempfile.TemporaryDirectory(dir=self.c.data.parent/"audit") as tmp:
            (Path(tmp)/"indication_rules.json").write_text(json.dumps(raw,ensure_ascii=False),encoding="utf-8")
            return load_indication_rules(Path(tmp),self.c.by_id,TOPICS)

    def test_every_rate_is_quoted_from_the_source_note(self):
        _,rules=load_indication_rules(self.c.data,self.c.by_id,TOPICS)
        self.assertEqual(len(rules),18)
        for id,rule in rules.items():
            note=self.c.by_id[id]["conditions_verbatim"]
            items=rule.get("branches",[])+rule.get("formulations",[])+([rule] if rule["kind"]=="rate_only" else [])
            for item in items:
                if item["rate"] is None:
                    self.assertNotRegex(note,r"\d+\s*%")
                else:
                    self.assertIn(f"{item['rate']}%",note)
                self.assertTrue(all(q in note for q in item["verbatim"]))

    def test_missing_rate_cannot_be_left_blank_when_note_has_one(self):
        def bad(raw):raw["rules"][0]["branches"][0].update(rate=None,rate_stated=False)
        with self.assertRaisesRegex(ValueError,"rate missing"):self.load_variant(bad)

    def test_related_drug_must_be_named_in_note(self):
        def bad(raw):raw["rules"][0]["related_drugs"]=["Imatinib"]
        with self.assertRaisesRegex(ValueError,"Related drug"):self.load_variant(bad)

    def test_invented_rate_is_rejected(self):
        def bad(raw):raw["rules"][0]["branches"][0]["rate"]=70
        with self.assertRaisesRegex(ValueError,"rate"):self.load_variant(bad)

    def test_paraphrased_quote_is_rejected(self):
        def bad(raw):raw["rules"][0]["branches"][0]["verbatim"]=["Thanh toán 60% cho ung thư vú"]
        with self.assertRaisesRegex(ValueError,"not found"):self.load_variant(bad)

    def test_changed_source_note_invalidates_rule(self):
        def bad(raw):raw["rules"][1]["note_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"Stale"):self.load_variant(bad)

    def test_unknown_topic_is_rejected(self):
        def bad(raw):raw["rules"][1]["branches"][0]["topic"]="pancreas"
        with self.assertRaisesRegex(ValueError,"topic"):self.load_variant(bad)

    def test_workbench_rate_comes_from_rules(self):
        from case_workbench import CaseWorkbench
        w=CaseWorkbench(self.c)
        r=w.evaluate({"drug_id":"TT20-PLI-0402-R481","facts":{},"answers":{"indication":"gastric","her2":"positive","extent":"advanced"}})
        self.assertEqual(r["candidate_source_rate"]["percentage"],50)
        r=w.evaluate({"drug_id":"TT20-PLI-0381-R459","facts":{},"answers":{"formulation":"polymeric"}})
        self.assertEqual(r["candidate_source_rate"]["percentage"],50)


class SuggestedFollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=Corpus()

    def test_missing_marker_is_offered_as_optional_question(self):
        r=self.c.converse("Trastuzumab điều trị ung thư vú có BHYT?")
        self.assertIn("HER2",[c["label"] for c in r["results"][0]["question_answer"]["confirm"]])
        self.assertIn("Còn ung thư dạ dày thì sao?",r["suggested_followups"])
        self.assertEqual(r["followups"],[]);self.assertFalse(r["requires_patient_details"])

    def test_suggestions_work_as_followups(self):
        first=self.c.converse("Trastuzumab điều trị ung thư vú có BHYT?")
        for q in first["suggested_followups"]:
            r=self.c.converse(q,first["state"])
            self.assertEqual(r["results"][0]["ingredient"],"Trastuzumab",q)
            self.assertNotEqual(r["results"][0]["question_answer"]["status"],"insufficient_evidence",q)

    def test_stated_marker_is_not_suggested_again(self):
        r=self.c.converse("Erlotinib ung thư phổi không phải tế bào nhỏ EGFR dương tính")
        self.assertNotIn("Nếu EGFR âm tính thì sao?",r["suggested_followups"])

    def test_uncovered_disease_suggests_source_branches(self):
        r=self.c.converse("Trastuzumab ung thư tụy có BHYT?")
        self.assertIn("Trastuzumab điều trị ung thư vú thì sao?",r["suggested_followups"])
        self.assertIsNone(r["results"][0]["question_answer"]["source_rate"])

    def test_generic_drug_has_no_invented_suggestion(self):
        self.assertEqual(self.c.converse("Metformin đái tháo đường típ 2")["suggested_followups"],[])

if __name__=="__main__":unittest.main()
