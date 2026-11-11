"""All laboratory rows with their own payment condition (v1.11 completed).

41 rows: 17 from the TT39/2024 appendix text layer, 24 transcribed from the 17/VBHN-BYT
scan. Only HbA1c, the four gene tests and SCC compare case facts with the row; every other
row is quoted and says that no case comparison was made. A marker or lab value named inside
a medicine question stays with the medicine.
"""
import datetime as dt
import json
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Corpus
from server import make_server

TODAY = dt.date(2026, 11, 10)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()

    def ask(self, q, prev=None):
        with patch('lab_lookup.local_today', return_value=TODAY):
            return self.c.converse(q, prev['state'] if prev else None)

    def lab(self, q, prev=None):
        return self.ask(q, prev)['lab_results'][0]

    def ids(self, q):
        return [x['id'] for x in self.ask(q).get('lab_results', [])]

    def settle(self, q, prev=None):
        """The conclusion after the one-click confirmation that a question with unread words needs."""
        r = self.ask(q, prev)
        if r['lab_results'][0]['status'] == 'needs_confirmation':
            r = self.ask('Đúng, đối chiếu theo các dữ kiện này', r)
        return r['lab_results'][0]


class Catalogue(Base):
    def test_counts_and_transcription(self):
        rows = list(self.c.labs.services.values())
        self.assertEqual(len(rows), 41)
        self.assertEqual(sum(r['transcription'] == 'text_layer' for r in rows), 17)
        self.assertEqual(sum(r['transcription'] == 'scan_read' for r in rows), 24)
        self.assertTrue(self.c.labs.integrity_ok())
        for r in rows:
            self.assertEqual(r['quote'], '\n'.join(r['conditions']))
            self.assertIsNone(r['service_code'])
            if r['doc'] == 'tt39':
                self.assertIn(f"STT {r['original_row']} theo TT35", r['locator'])
            if r.get('rate_mode') == 'paired':
                self.assertEqual(len(r['rate']), len(r['conditions']))

    def test_only_declared_rules_compare_a_case(self):
        rules = {r['id']: r.get('rule') for r in self.c.labs.services.values() if r.get('rule')}
        self.assertEqual(rules, {'hba1c': 'hba1c', 'her2': 'gene', 'braf': 'gene', 'egfr': 'gene', 'kras': 'gene', 'scc': 'scope'})
        # A scan-read row never has a rule: its text is not machine-checked.
        self.assertFalse(any(r.get('rule') for r in self.c.labs.services.values() if r['transcription'] == 'scan_read'))

    def test_every_service_is_found_by_its_printed_name(self):
        for r in self.c.labs.services.values():
            found = self.ids('Xét nghiệm ' + r['name'] + ' có điều kiện BHYT gì?')
            self.assertIn(r['id'], found, r['name'])

    def test_specific_name_wins_over_contained_name(self):
        expect = {'Định lượng Pro-BNP': ['probnp'], 'NT-proBNP có điều kiện gì': ['probnp'], 'Định lượng BNP': ['bnp'],
                  'kháng thể kháng tiểu cầu trực tiếp': ['platelet_ab_direct'], 'HIV kháng thuốc giải trình tự gene': ['hiv_resistance'],
                  'Xét nghiệm giải trình tự gen': ['gene_sequencing'], 'HCV genotype giải trình tự gene': ['hcv_genotype'],
                  'CA 15-3': ['tumor_markers'], 'định lượng CEA': ['tumor_markers'], 'HBV DNA': ['hbv_load'], 'tải lượng HCV': ['hcv_load'],
                  'procalcitonin': ['procalcitonin'], 'PIVKA-II': ['pivka']}
        for q, ids in expect.items():
            self.assertEqual(self.ids(q), ids, q)
        self.assertEqual(sorted(self.ids('xét nghiệm HLA')), ['hla_ssp', 'hla_sso'].__class__(sorted(['hla_ssp', 'hla_sso'])))
        self.assertEqual(sorted(self.ids('kháng thể kháng tiểu cầu')), ['platelet_ab_direct', 'platelet_ab_flow'])

    def test_loose_name_says_what_the_row_covers(self):
        r = self.lab('công thức máu có được BHYT không')
        self.assertEqual(r['id'], 'cbc_auto')
        self.assertTrue(any('không phải mọi xét nghiệm công thức máu' in n for n in r['notes']))
        self.assertEqual(r['rate_mode'], 'paired')

    def test_scan_rows_are_flagged_and_never_conclude(self):
        for q in ('Định lượng Pro-BNP hôm nay cho bệnh nhân suy tim', 'CMV Real-time PCR sau ghép tạng', 'Định lượng PIVKA u gan'):
            r = self.lab(q)
            self.assertEqual(r['status'], 'conditions_only', q)
            self.assertEqual(r['transcription'], 'scan_read')
            self.assertTrue(any('bản scan' in n and 'chưa được thẩm định' in n for n in r['notes']), q)
            self.assertEqual(r['citation']['document_id'], 'TT35_VBHN17_LABS')
            self.assertIn('chưa tự đối chiếu ca bệnh', r['conclusion'])

    def test_generic_text_layer_rows_never_conclude(self):
        for q in ('CRP hôm nay cho bệnh nhân sốt 39 độ nghi nhiễm trùng', 'HBV DNA lần đầu trước điều trị viêm gan B', 'Procalcitonin nhiễm khuẩn huyết lần 2 trong 24 giờ'):
            r = self.lab(q)
            self.assertEqual(r['status'], 'conditions_only', q)
            self.assertEqual(r['highlight'], [])
        self.assertTrue(self.lab('định lượng CRP')['rate'])            # Danh mục 1: rate column quoted
        self.assertIn('01 lần/mỗi 24 giờ', ' '.join(self.lab('procalcitonin')['rate']))

    def test_source_typo_is_kept_and_noted(self):
        r = self.lab('tải lượng HCV')
        self.assertIn('viêm ban vi rút C', r['conditions'][0])
        self.assertTrue(any('giữ nguyên văn' in n for n in r['notes']))


