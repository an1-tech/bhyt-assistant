"""Clinical-policy and conversation boundaries for the two-service pilot."""
import concurrent.futures
import datetime as dt
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Corpus
from lab_lookup import LabLookup
from server import make_server

TODAY=dt.date(2026,11,10)


class LaboratoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=Corpus()

    def ask(self, q, prev=None):
        with patch('lab_lookup.local_today',return_value=TODAY), patch('engine.api_post') as api:
            r=self.c.converse(q,prev['state'] if prev else None)
            api.assert_not_called()
        return r

    def lab(self,q,prev=None):
        return self.ask(q,prev)['lab_results'][0]

    def monitoring(self, days):
        return self.lab(f'HbA1c hôm nay để đánh giá kết quả điều trị đái tháo đường, lần trước cách {days} ngày')

    def test_general_answer_without_case_form(self):
        r=self.lab('HbA1c theo dõi đái tháo đường có điều kiện BHYT gì?')
        self.assertEqual(r['status'],'conditions_only')
        self.assertIsNone(r['pending'])
        self.assertEqual(len(r['conditions']),3)
        self.assertIn('thai kỳ',r['conditions'][2])

    def test_aliases(self):
        for text in ('Hb A1c','A1C','hemoglobin A1c','hba1c'):
            with self.subTest(text=text):self.assertEqual(self.lab(text)['id'],'hba1c')

    def test_90_plus_minus_3_boundary_is_not_automatic_denial_or_approval(self):
        for days,status in [(0,'source_condition_not_met'),(30,'source_condition_not_met'),(60,'source_condition_not_met'),(86,'source_condition_not_met'),(87,'needs_review'),(89,'needs_review'),(90,'needs_review'),(93,'needs_review'),(94,'source_conditions_match'),(120,'source_conditions_match')]:
            with self.subTest(days=days):self.assertEqual(self.monitoring(days)['status'],status)

    def test_asks_only_missing_purpose_then_date(self):
        a=self.ask('Tôi muốn chỉ định lại HbA1c hôm nay cho đái tháo đường')
        self.assertEqual(a['lab_results'][0]['pending'],'purpose')
        b=self.ask('Đánh giá kết quả điều trị',a)
        self.assertEqual(b['lab_results'][0]['pending'],'last_date')
        c=self.ask('Lần trước cách đây 60 ngày',b)
        self.assertEqual(c['lab_results'][0]['status'],'source_condition_not_met')

    def test_first_test_regimen_vs_monitoring(self):
        for purpose,status in [('xác định phác đồ điều trị','source_conditions_match'),('đánh giá kết quả điều trị','needs_review')]:
            r=self.lab('HbA1c lần đầu, đã chẩn đoán đái tháo đường, để '+purpose)
            self.assertEqual(r['status'],status)

    def test_unsupported_screening_not_assumed_treatment(self):
        for q in ('HbA1c sàng lọc đái tháo đường có BHYT không?', 'HbA1c hôm nay chưa được chẩn đoán đái tháo đường, xác định phác đồ, lần trước cách 120 ngày'):
            self.assertEqual(self.lab(q)['status'],'source_condition_not_met')

    def test_gestational_insulin_boundary(self):
        for days,status in [(29,'source_condition_not_met'),(30,'source_conditions_match'),(31,'source_conditions_match')]:
            self.assertEqual(self.lab(f'HbA1c hôm nay đái tháo đường thai kỳ điều trị insulin, lần trước cách {days} ngày')['status'],status)

    def test_gestational_negated_or_unknown_insulin(self):
        for text in ('không dùng insulin','chưa điều trị bằng insulin','đã ngừng insulin'):
            r=self.lab(f'HbA1c hôm nay đái tháo đường thai kỳ {text}, để đánh giá kết quả điều trị, lần trước cách 30 ngày')
            self.assertFalse(r['facts']['insulin'])
            self.assertEqual(r['status'],'source_condition_not_met')
        r=self.lab('HbA1c hôm nay đái tháo đường thai kỳ, chưa rõ có dùng insulin, lần trước cách 30 ngày')
        self.assertEqual(r['pending'],'insulin')

    def test_exact_date_and_leap_year_calculation(self):
        r=self.lab('HbA1c đánh giá kết quả điều trị đái tháo đường, lần trước ngày 29/02/2024, lần này ngày 01/03/2025')
        self.assertIn('cách 366 ngày',' '.join(r['reasons']))
        self.assertEqual(r['status'],'source_conditions_match')

    def test_pending_date_accepts_unlabelled_full_date(self):
        a=self.ask('HbA1c hôm nay theo dõi đái tháo đường')
        b=self.lab('01/08/2026',a)
        self.assertEqual(b['status'],'source_conditions_match')

    def test_invalid_ambiguous_future_dates_do_not_match(self):
        for suffix in ('lần trước ngày 31/02/2026','lần trước ngày 11/11/2026','lần trước 3 tháng trước','ngày 01/08/2026 và ngày 10/11/2026'):
            with self.subTest(suffix=suffix):
                self.assertEqual(self.lab('HbA1c hôm nay theo dõi đái tháo đường, '+suffix)['status'],'needs_info')

    def test_unknown_last_date_clears_previous_fact(self):
        a=self.ask('HbA1c hôm nay theo dõi đái tháo đường, lần trước cách 120 ngày')
        b=self.lab('Không nhớ ngày lần trước',a)
        self.assertNotIn('last_date',b['facts'])
        self.assertEqual(b['pending'],'last_date')
        self.assertEqual(self.lab('Không nhớ',a)['pending'],'last_date')

    def test_short_confirmation_and_question_about_insulin(self):
        a=self.ask('HbA1c hôm nay đái tháo đường thai kỳ, lần trước cách 30 ngày')
        self.assertEqual(a['lab_results'][0]['pending'],'insulin')
        self.assertEqual(self.lab('Có',a)['status'],'source_conditions_match')
        self.assertEqual(self.lab('Có dùng insulin không?',a)['pending'],'insulin')

    def test_egfr_casing_can_mean_renal_function(self):
        r=self.ask('eGFR có BHYT không?')
        self.assertEqual(r['status'],'needs_info')
        self.assertEqual(r['citations'],[])

    def test_corrected_purpose_resets_decision(self):
        a=self.ask('HbA1c hôm nay theo dõi đái tháo đường, lần trước cách 120 ngày')
        self.assertEqual(self.lab('Lần này để sàng lọc',a)['status'],'source_condition_not_met')

    def test_general_followup_returns_conditions_without_old_case(self):
        a=self.ask('HbA1c hôm nay theo dõi đái tháo đường, lần trước cách 30 ngày')
        b=self.lab('Cho tôi điều kiện chung',a)
        self.assertEqual(b['status'],'conditions_only')
        self.assertEqual(b['facts'],{})

    def test_new_explicit_case_does_not_inherit_last_date(self):
        a=self.ask('HbA1c hôm nay theo dõi đái tháo đường, lần trước cách 120 ngày')
        b=self.lab('HbA1c hôm nay theo dõi đái tháo đường',a)
        self.assertEqual(b['pending'],'last_date')

    def test_egfr_test_coverage_separate_from_drug(self):
        r=self.ask('Xét nghiệm đột biến gen EGFR điều trị ung thư phổi không tế bào nhỏ có BHYT không?')
        self.assertEqual(r['results'],[])
        self.assertEqual(r['lab_results'][0]['id'],'egfr')
        self.assertEqual(r['citations'][0]['document_id'],'TT39_2024_LABS')
        self.assertNotIn('dương tính',r['lab_results'][0]['conditions'][0])

    def test_egfr_case_followups(self):
        a=self.ask('Bệnh nhân ung thư phổi, xét nghiệm EGFR hôm nay có BHYT không?')
        self.assertEqual(a['lab_results'][0]['pending'],'disease')
        b=self.ask('Ung thư phổi không tế bào nhỏ',a)
        self.assertEqual(b['lab_results'][0]['pending'],'purpose')
        self.assertEqual(self.lab('Chẩn đoán đột biến trong điều trị',b)['status'],'source_conditions_match')

    def test_other_cancer_negation_and_screening(self):
        for q in ('Xét nghiệm EGFR ung thư vú có BHYT không?','Xét nghiệm EGFR hôm nay sàng lọc ung thư phổi không tế bào nhỏ','Xét nghiệm EGFR bệnh nhân ung thư phổi tế bào nhỏ điều trị hôm nay'):
            self.assertEqual(self.lab(q)['status'],'source_condition_not_met')
        r=self.lab('Xét nghiệm EGFR bệnh nhân chưa xác định ung thư phổi không tế bào nhỏ điều trị hôm nay')
        self.assertEqual(r['pending'],'disease')

    def test_egfr_method_and_repetition_not_inferred(self):
        for q in ('Xét nghiệm EGFR bằng NGS có điều kiện BHYT gì?','Xét nghiệm EGFR lần thứ 2 có được chi trả không?','Giá xét nghiệm EGFR bao nhiêu?'):
            self.assertEqual(self.lab(q)['status'],'needs_review')

    def test_renal_egfr_never_uses_mutation_rule(self):
        r=self.ask('eGFR mức lọc cầu thận có được BHYT chi trả không?')
        self.assertEqual(r['status'],'unknown')
        self.assertEqual(r['citations'],[])

    def test_marker_drug_question_uses_existing_engine(self):
        r=self.ask('Chưa có kết quả EGFR thì Erlotinib ung thư phổi không tế bào nhỏ có được thanh toán không?')
        self.assertEqual(r['results'][0]['ingredient'],'Erlotinib')
        self.assertNotIn('lab_results',r)
        self.assertTrue(any(c['document_id']=='TT20_2022' for c in r['citations']))

    def test_drug_marker_followup_and_explicit_switch(self):
        a=self.ask('Erlotinib ung thư phổi không tế bào nhỏ')
        b=self.ask('Chưa có kết quả EGFR thì thuốc này có được thanh toán không?',a)
        self.assertNotIn('lab_results',b)
        c=self.ask('Còn xét nghiệm EGFR có được BHYT chi trả không?',b)
        self.assertEqual(c['results'],[])
        self.assertNotIn('selected_ids',c['state'])

    def test_mixed_answer_has_independent_sources(self):
        r=self.ask('Cả xét nghiệm EGFR và thuốc Erlotinib trong ung thư phổi không tế bào nhỏ có BHYT không?')
        self.assertEqual(r['domain'],'mixed')
        self.assertEqual(r['results'][0]['ingredient'],'Erlotinib')
        self.assertEqual(r['lab_results'][0]['id'],'egfr')
        self.assertTrue({'TT20_2022','TT39_2024_LABS'}<={c['document_id'] for c in r['citations']})

    def test_unknown_drug_in_mixed_question_is_not_silently_dropped(self):
        r=self.ask('Cả xét nghiệm EGFR và thuốc Pertuzumab có được BHYT chi trả không?')
        self.assertEqual(r['domain'],'mixed')
        self.assertEqual(r['lab_results'][0]['id'],'egfr')
        self.assertIn('Pertuzumab',r['answer'])

    def test_insulin_exception_is_not_drug_lookup(self):
        r=self.ask('HbA1c đái tháo đường thai kỳ có điều trị insulin có điều kiện BHYT gì?')
        self.assertEqual(r['results'],[])

    def test_unsupported_new_test_drops_previous_lab(self):
        a=self.ask('HbA1c hôm nay theo dõi đái tháo đường, lần trước cách 120 ngày')
        b=self.ask('Còn xét nghiệm troponin có được chi trả không?',a)
        self.assertEqual(b['status'],'unknown')
        self.assertEqual(b['state'],{})
        c=self.ask('Còn xét nghiệm CRP có được chi trả không?',a)      # another listed test: its own row, no HbA1c facts
        self.assertEqual([x['id'] for x in c['lab_results']],['crp'])
        self.assertEqual(c['lab_results'][0]['facts'],{})

    def test_two_services_do_not_share_case_facts(self):
        r=self.ask('HbA1c và xét nghiệm EGFR hôm nay, lần trước cách 30 ngày có BHYT không?')
        self.assertEqual(len(r['lab_results']),2)
        self.assertTrue(all(x['status']=='conditions_only' and x['facts']=={} for x in r['lab_results']))
        self.assertEqual(r['state'],{})

    def test_signed_state_tampering_ignored(self):
        a=self.ask('HbA1c hôm nay theo dõi đái tháo đường, lần trước cách 30 ngày')
        a['state']['lab']['facts']['last_date']='2020-01-01'
        b=self.ask('Vậy hôm nay được không?',a)
        self.assertNotIn('lab_results',b)

    def test_pii_and_unsupported_snapshot_are_blocked_first(self):
        self.assertEqual(self.ask('HbA1c mã bệnh án: ABC123')['status'],'private_input')
        self.assertEqual(self.c.converse('HbA1c',as_of='2027-01-01')['status'],'unsupported_date')

    def test_threaded_requests_do_not_leak_facts(self):
        queries=[f'HbA1c hôm nay theo dõi đái tháo đường, lần trước cách {d} ngày' for d in (30,120)*5]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            answers=list(pool.map(self.c.converse,queries))
        self.assertEqual([r['lab_results'][0]['status'] for r in answers],['source_condition_not_met','source_conditions_match']*5)

    def test_source_hash_crop_and_metadata(self):
        self.assertTrue(self.c.labs.integrity_ok())
        for row in self.c.labs.services.values():
            self.assertIsNone(row['service_code']) # STT is not a billing code.
            self.assertIn('STT '+str(row['original_row']),row['locator'])
            page=self.c.labs.source_html(row['id']).decode()
            self.assertIn('id="source-row"',page)
            self.assertIn(row['image_url'],page)

    def test_changed_or_missing_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'lab_services.json').write_text(json.dumps(self.c.labs.bundle),encoding='utf-8')
            labs=LabLookup(p)
            r=labs.answer('HbA1c',{}, {'ids':['hba1c'],'kind':'lab'},TODAY)
            self.assertEqual(r['status'],'source_unavailable')
            self.assertEqual(r['citations'],[])
            self.assertNotIn('<img',labs.source_html('hba1c').decode())


class LabHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server(0)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def test_source_links_and_content_types(self):
        for path,ctype in [('/sources/labs/hba1c.html','text/html'),('/sources/labs/egfr.html','text/html'),('/sources/labs/hba1c-row.png','image/png'),('/sources/labs/egfr-row.png','image/png'),('/sources/labs/39-2024-appendix.pdf','application/pdf')]:
            with urlopen(self.base+path) as response:
                self.assertEqual(response.status,200)
                self.assertIn(ctype,response.headers['Content-Type'])
                self.assertTrue(response.read())

    def test_chat_protocol_and_metadata(self):
        with urlopen(self.base+'/api/health') as response:health=json.load(response)
        with urlopen(self.base+'/api/metadata') as response:m=json.load(response)
        self.assertEqual(m['lab_source']['service_count'],41)
        req=Request(self.base+'/api/chat',data=json.dumps({'message':'HbA1c có điều kiện BHYT gì?'}).encode(),headers={'Content-Type':'application/json','X-Session-Token':health['token']})
        with urlopen(req) as response:r=json.load(response)
        self.assertEqual(r['lab_results'][0]['status'],'conditions_only')
        self.assertIn('sig',r['state'])

    def test_source_path_traversal_is_not_served(self):
        with self.assertRaises(HTTPError) as err:urlopen(self.base+'/sources/labs/../../.env')
        self.assertEqual(err.exception.code,404)


if __name__=='__main__':unittest.main()
