import copy
import json
import os
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from engine import Corpus
from case_workbench import CaseWorkbench
from server import make_server

class CaseWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=Corpus();cls.w=CaseWorkbench(cls.c)
        cls.trast="TT20-PLI-0402-R481"
        cls.pac="TT20-PLI-0381-R459"

    def evaluate(self,id=None,answers=None,facts=None):
        return self.w.evaluate({"drug_id":id or self.trast,"answers":answers or {},"facts":facts or {}})

    def test_all_drugs_can_open_case_schema(self):
        for row in self.c.rows:
            self.assertEqual(self.w.schema(row["record_id"])["drug"]["id"],row["record_id"])

    def test_unknown_her2_is_missing_not_denied(self):
        r=self.evaluate(answers={"indication":"breast"})
        self.assertEqual(next(x for x in r["criteria"] if x["key"]=="her2")["status"],"missing")
        self.assertIsNone(r["candidate_source_rate"])
        self.assertIsNone(r["payment_eligibility"])

    def test_breast_and_gastric_rates_stay_separate(self):
        breast=self.evaluate(answers={"indication":"breast","her2":"positive"})
        gastric=self.evaluate(answers={"indication":"gastric","her2":"positive","extent":"advanced"})
        self.assertEqual(breast["candidate_source_rate"]["percentage"],60)
        self.assertEqual(gastric["candidate_source_rate"]["percentage"],50)
        for r in (breast,gastric):
            self.assertEqual(r["status"],"requires_review")
            self.assertEqual(r["candidate_source_rate"]["source_id"],self.trast)
            self.assertTrue(any(x["key"]=="clinical_sources" and x["status"]=="needs_review" for x in r["criteria"]))

    def test_gastric_requires_extent_and_negative_marker_does_not_match(self):
        for answers in ({"indication":"gastric","her2":"positive"},{"indication":"breast","her2":"negative"},{"indication":"other","her2":"positive"}):
            self.assertIsNone(self.evaluate(answers=answers)["candidate_source_rate"])

    def test_hidden_answers_are_removed_after_branch_switch(self):
        r=self.evaluate(answers={"indication":"breast","her2":"positive","extent":"other"})
        self.assertNotIn("extent",r["answers"])
        self.assertEqual(r["candidate_source_rate"]["percentage"],60)

    def test_paclitaxel_formulations_do_not_mix(self):
        for form,percentage in (("liposome",50),("polymeric",50),("other",100)):
            r=self.evaluate(self.pac,{"formulation":form})
            self.assertEqual(r["candidate_source_rate"]["percentage"],percentage)
            self.assertIsNone(r["payment_eligibility"])
            self.assertTrue(any(x["key"]=="transition" for x in r["criteria"]))

    def test_generic_note_empty_does_not_create_100_percent_rate(self):
        row=next(r for r in self.c.rows if r["ingredient"]=="Metformin")
        r=self.evaluate(row["record_id"],facts={"diagnosis":"đái tháo đường type 2"})
        self.assertIsNone(r["candidate_source_rate"])
        self.assertTrue(any(x["key"]=="source_note" for x in r["criteria"]))

    def test_product_name_never_means_verified_label(self):
        r=self.evaluate(facts={"product_name":"Sản phẩm nhập thử"})
        criterion=next(x for x in r["criteria"] if x["key"]=="product")
        self.assertEqual(criterion["status"],"needs_review")
        self.assertEqual(criterion["value"],"Sản phẩm nhập thử")

    def test_conditions_and_evidence_are_preserved(self):
        for id in self.w.profiles:
            r=self.evaluate(id)
            self.assertEqual(r["conditions_verbatim"],self.c.by_id[id]["conditions_verbatim"])
            ids={x["id"] for x in r["citations"]}
            self.assertTrue(all(set(x["source_ids"])<=ids for x in r["criteria"]))
            self.assertFalse(r["ai_used"])

    def test_other_drug_answers_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluate(self.pac,{"her2":"positive"})

    def test_private_and_malformed_case_inputs_rejected(self):
        for payload in ({"drug_id":self.trast,"facts":{"diagnosis":"mã bệnh án: ABC"}},
            {"drug_id":self.trast,"facts":{"diagnosis":"0901234567"}},
            {"drug_id":self.trast,"answers":{"her2":[]} },
            {"drug_id":"invented"},{"drug_id":self.trast,"facts":[]},
            {"drug_id":self.trast,"facts":{"diagnosis":"x"*501}},
            {"drug_id":self.trast,"facts":{"name":"test"}}):
            with self.subTest(payload=payload),self.assertRaises(ValueError):self.w.evaluate(payload)

    def test_case_evaluation_never_calls_ai(self):
        with patch.dict(os.environ,{"BHYT_ENABLE_AI":"1","OPENAI_API_KEY":"test","OPENAI_MODEL":"test"}),patch("engine.api_post") as api:
            self.evaluate(answers={"indication":"breast","her2":"positive"})
            api.assert_not_called()

    def test_followups_do_not_merge_distinct_drugs(self):
        r=self.c.chat("Erlotinib và Paclitaxel")
        follow=self.c.chat("điều trị ung thư",r["state"])
        self.assertEqual(len(follow["results"]),2)
        self.assertEqual([x["ingredient"] for x in follow["results"]],["Erlotinib","Paclitaxel"])
        self.assertTrue(all(len(x["record_ids"])==1 for x in follow["results"]))

    def test_same_drug_keeps_clinical_context(self):
        r=self.c.chat("Erlotinib")
        r=self.c.chat("từ năm 2014",r["state"])
        r=self.c.chat("Erlotinib uống",r["state"])
        self.assertIn("2014",r["state"]["context"])

    def test_injection_aliases_match_source_group(self):
        for route in ("tiêm tĩnh mạch","tiêm truyền","truyền tĩnh mạch"):
            r=self.c.chat("Trastuzumab "+route)
            self.assertEqual(r["results"][0]["status"],"listed_requires_context",route)

    def test_wrong_ai_rate_with_valid_source_is_rejected(self):
        fake={"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps({"summary":"Trastuzumab điều trị ung thư vú HER2 dương tính được thanh toán 50%.","source_ids":[self.trast]})}]}]}
        with patch.dict(os.environ,{"BHYT_ENABLE_AI":"1","OPENAI_API_KEY":"test","OPENAI_MODEL":"test"}),patch("engine.api_post",return_value=fake):
            self.assertNotIn("ai_explanation",self.c.chat("Trastuzumab ung thư vú HER2 dương tính"))

class CaseHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server(0);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base="http://127.0.0.1:"+str(cls.server.server_port)
        with urlopen(cls.base+"/api/health") as f:cls.token=json.load(f)["token"]
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def test_health_identifies_exact_project_instance(self):
        from server import INSTANCE_ID,APP_VERSION
        with urlopen(self.base+"/api/health") as f:r=json.load(f)
        self.assertEqual(r["instance_id"],INSTANCE_ID)
        self.assertEqual(r["version"],APP_VERSION)

    def test_case_search_schema_and_asset(self):
        for path in ("/api/case/drugs?q=Trastuzumab","/api/case/schema?id=TT20-PLI-0402-R481","/case.js"):
            with urlopen(self.base+path) as f:self.assertEqual(f.status,200);self.assertTrue(f.read())
    def test_evaluation_requires_token(self):
        req=Request(self.base+"/api/case/evaluate",data=b"{}",headers={"Content-Type":"application/json"})
        with self.assertRaises(HTTPError) as e:urlopen(req)
        self.assertEqual(e.exception.code,403)
    def test_evaluation_returns_source_linked_result(self):
        req=Request(self.base+"/api/case/evaluate",data=json.dumps({"drug_id":"TT20-PLI-0402-R481","answers":{"indication":"breast"}}).encode(),headers={"Content-Type":"application/json","X-Session-Token":self.token})
        with urlopen(req) as f:r=json.load(f)
        self.assertEqual(r["status"],"requires_review")
        self.assertTrue(r["citations"]);self.assertIsNone(r["payment_eligibility"])
    def test_invalid_schema_returns_400(self):
        with self.assertRaises(HTTPError) as e:urlopen(self.base+"/api/case/schema?id=wrong")
        self.assertEqual(e.exception.code,400)