class GeneAndScope(Base):
    def test_disease_inside_and_outside_the_row(self):
        cases = [('Xét nghiệm HER2 cho bệnh nhân ung thư vú đang điều trị hôm nay', 'source_conditions_match'),
                 ('Xét nghiệm HER2 cho bệnh nhân ung thư dạ dày đang điều trị hôm nay', 'source_conditions_match'),
                 ('Xét nghiệm HER2 cho bệnh nhân ung thư đại trực tràng đang điều trị hôm nay', 'source_condition_not_met'),
                 ('Xét nghiệm KRAS cho bệnh nhân ung thư đại trực tràng đang điều trị hôm nay', 'source_conditions_match'),
                 ('Xét nghiệm KRAS cho bệnh nhân ung thư phổi không tế bào nhỏ đang điều trị hôm nay', 'source_condition_not_met'),
                 ('Xét nghiệm BRAF cho bệnh nhân ung thư tuyến giáp đang điều trị hôm nay', 'source_conditions_match'),
                 ('Xét nghiệm BRAF cho bệnh nhân ung thư vú đang điều trị hôm nay', 'source_condition_not_met'),
                 ('Xét nghiệm BRAF tầm soát ung thư đại trực tràng hôm nay', 'source_condition_not_met')]
        for q, status in cases:
            self.assertEqual(self.lab(q)['status'], status, q)

    def test_negated_disease_is_not_the_named_disease(self):
        r = self.lab('Xét nghiệm HER2 hôm nay, bệnh nhân không phải ung thư vú mà là ung thư dạ dày đang điều trị')
        self.assertEqual(r['facts']['disease'], 'gastric')
        self.assertEqual(r['status'], 'source_conditions_match')
        self.assertEqual(self.lab('Xét nghiệm EGFR không phải cho ung thư phổi không tế bào nhỏ')['status'], 'source_condition_not_met')
        self.assertEqual(self.lab('Xét nghiệm KRAS hôm nay cho bệnh nhân nghi ngờ ung thư đại trực tràng')['pending'], 'disease')

    def test_unspecified_or_several_diseases_ask(self):
        a = self.ask('Bệnh nhân ung thư phổi, xét nghiệm HER2 hôm nay có BHYT không?')
        self.assertEqual(a['lab_results'][0]['pending'], 'disease')
        b = self.lab('Có', a)                    # three diseases in the row: "Có" names none of them
        self.assertEqual(b['pending'], 'disease')
        self.assertEqual(self.lab('Xét nghiệm HER2 hôm nay cho bệnh nhân ung thư vú hoặc ung thư đại trực tràng')['pending'], 'disease')

    def test_method_and_repetition_are_not_in_the_row(self):
        for q in ('Xét nghiệm HER2 bằng FISH cho ung thư vú có được BHYT không', 'HER2 hóa mô miễn dịch ung thư dạ dày có điều kiện BHYT gì',
                  'Xét nghiệm KRAS bằng NGS', 'Xét nghiệm EGFR lần 2 khi tiến triển, ung thư phổi không tế bào nhỏ đang điều trị'):
            self.assertEqual(self.lab(q)['status'], 'needs_review', q)

    def test_scc_checks_the_disease_only(self):
        r = self.lab('xét nghiệm SCC ung thư cổ tử cung')
        self.assertEqual(r['status'], 'conditions_only')
        self.assertTrue(any('tế bào vảy' in x for x in r['reasons']))
        self.assertEqual(self.lab('xét nghiệm SCC ung thư vú')['status'], 'source_condition_not_met')
        self.assertEqual(self.lab('định lượng SCC')['reasons'], [])


