"""Regression tests for the external review of commit 65de43e (08/11/2026).

Each test reproduces one reported defect; all failed before the fix.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from engine import Corpus, ROOT
from indication_chat import TOPICS
from indication_rules import load_indication_rules


class ReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=Corpus()

    def ask(self,q,state=None):return self.c.converse(q,state)
    def qa(self,r):return r["results"][0]["question_answer"]
    def status(self,q,state=None):return self.qa(self.ask(q,state))["status"]

    # 1. "không có đột biến RAS" means RAS wild-type (met), not RAS-mutated.
    def test_no_ras_mutation_is_met(self):
        for q in ("Cetuximab ung thư đại trực tràng di căn không có đột biến RAS",
                  "Cetuximab ung thư đại trực tràng di căn, không đột biến KRAS",
                  "Cetuximab ung thư đại trực tràng di căn RAS tự nhiên"):
            a=self.qa(self.ask(q))
            self.assertEqual(a["status"],"conditional_coverage",q)
            self.assertIn({"label":"RAS","requires":"RAS tự nhiên (không đột biến)","status":"met"},[{k:v for k,v in x.items() if k!="source"} for x in a["requirements"]],q)
        self.assertEqual(self.status("Cetuximab ung thư đại trực tràng di căn có đột biến KRAS"),"source_condition_not_met")

    # 2. Abiraterone: "nội tiết HOẶC hóa trị" failure.
    def test_abiraterone_or_condition(self):
        self.assertEqual(self.status("Abiraterone ung thư tiền liệt tuyến chưa dùng nội tiết nhưng đã thất bại hóa trị"),"conditional_coverage")
        self.assertEqual(self.status("Abiraterone ung thư tiền liệt tuyến đã thất bại điều trị nội tiết"),"conditional_coverage")
        a=self.qa(self.ask("Abiraterone ung thư tiền liệt tuyến chưa dùng nội tiết"))
        self.assertEqual(a["status"],"conditional_coverage")
        self.assertEqual(a["requirements"][0]["status"],"unknown")
        self.assertEqual(self.status("Abiraterone ung thư tiền liệt tuyến chưa dùng nội tiết hoặc hóa trị"),"source_condition_not_met")

    # 3. One unknown fact must not disable another stated condition.
    def test_unknown_fact_does_not_hide_other_condition(self):
        self.assertEqual(self.status("Cetuximab ung thư đại trực tràng chưa di căn, RAS chưa xác định"),"source_condition_not_met")
        a=self.qa(self.ask("Cetuximab ung thư đại trực tràng di căn, RAS chưa xác định"))
        self.assertEqual(a["status"],"conditional_coverage")
        self.assertIn({"label":"RAS","requires":"RAS tự nhiên (không đột biến)","status":"unknown"},[{k:v for k,v in x.items() if k!="source"} for x in a["requirements"]])

    # 4. A new assumption replaces the old one for the same condition.
    def test_latest_assumption_wins(self):
        first=self.ask("Cetuximab ung thư đại trực tràng di căn")
        mutated=self.ask("Nếu RAS đột biến thì sao?",first["state"])
        self.assertEqual(self.qa(mutated)["status"],"source_condition_not_met")
        wild=self.ask("Nếu RAS tự nhiên thì sao?",mutated["state"])
        self.assertEqual(self.qa(wild)["status"],"conditional_coverage")
        neg=self.ask("Trastuzumab ung thư vú HER2 âm tính")
        pos=self.ask("Nếu HER2 dương tính thì sao?",neg["state"])
        self.assertEqual(self.qa(pos)["status"],"conditional_coverage")
        self.assertEqual(self.qa(pos)["source_rate"]["percentage"],60)

    # 5. Everolimus purpose: transplant / "không phải ung thư" is the "other" branch.
    def test_everolimus_purpose(self):
        for q in ("Everolimus dùng chống thải ghép thận, không phải ung thư, có BHYT không?",
                  "Everolimus sau ghép thận ở bệnh nhân từng bị ung thư"):
            a=self.qa(self.ask(q))
            self.assertEqual(a.get("matched_branch"),"other",q)
            self.assertIn("Các trường hợp khác",a["conclusion"],q)
        self.assertEqual(self.qa(self.ask("Everolimus điều trị ung thư thận"))["matched_branch"],"oncology")

    # 6. Comparison keeps both drugs; a related-drug follow-up stays on the current drug.
    def test_prior_drug_vs_compared_drug(self):
        for q in ("So sánh Nilotinib với Imatinib","So sánh Imatinib và Nilotinib"):
            self.assertEqual({x["ingredient"] for x in self.ask(q)["results"]},{"Nilotinib","Imatinib"},q)
        first=self.ask("Nilotinib bạch cầu tủy mạn")
        r=self.ask("Nếu kháng Imatinib?",first["state"])
        self.assertEqual([x["ingredient"] for x in r["results"]],["Nilotinib"])
        self.assertEqual(self.qa(r)["requirements"][0]["status"],"met")
        r=self.ask("Nilotinib CML không dung nạp Imatinib")
        self.assertEqual([x["ingredient"] for x in r["results"]],["Nilotinib"])

    # a. Trastuzumab emtansine / deruxtecan are different medicines.
    def test_conjugate_is_not_base_drug(self):
        for q in ("Trastuzumab emtansine ung thư vú có BHYT không?","Trastuzumab deruxtecan ung thư vú","trastuzumab-deruxtecan ung thư dạ dày"):
            r=self.ask(q)
            self.assertFalse(r["results"],q)
            self.assertEqual(r["status"],"unknown_drug",q)
            self.assertIn("thuốc khác với “Trastuzumab”",r["answer"],q)

    # b. An unrecognised new medicine must not reuse the previous medicine.
    def test_unknown_drug_does_not_inherit_previous(self):
        first=self.ask("Trastuzumab ung thư vú")
        for q in ("Kadcyla ung thư vú có BHYT không?","Pertuzumab ung thư vú có BHYT không?"):
            r=self.ask(q,first["state"])
            self.assertFalse(r["results"],q)
            self.assertEqual(r["status"],"unknown_drug",q)
            self.assertEqual(r["state"],{},q)
        mixed=self.ask("So sánh Trastuzumab và Pertuzumab trong ung thư vú")
        self.assertEqual([x["ingredient"] for x in mixed["results"]],["Trastuzumab"])
        self.assertIn("Pertuzumab",mixed["notice"])
        # Ordinary follow-ups and unaccented Vietnamese still work.
        self.assertEqual(self.ask("Nếu HER2 âm tính thì sao?",first["state"])["results"][0]["ingredient"],"Trastuzumab")
        self.assertEqual(self.status("Thuoc Trastuzumab ung thu vu HER2 am tinh"),"source_condition_not_met")

    # c. HER2 negative in its common wordings.
    def test_her2_negative_wordings(self):
        for q in ("HER2 âm","HER2 negative","HER2 0","không có HER2 dương tính","không biểu lộ HER2","HER2 IHC 1+","bộ ba âm tính","HER2 (-)"):
            self.assertEqual(self.status("Trastuzumab ung thư vú "+q),"source_condition_not_met",q)
        for q in ("HER2 dương tính","HER2 3+","HER2 (+)","không di căn, HER2 dương tính"):
            self.assertEqual(self.status("Trastuzumab ung thư vú "+q),"conditional_coverage",q)
        a=self.qa(self.ask("Trastuzumab ung thư vú HER2 IHC 2+, chưa làm FISH"))
        self.assertEqual(a["status"],"conditional_coverage")
        self.assertEqual(a["requirements"][0]["status"],"unknown")

    # d. A follow-up chip sends the context of its own answer (frontend contract).
    def test_followup_chip_uses_its_own_state(self):
        js=(ROOT/"web/app.js").read_text(encoding="utf-8")
        self.assertIn("const snap=JSON.parse(JSON.stringify(data.state||{}))",js)
        self.assertIn("send(q,snap)",js)
        self.assertIn("state:ctx??state",js)
        # Backend side: an older answer's state still answers about its own drug.
        old=self.ask("Trastuzumab ung thư vú")
        self.ask("Cetuximab ung thư đại trực tràng di căn",old["state"])
        r=self.ask(old["suggested_followups"][0],old["state"])
        self.assertEqual(r["results"][0]["ingredient"],"Trastuzumab")

    # e. The rule loader checks the disease–quote–rate relation.
    def test_loader_rejects_swapped_branches(self):
        raw=json.loads((self.c.data/"indication_rules.json").read_text(encoding="utf-8"))
        bad=copy.deepcopy(raw);b=bad["rules"][0]["branches"]
        b[0]["rate"],b[1]["rate"]=b[1]["rate"],b[0]["rate"]
        b[0]["verbatim"],b[1]["verbatim"]=b[1]["verbatim"],b[0]["verbatim"]
        with tempfile.TemporaryDirectory(dir=self.c.data.parent/"audit") as tmp:
            (Path(tmp)/"indication_rules.json").write_text(json.dumps(bad,ensure_ascii=False),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"disease"):
                load_indication_rules(Path(tmp),self.c.by_id,TOPICS)
        bad=copy.deepcopy(raw);s=next(r for r in bad["rules"] if r["ingredient"]=="Sorafenib")
        s["branches"][2]["verbatim"]=["thanh toán 30%","ung thư tế bào biểu mô gan"];s["branches"][2]["topic"]="liver";s["branches"][0]["topic"]="kidney"
        with tempfile.TemporaryDirectory(dir=self.c.data.parent/"audit") as tmp:
            (Path(tmp)/"indication_rules.json").write_text(json.dumps(bad,ensure_ascii=False),encoding="utf-8")
            with self.assertRaises(ValueError):
                load_indication_rules(Path(tmp),self.c.by_id,TOPICS)

if __name__=="__main__":unittest.main()
