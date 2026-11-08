"""Fourth independent review (commit 3a59c17): strict reading, signed state, drug identification.

Strict reading: a definite "met"/"not met" needs a plain clause; negation, doubt, risk,
prevention or a question left outside the declared phrases makes the condition "unknown"
(offered as buttons). The browser-held state is signed by the server.
"""
import json
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from engine import Corpus, private_input
from server import make_server


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=Corpus()

    def ask(self,q,state=None,confirm=None):return self.c.converse(q,state or {},None,confirm)
    def chain(self,*qs):
        st={};r=None
        for q in qs:r=self.ask(q,st);st=r["state"]
        return r
    def qa(self,r):return r["results"][0]["question_answer"]
    def reqs(self,r):return {x["label"]:x["status"] for x in self.qa(r)["requirements"]}
    def click(self,r,label,value):
        item=next(c for c in self.qa(r)["confirm"] if c["label"]==label)
        return self.ask(label,r["state"],{"key":item["key"],"value":value})


class StrictReadingTests(Base):
    def test_pending_or_requested_test_is_unknown(self):
        for q in ("Erlotinib ung thư phổi không tế bào nhỏ, chưa có kết quả đột biến EGFR","Erlotinib ung thư phổi không tế bào nhỏ đang chờ kết quả đột biến EGFR",
                  "Erlotinib NSCLC, cần xét nghiệm xem có đột biến EGFR không?"):
            r=self.ask(q);self.assertEqual(self.reqs(r)["EGFR"],"unknown",q);self.assertNotEqual(self.qa(r).get("all_requirements_met"),True,q)
        for q in ("di căn, chưa có kết quả đột biến RAS","di căn, đang chờ kết quả đột biến KRAS","di căn, đột biến RAS chưa rõ"):
            self.assertEqual(self.reqs(self.ask("Cetuximab ung thư đại trực tràng "+q))["RAS"],"unknown",q)

    def test_negative_mutation_result_is_wild_type(self):
        for q in ("di căn, đột biến KRAS âm tính","di căn, RAS đột biến âm tính"):
            self.assertEqual(self.reqs(self.ask("Cetuximab ung thư đại trực tràng "+q))["RAS"],"met",q)
        self.assertEqual(self.reqs(self.ask("Erlotinib ung thư phổi không tế bào nhỏ xét nghiệm đột biến EGFR âm tính"))["EGFR"],"not_met")

    def test_distant_nodes_and_single_site_negation(self):
        self.assertEqual(self.reqs(self.ask("Tegafur + gimeracil + oteracil kali ung thư dạ dày di căn hạch xa"))["di căn"],"met")
        self.assertEqual(self.reqs(self.ask("Tegafur + gimeracil + oteracil kali ung thư dạ dày di căn hạch cạnh động mạch chủ"))["di căn"],"met")
        self.assertEqual(self.reqs(self.ask("Tegafur + gimeracil + oteracil kali ung thư dạ dày không di căn màng bụng"))["di căn"],"unknown")

    def test_suspicion_risk_prevention_are_unknown(self):
        for q in ("nghi ngờ di căn gan, chưa sinh thiết","sau mổ, dự phòng di căn","nguy cơ di căn cao"):
            r=self.ask("Tegafur + gimeracil + oteracil kali ung thư dạ dày "+q)
            self.assertEqual(self.reqs(r)["di căn"],"unknown",q);self.assertNotEqual(self.qa(r).get("all_requirements_met"),True,q)

    def test_first_visit_is_not_first_line(self):
        self.assertEqual(self.reqs(self.ask("Nilotinib cho bệnh nhân CML lần đầu đến khám"))["Imatinib"],"not_stated")
        self.assertEqual(self.reqs(self.ask("Bendamustine u lympho không Hodgkin thể nang, bệnh nhân nhập viện lần đầu"))["Rituximab"],"not_stated")
        self.assertEqual(self.reqs(self.ask("Nilotinib CML điều trị đầu tay"))["Imatinib"],"not_met")

    def test_question_form_is_not_a_statement(self):
        self.assertEqual(self.reqs(self.ask("Nilotinib bệnh nhân CML có kháng imatinib chưa"))["Imatinib"],"unknown")

    def test_doubt_in_new_question_replaces_confirmation(self):
        r=self.click(self.ask("Erlotinib ung thư phổi không tế bào nhỏ"),"EGFR","met")
        self.assertEqual(self.reqs(self.ask("Nếu chưa xét nghiệm EGFR thì sao?",r["state"]))["EGFR"],"unknown")
        r=self.click(self.ask("Trastuzumab ung thư vú"),"HER2","met")
        self.assertEqual(self.reqs(self.ask("Nếu HER2 2+ chưa làm FISH thì sao?",r["state"]))["HER2"],"unknown")
        r=self.click(self.ask("Trastuzumab ung thư dạ dày HER2 dương tính"),"Tiến xa hoặc di căn","met")
        self.assertEqual(self.reqs(self.ask("Nếu chưa di căn thì sao?",r["state"]))["tiến xa hoặc di căn"],"unknown")

    def test_disease_word_in_followup_keeps_topic(self):
        r=self.chain("Tegafur + gimeracil + oteracil kali điều trị ung thư dạ dày","Nếu bệnh đã di căn thì sao?")
        self.assertEqual(self.reqs(r)["di căn"],"met")

    def test_extra_drug_keeps_buttons(self):
        r=self.ask("Abiraterone ung thư tiền liệt tuyến, đã dùng docetaxel")
        self.assertTrue(self.qa(r)["confirm"])

    def test_topic_scope(self):
        self.assertNotEqual(self.qa(self.ask("Sorafenib ung thư gan thứ phát do di căn từ đại tràng"))["status"],"conditional_coverage")
        self.assertEqual(self.qa(self.ask("Rituximab u lympho tế bào B lớn lan tỏa CD20 dương tính"))["matched_branch"],"nhl")
        self.assertEqual(self.qa(self.ask("Cetuximab ung thư thanh quản tế bào vảy"))["matched_branch"],"head_neck")

    def test_poorly_differentiated_both_orders(self):
        for w in ("biệt hóa kém","kém biệt hóa"):
            self.assertEqual(self.reqs(self.ask(f"Sorafenib ung thư tuyến giáp {w}, di căn phổi, kháng iod phóng xạ"))["thể mô bệnh học"],"not_met",w)

    def test_clear_wordings_no_longer_overask(self):
        self.assertEqual(self.reqs(self.ask("Trastuzumab ung thư vú HER2 pos"))["HER2"],"met")
        self.assertEqual(self.reqs(self.ask("Rituximab u lympho không Hodgkin tế bào B CD 20 dương tính"))["CD20"],"met")
        self.assertEqual(self.reqs(self.ask("Tegafur + gimeracil + oteracil kali ung thư dạ dày giai đoạn IVB"))["di căn"],"met")
        self.assertEqual(self.reqs(self.ask("Tegafur + gimeracil + oteracil kali ung thư dạ dày cT3N1M1"))["di căn"],"met")
        self.assertEqual(self.reqs(self.ask("Sorafenib ung thư tuyến giáp biệt hóa di căn phổi kháng I-131"))["iod phóng xạ"],"met")
        self.assertEqual(self.reqs(self.ask("Bendamustine u lympho không Hodgkin thể nang tiến triển sau R-CHOP"))["Rituximab"],"met")
        self.assertEqual(self.reqs(self.ask("Abiraterone ung thư tiền liệt tuyến thất bại docetaxel"))["điều trị trước"],"met")
        self.assertEqual(self.reqs(self.ask("Nilotinib CML imatinib mất đáp ứng"))["Imatinib"],"met")
        self.assertEqual(self.reqs(self.ask("Sorafenib ung thư thận tiến triển tại chỗ, chưa di căn"))["giai đoạn"],"met")