class DrugOrLab(Base):
    def drug_only(self, q, name=None):
        r = self.ask(q)
        self.assertNotIn('lab_results', r, q)
        if name:
            self.assertEqual([x['ingredient'] for x in r['results']], [name], q)

    def test_marker_as_drug_condition_stays_with_the_drug(self):
        self.drug_only('Trastuzumab ung thư vú HER2 dương tính', 'Trastuzumab')
        self.drug_only('Trastuzumab ung thư vú không xét nghiệm HER2', 'Trastuzumab')
        self.drug_only('Cetuximab ung thư đại trực tràng KRAS tự nhiên', 'Cetuximab')
        self.drug_only('Cetuximab ung thư đại trực tràng chưa có kết quả xét nghiệm KRAS', 'Cetuximab')

    def test_test_question_naming_a_drug_is_a_test_question(self):
        self.assertEqual(self.ids('Xét nghiệm KRAS trước khi dùng Cetuximab có được BHYT không'), ['kras'])
        self.assertEqual(self.ids('Xét nghiệm tải lượng HBV cho bệnh nhân đang dùng Tenofovir có được BHYT thanh toán không'), ['hbv_load'])

    def test_lab_value_in_a_drug_question_is_not_an_order(self):
        self.drug_only('Metformin đái tháo đường type 2 HbA1c 9%', 'Metformin')
        self.drug_only('Insulin cho bệnh nhân HbA1c cao có được BHYT không')
        self.drug_only('HbA1c 8% thì dùng thuốc gì')
        self.drug_only('Entecavir viêm gan B', 'Entecavir')
        self.drug_only('Tenofovir viêm gan B tải lượng HBV cao')

    def test_hba1c_with_insulin_or_a_drug_as_context_is_still_the_test(self):
        self.assertEqual(self.ids('HbA1c đái tháo đường thai kỳ có điều trị insulin có điều kiện BHYT gì?'), ['hba1c'])
        self.assertEqual(self.ids('Bệnh nhân đang dùng Metformin, chỉ định HbA1c hôm nay để đánh giá kết quả điều trị đái tháo đường, lần trước cách 100 ngày'), ['hba1c'])

    def test_test_not_in_the_lists(self):
        r = self.ask('xét nghiệm troponin có được BHYT không')
        self.assertEqual((r['status'], r['citations']), ('unknown', []))
        self.assertIn('không có nghĩa là BHYT không chi trả', r['answer'])
        self.assertIn('41 dòng', r['answer'])
        self.assertEqual(len(r['lab_links']), 2)
        r = self.ask('Định lượng albumin máu có được BHYT không')      # albumin is also a medicine
        self.assertEqual((r['status'], r.get('domain'), r['results']), ('unknown', 'lab', []))

    def test_other_technical_service_points_to_the_documents(self):
        r = self.ask('chụp PET/CT ung thư phổi có được BHYT không')
        self.assertEqual(r['status'], 'unknown')
        self.assertIn('chưa được nạp', r['answer'])
        self.assertEqual(len(r['lab_links']), 2)

    def test_private_input_blocked_for_any_test(self):
        self.assertEqual(self.ask('Nguyễn Văn An 0912345678 làm xét nghiệm KRAS')['status'], 'private_input')


