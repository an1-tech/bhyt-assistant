"""Confirmation buttons (v1.10) and the third review of commit bf77b37 (F1–F12).

Unclear conditions are never guessed from free text; the answer offers buttons and a
confirmed fact always beats text reading.
"""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from engine import Corpus
from indication_chat import TOPICS
from indication_rules import load_indication_rules
from server import make_server


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=Corpus()

    def ask(self,q,state=None,confirm=None):return self.c.converse(q,state or {},None,confirm)
    def qa(self,r):return r["results"][0]["question_answer"]
    def reqs(self,r):return {x["label"]:x["status"] for x in self.qa(r)["requirements"]}
    def item(self,r,label):return next(c for c in self.qa(r)["confirm"] if c["label"]==label)
    def click(self,r,label,value):
        item=self.item(r,label)
        assert value in {o["value"] for o in item["options"]}
        return self.ask(label+": "+value,r["state"],{"key":item["key"],"value":value})


class ConfirmFlowTests(Base):
    def test_unstated_conditions_offer_buttons_not_guesses(self):
        r=self.ask("Cetuximab ung thư đại trực tràng có BHYT không?")
        labels=[c["label"] for c in self.qa(r)["confirm"]]
        self.assertEqual(labels,["Di căn","RAS"])
        self.assertEqual(self.item(r,"RAS")["options"][0]["label"],"RAS tự nhiên")
        self.assertEqual([o["value"] for o in self.item(r,"RAS")["options"]],["met","not_met","unknown"])

    def test_confirmed_fact_decides_and_persists(self):
        r=self.ask("Cetuximab ung thư đại trực tràng")
        r=self.click(r,"RAS","not_met")
        self.assertEqual(self.qa(r)["status"],"source_condition_not_met")
        self.assertEqual(r["results"][0]["ingredient"],"Cetuximab")
        r=self.click(r,"RAS","met");r=self.click(r,"Di căn","met")
        a=self.qa(r)
        self.assertEqual(a["status"],"conditional_coverage");self.assertTrue(a.get("all_requirements_met"))
        self.assertEqual(a["source_rate"]["percentage"],50)
        self.assertTrue(all(x["source"]=="confirmed" for x in a["requirements"]))
        self.assertIn("Theo xác nhận",";".join(a["conditions"]))
        # Confirmed conditions keep their buttons so the doctor can change them.
        self.assertEqual({c["label"] for c in a["confirm"]},{"Di căn","RAS"})

    def test_new_question_replaces_confirmed_fact(self):
        r=self.click(self.ask("Cetuximab ung thư đại trực tràng di căn"),"RAS","not_met")
        r=self.ask("Nếu RAS tự nhiên thì sao?",r["state"])
        self.assertEqual(self.reqs(r)["RAS"],"met")
        self.assertNotIn("ras",r["state"]["facts"].get(r["results"][0]["record_ids"][0],{}).get("colorectal",{}))

    def test_confirmed_fact_beats_later_text_and_survives_followups(self):
        r=self.click(self.ask("Cetuximab ung thư đại trực tràng di căn"),"RAS","met")
        r=self.ask("Tỷ lệ thanh toán bao nhiêu?",r["state"])
        self.assertEqual(self.reqs(r)["RAS"],"met")

    def test_new_medicine_drops_confirmed_facts(self):
        r=self.click(self.ask("Cetuximab ung thư đại trực tràng di căn"),"RAS","met")
        r=self.ask("Trastuzumab ung thư vú",r["state"])
        self.assertEqual(r["state"]["facts"],{})

    def test_invalid_confirmations_are_rejected(self):
        r=self.ask("Cetuximab ung thư đại trực tràng di căn")
        key=self.item(r,"RAS")["key"]
        for bad in ({"key":key,"value":"yes"},{"key":"x|y|z","value":"met"},{"key":key.replace("ras","her2"),"value":"met"},{"value":"met"},"met"):
            with self.assertRaises(ValueError):self.ask("RAS",r["state"],bad)
        with self.assertRaises(ValueError):self.ask("RAS",{},{"key":key,"value":"met"})

    def test_formulation_is_confirmed_not_guessed(self):
        r=self.ask("Doxorubicin chưa rõ có phải dạng liposome hay không")
        a=self.qa(r);self.assertNotIn("matched_branch",a)
        item=a["confirm"][0];self.assertEqual({o["value"] for o in item["options"]},{"liposome","other"})
        r=self.ask("Dạng liposome",r["state"],{"key":item["key"],"value":"liposome"})
        self.assertEqual(self.qa(r)["matched_branch"],"liposome");self.assertIn("Theo xác nhận",self.qa(r)["conclusion"])

    def test_multi_drug_answers_offer_no_buttons(self):
        r=self.ask("So sánh Imatinib và Nilotinib cho CML")
        self.assertTrue(all(x["question_answer"]["confirm"]==[] for x in r["results"]))


class ConfirmHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server(0);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base="http://127.0.0.1:"+str(cls.server.server_port)
        with urlopen(cls.base+"/api/health") as f:cls.token=json.load(f)["token"]
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def post(self,body):
        req=Request(self.base+"/api/chat",data=json.dumps(body).encode(),headers={"Content-Type":"application/json","X-Session-Token":self.token})
        with urlopen(req) as f:return json.load(f)

    def test_confirm_round_trip(self):
        r=self.post({"message":"Cetuximab ung thư đại trực tràng di căn"})
        item=next(c for c in r["results"][0]["question_answer"]["confirm"] if c["label"]=="RAS")
        r=self.post({"message":"RAS: RAS đột biến","state":r["state"],"confirm":{"key":item["key"],"value":"not_met"}})
        self.assertEqual(r["results"][0]["question_answer"]["status"],"source_condition_not_met")


