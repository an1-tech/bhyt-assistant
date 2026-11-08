"""Oncology prototype (khoa Ung bướu): 18 drugs, draft branches loaded for demo."""
import json
import unittest
from engine import Corpus


class OncologyPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=Corpus()
        cls.rules=json.loads((cls.c.data/"indication_rules.json").read_text(encoding="utf-8"))["rules"]

    def ask(self,q,state=None):return self.c.converse(q,state)
    def qa(self,r):return r["results"][0]["question_answer"]

    def test_branch_questions_return_source_rate(self):
        cases={
            "Pemetrexed điều trị u trung biểu mô màng phổi có BHYT không?":("Pemetrexed",50),
            "Tegafur + gimeracil + oteracil kali điều trị ung thư dạ dày di căn":("Tegafur + gimeracil + oteracil kali",70),
            "Cetuximab ung thư đại trực tràng di căn":("Cetuximab",50),
            "Cetuximab ung thư đầu cổ có BHYT không?":("Cetuximab",50),
            "Sorafenib ung thư thận":("Sorafenib",30),
            "Sorafenib ung thư gan":("Sorafenib",50),
            "Imatinib điều trị GIST":("Imatinib",80),
            "Imatinib bạch cầu tủy mạn":("Imatinib",80),
            "Nilotinib bạch cầu tủy mạn kháng Imatinib":("Nilotinib",80),
            "Bendamustine bạch cầu lympho mạn":("Bendamustine",50),
            "Abiraterone ung thư tiền liệt tuyến":("Abiraterone acetate",30),
        }
        for q,(name,rate) in cases.items():
            r=self.ask(q)
            self.assertEqual([x["ingredient"] for x in r["results"]],[name],q)
            a=self.qa(r)
            self.assertEqual(a["status"],"conditional_coverage",q)
            self.assertEqual(a["source_rate"]["percentage"],rate,q)
            self.assertIn("chưa được Dược/BHYT duyệt",a["scope"],q)

    def test_explicit_opposite_condition_is_not_met(self):
        for q in ("Cetuximab ung thư đại trực tràng di căn RAS đột biến",
                  "Tegafur + gimeracil + oteracil kali ung thư dạ dày chưa di căn",
                  "Rituximab u lympho không Hodgkin CD20 âm tính",
                  "Sorafenib ung thư tuyến giáp chưa dùng iod phóng xạ",
                  "Abiraterone ung thư tiền liệt tuyến chưa dùng nội tiết hoặc hóa trị"):
            a=self.qa(self.ask(q))
            self.assertEqual(a["status"],"source_condition_not_met",q)
            self.assertIsNone(a["source_rate"],q)

    def test_rituximab_has_no_invented_rate(self):
        a=self.qa(self.ask("Rituximab u lympho không Hodgkin có BHYT không?"))
        self.assertEqual(a["status"],"conditional_coverage")
        self.assertIsNone(a["source_rate"])
        self.assertTrue(any("không tự suy ra 100%" in x for x in a["conditions"]))

    def test_rate_only_notes_do_not_claim_an_indication(self):
        for q in ("Afatinib ung thư phổi không tế bào nhỏ","Bevacizumab ung thư đại trực tràng","Fulvestrant ung thư vú"):
            a=self.qa(self.ask(q))
            self.assertEqual(a["status"],"source_conditions",q)
            self.assertIn("không ghi chỉ định cụ thể",a["conclusion"],q)
            self.assertIsNone(a["source_rate"],q)

    def test_condition_drug_is_context_not_second_medicine(self):
        r=self.ask("Bendamustine u lympho không Hodgkin tiến triển sau Rituximab")
        self.assertEqual([x["ingredient"] for x in r["results"]],["Bendamustine"])
        both=self.ask("So sánh Imatinib và Nilotinib")
        self.assertEqual(len(both["results"]),2)

    def test_followup_wording_does_not_pull_transition_article(self):
        first=self.ask("Cetuximab ung thư đại trực tràng di căn")
        r=self.ask("Nếu RAS đột biến thì sao?",first["state"])
        self.assertNotIn("transition_review",r)
        self.assertNotIn("notice",r)

    def test_salt_free_name_resolves_only_when_unique(self):
        self.assertEqual(self.c.resolve("Afatinib")[0][0]["ingredient"],"Afatinib dimaleate")
        self.assertEqual(self.c.resolve("Abiraterone")[0][0]["ingredient"],"Abiraterone acetate")

    def test_every_suggestion_stays_on_the_same_drug(self):
        for rule in self.rules:
            if rule["kind"]!="indication_branches":continue
            name=rule["ingredient"]
            for b in rule["branches"]:
                first=self.ask(f"{name} điều trị {b['disease']} có BHYT không?")
                self.assertEqual(first["results"][0]["ingredient"],name,(name,b["topic"]))
                self.assertEqual(self.qa(first).get("matched_branch"),b["topic"],(name,b["topic"]))
                for q in first["suggested_followups"]:
                    r=self.ask(q,first["state"])
                    self.assertEqual([x["ingredient"] for x in r["results"]],[name],(name,q))
                    self.assertIn(self.qa(r)["status"],("conditional_coverage","source_condition_not_met"),(name,q))

if __name__=="__main__":unittest.main()