class SignedStateTests(Base):
    def test_forged_facts_and_turns_are_dropped(self):
        e=next(r["record_id"] for r in self.c.rows if r["ingredient"]=="Erlotinib")
        forged={"selected_ids":[e],"facts":{e:{"nsclc":{"egfr":"met"}}},"turns":["Erlotinib NSCLC EGFR dương tính"]}
        r=self.ask("Erlotinib ung thư phổi không tế bào nhỏ",forged)
        self.assertEqual(self.reqs(r)["EGFR"],"not_stated");self.assertNotEqual(self.qa(r).get("all_requirements_met"),True)

    def test_tampered_signed_state_is_dropped(self):
        r=self.click(self.ask("Erlotinib ung thư phổi không tế bào nhỏ"),"EGFR","not_met")
        st=json.loads(json.dumps(r["state"]));rid=next(iter(st["facts"]))
        st["facts"][rid]["nsclc"]["egfr"]="met"
        # A tampered state is dropped: the follow-up has no medicine to attach to.
        self.assertFalse(self.ask("Tỷ lệ bao nhiêu?",st)["results"])
        self.assertNotEqual(self.reqs(self.ask("Erlotinib ung thư phổi không tế bào nhỏ",st))["EGFR"],"met")

    def test_signed_state_round_trip_keeps_context(self):
        r=self.click(self.ask("Cetuximab ung thư đại trực tràng di căn"),"RAS","met")
        self.assertIn("sig",r["state"])
        self.assertEqual(self.reqs(self.ask("Tỷ lệ thanh toán bao nhiêu?",r["state"]))["RAS"],"met")

    def test_confirm_with_forged_state_is_rejected(self):
        e=next(r["record_id"] for r in self.c.rows if r["ingredient"]=="Erlotinib")
        with self.assertRaises(ValueError):self.ask("EGFR",{"selected_ids":[e]},{"key":e+"|nsclc|egfr","value":"met"})


