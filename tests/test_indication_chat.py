import json
import os
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from engine import Corpus,ROOT
from server import make_server
from indication_chat import topics_in

class IndicationChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=Corpus()
    def ask(self,q,state=None):return self.c.converse(q,state)
    def qa(self,r):return r["results"][0]["question_answer"]

    def test_breast_question_answers_without_her2_entry(self):
        r=self.ask("Trastuzumab điều trị ung thư vú có được BHYT chi trả không?")
        a=self.qa(r)
        self.assertEqual(a["status"],"conditional_coverage")
        self.assertIn("HER2 dương tính.",a["conditions"])
        self.assertEqual(a["source_rate"]["percentage"],60)
        self.assertEqual(r["followups"],[])
        self.assertFalse(r["requires_patient_details"])
        self.assertIsNone(r["payment_eligibility"])

    def test_gastric_question_states_extent_as_condition_not_input(self):
        a=self.qa(self.ask("Trastuzumab có được BHYT thanh toán trong ung thư dạ dày?"))
        self.assertEqual(a["source_rate"]["percentage"],50)
        self.assertIn("Ung thư dạ dày tiến xa hoặc di căn.",a["conditions"])

    def test_negative_marker_does_not_receive_positive_conclusion(self):
        for q in ("Trastuzumab ung thư vú HER2 âm tính", "Trastuzumab ung thư vú HER2 (-)","Erlotinib ung thư phổi không tế bào nhỏ EGFR âm tính"):
            a=self.qa(self.ask(q))
            self.assertEqual(a["status"],"source_condition_not_met",q)
            self.assertIsNone(a["source_rate"])

    def test_different_tumor_is_not_covered_by_breast_rule(self):
        a=self.qa(self.ask("Trastuzumab điều trị ung thư đại trực tràng có được BHYT không?"))
        self.assertEqual(a["status"],"insufficient_evidence")
        self.assertIsNone(a["source_rate"])

    def test_nsclc_and_small_cell_do_not_share_rule(self):
        for name in ("Erlotinib","Gefitinib"):
            a=self.qa(self.ask(name+" dùng cho ung thư phổi không phải tế bào nhỏ có BHYT chi trả?"))
            self.assertEqual(a["source_rate"]["percentage"],50)
            b=self.qa(self.ask(name+" điều trị ung thư phổi tế bào nhỏ?"))
            self.assertEqual(b["status"],"insufficient_evidence")
            self.assertIsNone(b["source_rate"])

    def test_unspecified_lung_cancer_is_qualified(self):
        a=self.qa(self.ask("Erlotinib ung thư phổi có được chi trả?"))
        self.assertEqual(a["status"],"source_conditions")
        self.assertIn("không phải tế bào nhỏ",a["conclusion"])
        self.assertIsNone(a["source_rate"])

    def test_no_repeated_form_or_route_demand(self):
        for q in ("Paracetamol có được BHYT trả khi điều trị sốt?","Metformin đái tháo đường type 2 có được BHYT không?","Doxorubicin ung thư vú?","Paclitaxel ung thư dạ dày?"):
            r=self.ask(q)
            self.assertEqual(r["followups"],[])
            self.assertNotIn("Bạn đang dùng đường nào",r["answer"])
            self.assertNotIn("Bạn có thể bổ sung",r["answer"])
            self.assertIsNone(r["payment_eligibility"])

    def test_empty_note_does_not_prove_diabetes_coverage_or_rate(self):
        r=self.ask("Metformin đái tháo đường típ 2 có được BHYT chi trả?")
        a=self.qa(r)
        self.assertEqual(a["status"],"insufficient_evidence")
        self.assertIsNone(a["source_rate"])
        self.assertIn("chưa đủ căn cứ",a["conclusion"])
        self.assertTrue(any(c["document_id"]=="QD1353_2021" for c in r["clinical_references"]))

    def test_other_notes_are_quoted_without_new_disease_rule(self):
        r=self.ask("Paclitaxel điều trị ung thư vú có được BHYT chi trả?")
        a=self.qa(r)
        self.assertEqual(a["status"],"source_conditions")
        self.assertIn("dạng bào chế",a["conclusion"])
        self.assertEqual(a["conditions"],r["results"][0]["conditions"])

    def test_natural_followup_uses_same_drug_and_changes_topic(self):
        r=self.ask("Trastuzumab điều trị ung thư vú HER2 âm tính có BHYT không?")
        second=self.ask("Còn ung thư dạ dày thì sao?",r["state"])
        self.assertEqual(second["results"][0]["ingredient"],"Trastuzumab")
        self.assertEqual(self.qa(second)["status"],"conditional_coverage")
        self.assertEqual(self.qa(second)["source_rate"]["percentage"],50)
        self.assertNotIn("QD3128_2020",{c["document_id"] for c in second["clinical_references"]})

    def test_marker_followup_can_start_with_neu(self):
        r=self.ask("Trastuzumab ung thư vú có BHYT không?")
        second=self.ask("Nếu HER2 âm tính thì sao?",r["state"])
        self.assertEqual(self.qa(second)["status"],"source_condition_not_met")

    def test_new_medicine_does_not_inherit_old_disease(self):
        first=self.ask("Trastuzumab ung thư vú HER2 âm tính")
        second=self.ask("Erlotinib ung thư phổi không tế bào nhỏ",first["state"])
        self.assertEqual(self.qa(second)["status"],"conditional_coverage")
        self.assertNotIn("HER2",second["state"]["context"])

    def test_unknown_new_disease_cannot_inherit_covered_breast_cancer(self):
        first=self.ask("Trastuzumab điều trị ung thư vú")
        for message in ("Trastuzumab điều trị tăng huyết áp có BHYT không?","Còn bệnh tăng huyết áp thì sao?","Trastuzumab ung thư tụy có BHYT?"):
            r=self.ask(message,first["state"])
            self.assertEqual(r["results"][0]["ingredient"],"Trastuzumab")
            self.assertNotEqual(self.qa(r)["status"],"conditional_coverage")
            self.assertIsNone(self.qa(r)["source_rate"])

    def test_uncertain_marker_is_not_resolved_to_negative(self):
        r=self.ask("Trastuzumab ung thư vú chưa biết HER2 âm tính hay dương tính?")
        self.assertEqual(self.qa(r)["status"],"conditional_coverage")
        self.assertTrue(self.qa(r)["source_rate"]["conditional"])

    def test_negated_disease_does_not_activate_branch(self):
        self.assertNotIn("breast",topics_in("không phải ung thư vú"))
        self.assertNotEqual(self.qa(self.ask("Trastuzumab dùng không phải ung thư vú"))["status"],"conditional_coverage")

    def test_chat_has_no_external_ai_call_even_with_key_configured(self):
        with patch.dict(os.environ,{"BHYT_ENABLE_AI":"1","OPENAI_API_KEY":"test","OPENAI_MODEL":"test"}),patch("engine.api_post") as api:
            r=self.ask("Metformin điều trị đái tháo đường type 2")
            api.assert_not_called()
            self.assertEqual(r["mode"],"local")

    def test_transition_question_does_not_assume_current_rate(self):
        r=self.ask("Erlotinib điều trị ung thư phổi không tế bào nhỏ từ năm 2014 có BHYT?")
        self.assertEqual(self.qa(r)["status"],"transition_requires_review")
        self.assertIsNone(self.qa(r)["source_rate"])
        self.assertTrue(r["transition_review"])

    def test_wrong_route_unknown_drug_and_date_do_not_claim_coverage(self):
        a=self.qa(self.ask("Trastuzumab uống điều trị ung thư vú có BHYT?"))
        self.assertEqual(a["status"],"insufficient_evidence")
        self.assertIsNone(a["source_rate"])
        self.assertFalse(self.ask("Kadcyla điều trị ung thư vú có BHYT?")["results"])
        self.assertEqual(self.c.converse("Trastuzumab",as_of="2027-01-01")["status"],"unsupported_date")

    def test_source_links_are_real_and_legal_core_stays_separate(self):
        r=self.ask("Trastuzumab ung thư vú có BHYT?")
        ids={c["id"] for c in r["citations"]}
        self.assertTrue(set(self.qa(r)["source_ids"])<=ids)
        self.assertTrue(all(c["id"] in self.c.by_chunk for c in r["citations"]))
        self.assertTrue(all(c["document_id"]=="QD3128_2020" for c in r["clinical_references"]))

class ChatOnlyHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server(0);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.base="http://127.0.0.1:"+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def test_only_chat_input_is_rendered(self):
        with urlopen(self.base+"/") as f:html=f.read().decode()
        self.assertEqual(html.count('<textarea'),1)
        self.assertEqual(html.count('<form'),1)
        for text in ('id="case-form"','id="case-diagnosis"','src="/case.js"','<select','<input'):
            self.assertNotIn(text,html)
        self.assertIn('id="question"',html)

    def test_chat_api_answers_without_facts_or_answers_fields(self):
        with urlopen(self.base+"/api/health") as f:token=json.load(f)["token"]
        req=Request(self.base+"/api/chat",data=json.dumps({"message":"Trastuzumab ung thư vú có BHYT?"}).encode(),headers={"Content-Type":"application/json","X-Session-Token":token})
        with urlopen(req) as f:r=json.load(f)
        self.assertEqual(r["response_type"],"general_indication_chat")
        self.assertEqual(r["results"][0]["question_answer"]["status"],"conditional_coverage")
        self.assertFalse(r["requires_patient_details"])

if __name__=="__main__":unittest.main()
