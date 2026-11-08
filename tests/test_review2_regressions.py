"""Regression tests for the second independent review of commit 9850aec (08/11/2026).

Reviewer A: condition reading and context. Reviewer B: drug identification,
conversation state, privacy. Every case below failed before the fix.
"""
import unittest
from engine import Corpus, private_input


class Review2Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=Corpus()

    def chain(self,*messages):
        state={};r=None
        for m in messages:
            r=self.c.converse(m,state);state=r.get("state") or {}
        return r

    def drugs(self,*messages):return [x["ingredient"] for x in self.chain(*messages)["results"]]
    def status(self,*messages):
        r=self.chain(*messages)
        return r["results"][0]["question_answer"]["status"] if r["results"] else r["status"]
    def rate(self,*messages):
        r=self.chain(*messages)
        return (r["results"][0]["question_answer"].get("source_rate") or {}).get("percentage")


class DrugIdentificationTests(Review2Base):
    def test_b1_unknown_lowercase_or_code_does_not_reuse_previous_drug(self):
        for follow in ("Còn keytruda thì sao?","Vậy kadcyla điều trị ung thư vú thì sao?","Còn T-DM1 thì sao"):
            r=self.chain("Trastuzumab ung thư vú",follow)
            self.assertFalse(r["results"],follow);self.assertEqual(r["status"],"unknown_drug",follow)
        self.assertEqual(self.status("Imatinib CML","Còn glivec thì sao"),"unknown_drug")

    def test_b1_known_code_names_resolve(self):
        self.assertEqual(self.drugs("5-FU"),["Fluorouracil (5-FU)"])
        self.assertEqual(self.drugs("Trastuzumab ung thư vú","Nếu dùng 5-FU thì sao?"),["Fluorouracil (5-FU)"])

    def test_b2_switching_to_related_drug_without_condition_word(self):
        self.assertEqual(self.drugs("Nilotinib điều trị CML","Còn Imatinib thì sao?"),["Imatinib"])
        self.assertEqual(self.drugs("Nilotinib điều trị CML","Nếu kháng Imatinib?"),["Nilotinib"])

    def test_b3_salt_words_are_not_drug_names(self):
        cases={"Gentamicin sulfat":["Gentamicin"],"Metoprolol tartrat":["Metoprolol"],"Ipratropium bromid khí dung":["Ipratropium"],
               "Dexamethason natri phosphate":["Dexamethason"],"Zoledronic acid điều trị tăng calci máu":["Zoledronic acid"]}
        for q,expected in cases.items():
            self.assertEqual([g[0]["ingredient"] for g in self.c.resolve(q)],expected,q)
        self.assertNotIn("Magnesi sulfat",[g[0]["ingredient"] for g in self.c.resolve("Magnesi lactat")])

    def test_b4_con_is_not_alcohol(self):
        self.assertEqual(self.drugs("Trastuzumab ung thư vú","Nếu tỷ lệ còn 70% thì sao?"),["Trastuzumab"])
        self.assertNotIn("Cồn 70°",self.drugs("Trastuzumab ung thư vú","Còn 70 tuổi thì sao"))
        self.assertEqual([g[0]["ingredient"] for g in self.c.resolve("Cồn 70° sát khuẩn")],["Cồn 70°"])

    def test_b5_conjugate_spellings(self):
        for q in ("trastuzumab emtansin ung thư vú","Trastuzumab DM1 ung thư vú","Trastuzumab-MCC-DM1 ung thư vú"):
            r=self.chain(q);self.assertFalse(r["results"],q);self.assertEqual(r["status"],"unknown_drug",q)

    def test_b7_patient_identifiers_are_blocked(self):
        for q in ("DN4797932251234 Trastuzumab ung thư vú","số thẻ BHYT là HC4010123456789","Trastuzumab, SĐT 0912 345 678",
                  "Trastuzumab +84912345678","Họ tên: Nguyễn Văn An","mã bệnh án 2026-0012345","bệnh nhân Nguyễn Văn An, sinh 12/03/1965"):
            self.assertTrue(private_input(q),q)
            self.assertEqual(self.chain(q)["status"],"private_input",q)
        for q in ("Trastuzumab 440 mg ung thư vú","Bệnh nhân Trastuzumab Ung thư vú HER2 dương tính","Liều 100000 đơn vị"):
            self.assertFalse(private_input(q),q)

    def test_b8_listed_synonyms_resolve(self):
        self.assertEqual(self.drugs("Methylprednisolon"),["Methyl prednisolon"])
        self.assertEqual(self.drugs("Leucovorin"),["Calci folinat (folinic acid, leucovorin)"])

    def test_b9_capitalised_misspelling_gets_suggestion(self):
        r=self.chain("Paclitaxen")
        self.assertEqual(r["status"],"ambiguous");self.assertIn("Paclitaxel",r["suggestions"])
        r=self.chain("Pertuzumab ung thư vú")
        self.assertEqual(r["status"],"unknown_drug");self.assertNotIn("Trastuzumab",r.get("suggestions",[]))

    def test_b10_english_clinical_words_are_not_drugs(self):
        self.assertEqual(self.drugs("Trastuzumab ung thu vu","Neu Benh nhan Stage IV thi sao"),["Trastuzumab"])
        for w in ("Please","Mutation","Luminal"):
            self.assertEqual(self.c.unrecognized_names(w+" B"),[],w)

    def test_b11_followup_after_two_drugs_keeps_both(self):
        self.assertEqual(self.drugs("Trastuzumab và Paclitaxel ung thư vú","Còn ung thư dạ dày?"),["Trastuzumab","Paclitaxel"])

    def test_b12_drug_followups_without_disease_word(self):
        for q in ("Thuốc này cần hội chẩn không","Tỷ lệ thanh toán bao nhiêu?","Có cần xét nghiệm FISH không?"):
            self.assertEqual(self.drugs("Trastuzumab ung thư vú",q),["Trastuzumab"],q)

    def test_b13_two_named_drugs_are_both_answered(self):
        self.assertEqual(set(self.drugs("Imatinib hay Nilotinib cho CML kháng Imatinib")),{"Imatinib","Nilotinib"})
        self.assertEqual(set(self.drugs("Nilotinib hoặc Imatinib cho CML")),{"Imatinib","Nilotinib"})
        self.assertEqual(self.drugs("Bendamustine CLL không đáp ứng Fludarabin"),["Bendamustine"])

    def test_b14_comma_list_is_not_a_combination(self):
        self.assertEqual(self.drugs("Paracetamol, ibuprofen có BHYT không"),["Paracetamol (acetaminophen)","Ibuprofen"])
        self.assertEqual(self.drugs("Paracetamol + ibuprofen có BHYT không"),["Paracetamol + ibuprofen"])
        r=self.chain("Amoxicilin và acid clavulanic")
        self.assertIn("phối hợp",r.get("notice",""))

    def test_b15_route_buttons_do_not_loop(self):
        r=self.chain("Morphin tiêm hoặc uống có BHYT không")
        self.assertEqual(r["suggestion_mode"],"replace")
        for s in r["suggestions"]:
            self.assertEqual(self.chain(s)["status"],"answered",s)

    def test_b16_unrelated_word_gets_no_blood_product(self):
        self.assertNotIn("Khối bạch cầu",self.chain("hội chẩn là gì").get("suggestions",[]))

    def test_b18_combination_without_salt_word(self):
        self.assertEqual(self.drugs("Tegafur gimeracil oteracil ung thư dạ dày di căn"),["Tegafur + gimeracil + oteracil kali"])

    def test_b17_tolerance_explanation(self):
        r=self.chain("Nilotinib CML dung nạp tốt Imatinib")
        a=r["results"][0]["question_answer"]
        self.assertEqual(a["status"],"source_condition_not_met");self.assertNotIn("chưa dùng thuốc trước đó",a["conclusion"])

    def test_b19_switch_drug_keeps_disease(self):
        r=self.chain("Erlotinib ung thư phổi không tế bào nhỏ","Còn gefitinib?")
        self.assertEqual(r["results"][0]["ingredient"],"Gefitinib")
        self.assertEqual(r["results"][0]["question_answer"]["matched_branch"],"nsclc")