class HbA1cReading(Base):
    def test_the_doctors_question_in_one_sentence(self):
        r = self.lab('HbA1c cho bệnh nhân đái tháo đường type 2 để đánh giá kết quả điều trị, lần trước làm ngày 01/08/2026, hôm nay có được BHYT thanh toán không?')
        self.assertEqual(r['status'], 'source_conditions_match')
        self.assertIn('cách 101 ngày', ' '.join(r['reasons']))
        self.assertEqual(r['highlight'], [1])

    def test_marked_branch_follows_the_purpose(self):
        self.assertEqual(self.lab('HbA1c hôm nay xác định phác đồ cho đái tháo đường, lần trước cách 100 ngày')['highlight'], [0])
        self.assertEqual(self.lab('HbA1c hôm nay đái tháo đường thai kỳ điều trị insulin, lần trước cách 20 ngày')['highlight'], [2])
        self.assertEqual(self.lab('HbA1c có điều kiện BHYT gì?')['highlight'], [])
        self.assertEqual(self.lab('HbA1c hôm nay tầm soát')['highlight'], [])

    def test_unconfirmed_diabetes_is_not_confirmed(self):
        for q in ('Bệnh nhân tiền đái tháo đường làm HbA1c hôm nay để theo dõi', 'HbA1c hôm nay cho bệnh nhân chưa có chẩn đoán đái tháo đường, để theo dõi',
                  'HbA1c hôm nay cho bệnh nhân nghi ngờ đái tháo đường, để theo dõi', 'HbA1c hôm nay, rối loạn dung nạp glucose, để theo dõi'):
            r = self.settle(q)
            self.assertIs(r['facts']['diabetes'], False, q)
            self.assertEqual(r['status'], 'source_condition_not_met', q)

    def test_negated_purpose(self):
        r = self.lab('HbA1c hôm nay không phải để theo dõi mà để chẩn đoán')
        self.assertEqual(r['facts'].get('purpose'), 'screening')
        self.assertEqual(r['status'], 'source_condition_not_met')
        r = self.lab('HbA1c hôm nay cho bệnh nhân đã được chẩn đoán đái tháo đường, để theo dõi điều trị, lần trước cách 100 ngày')
        self.assertEqual(r['status'], 'source_conditions_match')       # "đã được chẩn đoán" is not a diagnostic purpose

    def test_months_and_weeks(self):
        base = 'HbA1c hôm nay đánh giá kết quả điều trị đái tháo đường, lần trước '
        for text, status in [('cách đây 2 tháng', 'source_condition_not_met'), ('4 tháng trước', 'source_conditions_match'), ('3 tháng trước', 'needs_info'),
                             ('cách 6 tuần', 'source_condition_not_met'), ('cách 14 tuần', 'source_conditions_match'), ('cách 13 tuần', 'needs_review')]:
            self.assertEqual(self.lab(base + text)['status'], status, text)
        r = self.lab(base + 'cách đây 2 tháng')
        self.assertIn('ước 56–62 ngày', ' '.join(r['reasons']))
        self.assertNotIn('last_date', r['facts'])
        self.assertEqual(self.lab('HbA1c hôm nay đái tháo đường thai kỳ điều trị insulin, lần trước 1 tháng trước')['pending'], 'last_date')

    def test_exact_date_replaces_a_month_estimate(self):
        a = self.ask('HbA1c hôm nay theo dõi đái tháo đường, lần trước 3 tháng trước')
        self.assertEqual(a['lab_results'][0]['pending'], 'last_date')
        b = self.lab('ngày 01/08/2026', a)
        self.assertEqual(b['status'], 'source_conditions_match')
        self.assertNotIn('last_range', b['facts'])

    def test_tomorrow_is_not_treated_as_today(self):
        r = self.lab('HbA1c ngày mai đánh giá điều trị đái tháo đường, lần trước cách 100 ngày')
        self.assertEqual(r['status'], 'needs_review')
        self.assertEqual(r['facts']['planned_date'], '2026-11-11')

    def test_renal_egfr(self):
        self.assertEqual(self.ask('eGFR cho bệnh nhân suy thận có được BHYT không')['status'], 'unknown')


class LabHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def test_every_viewer_page_and_image_is_served(self):
        with urlopen(self.base + '/api/metadata') as response:
            meta = json.load(response)['lab_source']
        self.assertEqual((meta['text_layer_count'], meta['scan_read_count']), (17, 24))
        images = set()
        for s in meta['services']:
            with urlopen(self.base + s['viewer_url'].split('#')[0]) as response:
                page = response.read().decode()
            self.assertIn('id="source-row"', page)
            found = [x.split('"')[0] for x in page.split('src="')[1:]]
            self.assertTrue(found, s['id'])
            images.update(found)
            if s['transcription'] == 'scan_read':
                self.assertIn('Đỗ Quốc An đọc', page)
        for url in images:
            with urlopen(self.base + url) as response:
                self.assertIn('image/png', response.headers['Content-Type'])
        with urlopen(self.base + '/sources/labs/17-vbhn-2024.pdf') as response:
            self.assertIn('application/pdf', response.headers['Content-Type'])

    def test_files_outside_the_bundle_are_not_served(self):
        for path in ('/sources/labs/unknown.html', '/sources/labs/secret.png', '/sources/labs/../lab_services.json'):
            with self.assertRaises(HTTPError) as err:
                urlopen(self.base + path)
            self.assertEqual(err.exception.code, 404, path)


if __name__ == '__main__':
    unittest.main()