class Review3Tests(Base):
    """Codex review of bf77b37: each case gave a wrong answer before the fix."""
    def test_f1_paclitaxel_polymeric(self):
        for q,branch in (("Paclitaxel không phải liposome mà là polymeric micelle","polymeric"),("Paclitaxel dạng polymeric micelle, không phải liposome","polymeric"),
                         ("Paclitaxel dạng liposome, không phải polymeric micelle","liposome")):
            self.assertEqual(self.qa(self.ask(q))["matched_branch"],branch,q)

    def test_f2_kras_nras_order_independent(self):
        for q in ("di căn KRAS đột biến, NRAS tự nhiên","di căn NRAS tự nhiên, KRAS đột biến","di căn không có đột biến KRAS và NRAS đột biến"):
            self.assertEqual(self.qa(self.ask("Cetuximab ung thư đại trực tràng "+q))["status"],"source_condition_not_met",q)

    def test_f3_or_conditions(self):
        for q in ("Nilotinib CML kháng Imatinib nhưng dung nạp tốt Imatinib","Nilotinib CML dung nạp tốt Imatinib nhưng kháng Imatinib",
                  "Nilotinib CML không dung nạp Imatinib nhưng không kháng Imatinib"):
            self.assertEqual(self.qa(self.ask(q))["source_rate"]["percentage"],80,q)
        for q in ("Trastuzumab ung thư dạ dày tiến xa, chưa di căn, HER2 dương tính","Trastuzumab ung thư dạ dày chưa di căn, tiến xa, HER2 dương tính"):
            self.assertEqual(self.reqs(self.ask(q))["tiến xa hoặc di căn"],"met",q)

    def test_f4_positive_inside_negation(self):
        for q in ("Abiraterone ung thư tiền liệt tuyến chưa thất bại nội tiết và chưa hóa trị","Abiraterone ung thư tiền liệt tuyến không thất bại nội tiết và chưa hóa trị",
                  "Trastuzumab ung thư dạ dày không tiến xa và không di căn HER2 dương tính","Bendamustine CLL Binet A nhưng không phải Binet B"):
            r=self.ask(q)
            self.assertNotIn("met",[v for k,v in self.reqs(r).items() if k not in ("HER2","Fludarabin")],q)
            self.assertNotEqual(self.qa(r).get("all_requirements_met"),True,q)

    def test_f5_organ_specific_negation(self):
        for q in ("di căn gan, không di căn não, RAS tự nhiên","không di căn não, di căn gan, RAS tự nhiên","di căn gan nhưng không di căn phổi RAS tự nhiên"):
            self.assertEqual(self.reqs(self.ask("Cetuximab ung thư đại trực tràng "+q))["di căn"],"met",q)
        self.assertEqual(self.reqs(self.ask("Cetuximab ung thư đại trực tràng giai đoạn III di căn hạch RAS tự nhiên"))["di căn"],"not_met")

    def test_f6_conjugate_in_brackets(self):
        r=self.ask("Trastuzumab (deruxtecan) ung thư vú")
        self.assertFalse(r["results"]);self.assertEqual(r["status"],"unknown_drug")

    def test_f7_unknown_other_marker_does_not_hide_ras(self):
        r=self.ask("Cetuximab ung thư đại trực tràng di căn RAS đột biến chưa biết tình trạng EGFR")
        self.assertEqual(self.qa(r)["status"],"source_condition_not_met")

    def test_f8_thyroid_requires_progression_or_metastasis(self):
        r=self.ask("Sorafenib ung thư tuyến giáp biệt hóa giai đoạn sớm chưa tiến triển, chưa di căn, đã thất bại iod phóng xạ")
        self.assertEqual(self.qa(r)["status"],"source_condition_not_met")
        r=self.ask("Sorafenib ung thư tuyến giáp biệt hóa di căn phổi, đã thất bại iod phóng xạ")
        self.assertTrue(self.qa(r).get("all_requirements_met"))

    def test_f9_ki67_is_not_a_drug(self):
        r=self.ask("Nếu Ki-67 cao thì sao?",self.ask("Trastuzumab ung thư vú")["state"])
        self.assertEqual(r["results"][0]["ingredient"],"Trastuzumab")

    def test_f10_outside_cancer_is_scope_not_route(self):
        a=self.qa(self.ask("Everolimus dùng ngoài ung thư có BHYT?"))
        self.assertEqual(a["matched_branch"],"other")

    def test_f11_loader_rejects_dropped_requirement(self):
        raw=json.loads((self.c.data/"indication_rules.json").read_text(encoding="utf-8"))
        bad=copy.deepcopy(raw);b=bad["rules"][0]["branches"][0];b["requirements"]=[];b["conditions"]=[]
        with tempfile.TemporaryDirectory(dir=self.c.data.parent/"audit") as t:
            (Path(t)/"indication_rules.json").write_text(json.dumps(bad,ensure_ascii=False),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"no requirement"):load_indication_rules(Path(t),self.c.by_id,TOPICS)

    def test_f12_unclear_formulation(self):
        self.assertNotIn("matched_branch",self.qa(self.ask("Doxorubicin chưa rõ có phải dạng liposome hay không")))

if __name__=="__main__":unittest.main()