class ConditionReadingTests(Review2Base):
    def test_a1_missing_note_conditions_now_checked(self):
        for q in ("Trastuzumab ung thư dạ dày chưa di căn, HER2 dương tính","Trastuzumab ung thư dạ dày giai đoạn sớm HER2 dương tính",
                  "Bendamustine CLL Binet A không phù hợp fludarabin","Bendamustine u lympho không Hodgkin tế bào B lớn lan tỏa tiến triển sau rituximab",
                  "Sorafenib ung thư tuyến giáp thể tủy kháng iod phóng xạ","Sorafenib ung thư tuyến giáp thể không biệt hóa kháng iod",
                  "Sorafenib ung thư thận giai đoạn sớm","Cetuximab ung thư đầu cổ không phải tế bào vảy","Rituximab u lympho không Hodgkin tế bào T CD20 dương tính"):
            self.assertEqual(self.status(q),"source_condition_not_met",q)
        self.assertEqual(self.status("Trastuzumab ung thư dạ dày di căn HER2 dương tính"),"conditional_coverage")
        self.assertEqual(self.status("Trastuzumab ung thư dạ dày","Nếu di căn thì sao?"),"conditional_coverage")
        self.assertEqual(self.rate("Sorafenib ung thư tuyến giáp thể nhú, đã thất bại điều trị iod phóng xạ"),50)

    def test_a2_peritoneal_mesothelioma_is_not_pleural(self):
        self.assertNotEqual(self.status("Pemetrexed u trung biểu mô phúc mạc"),"conditional_coverage")
        self.assertEqual(self.rate("Pemetrexed u trung biểu mô màng phổi"),50)

    def test_a3_negated_metastasis(self):
        for q in ("Cetuximab ung thư đại trực tràng chưa có dấu hiệu di căn RAS tự nhiên","Cetuximab ung thư đại trực tràng không thấy di căn, RAS tự nhiên",
                  "Tegafur + gimeracil + oteracil kali ung thư dạ dày không có dấu hiệu di căn","Tegafur + gimeracil + oteracil kali ung thư dạ dày tiến xa tại chỗ",
                  "Cetuximab ung thư đại trực tràng giai đoạn III di căn hạch RAS tự nhiên"):
            self.assertEqual(self.status(q),"source_condition_not_met",q)
        self.assertEqual(self.status("Cetuximab ung thư đại trực tràng stage IV RAS tự nhiên"),"conditional_coverage")

    def test_a4_ras_wild_type_wordings(self):
        for q in ("di căn không phát hiện đột biến RAS","di căn không thấy đột biến KRAS NRAS","di căn chưa có đột biến RAS","di căn RAS âm tính"):
            self.assertEqual(self.status("Cetuximab ung thư đại trực tràng "+q),"conditional_coverage",q)
        self.assertEqual(self.status("Cetuximab ung thư đại trực tràng di căn KRAS G12D"),"source_condition_not_met")

    def test_a5_inability_wordings(self):
        for q in ("Nilotinib CML không thể dung nạp imatinib","Nilotinib CML không còn dung nạp imatinib"):
            self.assertEqual(self.rate(q),80,q)
        self.assertEqual(self.rate("Bendamustine CLL Binet C không còn phù hợp với fludarabin"),50)
        self.assertEqual(self.status("Nilotinib CML không kháng Imatinib"),"source_condition_not_met")

    def test_a6_first_time_does_not_override_explicit_failure(self):
        self.assertEqual(self.rate("Nilotinib CML lần đầu dùng nilotinib sau khi kháng imatinib"),80)
        self.assertEqual(self.rate("Bendamustine u lympho không Hodgkin diễn tiến chậm, lần đầu dùng bendamustine sau khi thất bại rituximab"),50)
        self.assertEqual(self.rate("Abiraterone ung thư tiền liệt tuyến thất bại điều trị nội tiết, lần đầu dùng abiraterone"),30)
        self.assertEqual(self.rate("Abiraterone ung thư tiền liệt tuyến thất bại nội tiết đầu tay"),30)
        self.assertEqual(self.status("Nilotinib CML điều trị đầu tay"),"source_condition_not_met")

    def test_a7_yes_no_question_khong_is_not_negation(self):
        self.assertEqual(self.rate("erlotinib co duoc bhyt tra khong egfr duong tinh ung thu phoi khong te bao nho"),50)

    def test_a8_egfr_mutation_vocabulary(self):
        for q in ("EGFR wild-type","không có đột biến EGFR"):
            self.assertEqual(self.status("Erlotinib ung thư phổi không tế bào nhỏ "+q),"source_condition_not_met",q)
        for q in ("có đột biến EGFR","EGFR exon 19"):
            r=self.chain("Erlotinib ung thư phổi không tế bào nhỏ "+q)
            self.assertEqual(r["results"][0]["question_answer"]["requirements"][0]["status"],"met",q)

    def test_a9_test_not_done_is_unknown(self):
        for q in ("không xét nghiệm HER2","không có kết quả HER2","HER2 đang chờ kết quả"):
            a=self.chain("Trastuzumab ung thư vú "+q)["results"][0]["question_answer"]
            self.assertEqual(a["requirements"][0]["status"],"unknown",q)
            self.assertIn("chưa rõ",a["conclusion"],q)

    def test_a10_benh_nhan_in_followup_keeps_context(self):
        self.assertEqual(self.status("Trastuzumab ung thư vú HER2 dương tính","Nếu bệnh nhân HER2 âm tính thì sao?"),"source_condition_not_met")
        self.assertEqual(self.status("Cetuximab ung thư đại trực tràng di căn","Nếu bệnh nhân RAS đột biến thì sao?"),"source_condition_not_met")

    def test_a11_thay_is_not_hay(self):
        a=self.chain("Cetuximab ung thư đại trực tràng di căn không thấy đột biến KRAS NRAS")["results"][0]["question_answer"]
        self.assertEqual({r["label"]:r["status"] for r in a["requirements"]},{"di căn":"met","RAS":"met"})

    def test_a12_unrelated_or_and_fish_decides(self):
        a=self.chain("Trastuzumab ung thư vú HER2 dương tính và di căn gan hoặc phổi")["results"][0]["question_answer"]
        self.assertEqual(a["requirements"][0]["status"],"met")
        self.assertEqual(self.status("Trastuzumab ung thư vú HER2 IHC 2+ FISH âm tính"),"source_condition_not_met")
        self.assertEqual(self.status("Trastuzumab ung thư vú HER2 IHC 2+ FISH dương tính"),"conditional_coverage")

    def test_a13_poor_response_is_failure(self):
        self.assertEqual(self.rate("Sorafenib ung thư tuyến giáp biệt hóa, iod phóng xạ đáp ứng kém"),50)
        r=self.chain("Nilotinib CML imatinib đáp ứng kém")
        self.assertEqual([x["ingredient"] for x in r["results"]],["Nilotinib"]);self.assertEqual(r["results"][0]["question_answer"]["source_rate"]["percentage"],80)

    def test_a15_everolimus_no_cancer(self):
        a=self.chain("Everolimus chống thải ghép thận, bệnh nhân không có ung thư")["results"][0]["question_answer"]
        self.assertEqual(a["matched_branch"],"other")

    def test_a16_abiraterone_consistent(self):
        for q in ("chưa điều trị nội tiết, chưa hóa trị","chưa điều trị nội tiết và hóa trị"):
            self.assertEqual(self.status("Abiraterone ung thư tiền liệt tuyến "+q),"source_condition_not_met",q)
        self.assertEqual(self.rate("Abiraterone ung thư tiền liệt tuyến thất bại với ADT"),30)

    def test_a_p3_items(self):
        self.assertEqual(self.status("Cetuximab ung thư đại trực tràng di căn","RAS đột biến"),"source_condition_not_met")
        self.assertEqual(self.status("Rituximab u lympho không Hodgkin tế bào B","CD20 âm tính"),"source_condition_not_met")
        self.assertEqual(self.status("Trastuzumab ung thư vú không phải HER2 âm tính"),"conditional_coverage")
        a=self.chain("Doxorubicin dạng liposome")["results"][0]["question_answer"]
        self.assertEqual(a["matched_branch"],"liposome");self.assertIn("50%",a["conclusion"])
        r=self.chain("Trastuzumab ung thư dạ dày, bệnh nhân không có ung thư vú")
        self.assertEqual(r["results"][0]["question_answer"]["matched_branch"],"gastric")
        self.assertEqual(self.rate("Bendamustine u lympho không Hodgkin thể nang, tái phát sau rituximab"),50)

if __name__=="__main__":unittest.main()