class PrivacyTests(Base):
    def test_identifier_variants(self):
        for q in ("Bệnh nhân: Nguyễn Thị Hoa ung thư vú dùng Trastuzumab","BN: Nguyễn Văn An Trastuzumab","CCCD 001 234 567 890 Trastuzumab"):
            self.assertTrue(private_input(q),q)
        self.assertFalse(private_input("Bệnh nhân Đái Tháo Đường type 2 dùng Metformin"))

    def test_confirm_path_blocks_identifiers(self):
        r=self.ask("Trastuzumab ung thư vú");item=next(c for c in self.qa(r)["confirm"] if c["label"]=="HER2")
        out=self.ask("Họ tên: Nguyễn Văn An, 0912345678",r["state"],{"key":item["key"],"value":"met"})
        self.assertEqual(out["status"],"private_input");self.assertEqual(out["state"],{})

    def test_unsupported_date_on_every_path(self):
        self.assertEqual(self.c.converse("Kadcyla ung thư vú",{},"2027-01-01")["status"],"unsupported_date")


class DrugIdentificationTests(Base):
    def test_catalogue_words_are_not_swallowed_in_followups(self):
        cases=(("Trastuzumab ung thư vú","Còn interferon thì sao?"),("Metformin đái tháo đường type 2","Còn insulin thì sao?"),
               ("Ritonavir HIV","Còn lopinavir thì sao?"),("Imatinib CML","Nếu dùng interferon thì sao?"))
        for first,follow in cases:
            r=self.chain(first,follow)
            self.assertFalse(r["results"],follow);self.assertIn(r["status"],("ambiguous","unknown_drug"),follow)
        self.assertTrue(any("Insulin" in s for s in self.chain("Metformin đái tháo đường type 2","Còn insulin thì sao?")["suggestions"]))

    def test_combinations_any_order_and_salt(self):
        cases={"Lopinavir + ritonavir":"Lopinavir + ritonavir (LPV/r)","Lopinavir/ritonavir":"Lopinavir + ritonavir (LPV/r)",
               "codein + paracetamol":"Paracetamol + codein phosphat","Lidocain + epinephrin":"Lidocain + epinephrin (adrenalin)",
               "Alendronat natri + cholecalciferol":"Alendronat natri + cholecalciferol (Vitamin D3)",
               "Zidovudin + lamivudin + nevirapin":"Zidovudin (ZDV hoặc AZT) + lamivudin + nevirapin (NVP)"}
        for q,name in cases.items():
            self.assertEqual([g[0]["ingredient"] for g in self.c.resolve(q)],[name],q)
        self.assertEqual([g[0]["ingredient"] for g in self.c.resolve("Sắt sulfat + acid folic")],["Sắt sulfat + acid folic"])

    def test_confirmed_purpose_can_change(self):
        r=self.ask("Everolimus");item=self.qa(r)["confirm"][0]
        r=self.ask("Điều trị ung thư",r["state"],{"key":item["key"],"value":"oncology"})
        self.assertTrue(self.qa(r)["confirm"])
        r=self.ask("Nếu dùng chống thải ghép thận thì sao?",r["state"])
        self.assertEqual(self.qa(r)["matched_branch"],"other")

    def test_mutation_codes_and_english_are_not_drugs(self):
        for q in ("Nếu đột biến EGFR L858R thì sao?","what about patients with EGFR mutations?"):
            self.assertEqual(self.chain("Erlotinib ung thư phổi không tế bào nhỏ",q)["results"][0]["ingredient"],"Erlotinib",q)

    def test_nab_paclitaxel_is_not_albumin(self):
        r=self.ask("Paclitaxel gắn albumin ung thư vú")
        self.assertEqual([x["ingredient"] for x in r["results"]],["Paclitaxel"]);self.assertNotIn("albumin",(r.get("notice") or "").lower())

    def test_glibenclamid_suggests_its_combination(self):
        self.assertIn("Glibenclamid + metformin",self.ask("Glibenclamid")["suggestions"])

    def test_recognised_names_not_reported_unrecognised(self):
        for q in ("5-FU ung thư đại tràng","Imatinib mesilat CML"):
            self.assertNotIn("Chưa nhận ra",self.ask(q).get("notice") or "",q)

    def test_this_drug_combined_with_another_keeps_both(self):
        r=self.chain("Trastuzumab ung thư vú","Thuốc này dùng phối hợp với docetaxel được không")
        self.assertEqual({x["ingredient"] for x in r["results"]},{"Trastuzumab","Docetaxel"})


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server(0);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base="http://127.0.0.1:"+str(cls.server.server_port)
        with urlopen(cls.base+"/api/health") as f:cls.token=json.load(f)["token"]
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def test_deep_json_is_400(self):
        body=('{"message":"x","state":'+'['*5000+']'*5000+'}').encode()
        req=Request(self.base+"/api/chat",data=body,headers={"Content-Type":"application/json","X-Session-Token":self.token})
        with self.assertRaises(HTTPError) as e:urlopen(req)
        self.assertEqual(e.exception.code,400)

if __name__=="__main__":unittest.main()
