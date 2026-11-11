"""External review of the completed lab lookup (2026-11-11): eight confirmed defects.

The cause of 1–3 was the same: negation and doubt were read phrase by phrase. A fact is now
read inside its own clause — 'no' only when a negation governs it, 'unknown' on doubt, plan,
question or double negation — and anything but a plain yes/no is asked back.
"""
import datetime as dt
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Corpus
from lab_lookup import clause_list, governed, mentions, verdict, F_USE, F_IS

TODAY = dt.date(2026, 11, 10)
GDM = 'HbA1c hôm nay theo dõi đái tháo đường thai kỳ, {}, lần trước cách 35 ngày'


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()

    def ask(self, q, prev=None, corpus=None):
        with patch('lab_lookup.local_today', return_value=TODAY):
            return (corpus or self.c).converse(q, prev['state'] if prev else None)

    def lab(self, q, prev=None):
        return self.ask(q, prev)['lab_results'][0]


class ReadingMechanism(unittest.TestCase):
    def state(self, text, keyword='insulin', fillers=F_USE, **kw):
        return verdict(mentions(clause_list(text), keyword, fillers, **kw))

    def test_states(self):
        for text, expected in [('đang dùng insulin', 'yes'), ('không còn dùng insulin', 'no'), ('chưa có chỉ định dùng insulin', 'no'),
                               ('đã dừng insulin', 'no'), ('đã dùng insulin', 'yes'), ('dự kiến dùng insulin', 'unknown'),
                               ('có thể sẽ dùng insulin', 'unknown'), ('có dùng insulin không', 'unknown'), ('không phải không dùng insulin', 'unknown'),
                               ('chưa ngừng insulin', 'unknown'), ('không nhớ có dùng insulin', 'unknown'), ('không sốt, có dùng insulin', 'yes'),
                               ('không dùng thuốc viên mà dùng insulin', 'yes'), ('đang dùng insulin, sau đó không dùng insulin', 'unknown')]:
            self.assertEqual(self.state(text, stoppable=True), expected, text)
        self.assertEqual(self.state('trước đây dùng insulin nay đã ngưng', stoppable=True), 'no')

    def test_negation_inside_a_disease_name_is_not_a_negation(self):
        c = clause_list('ung thư phổi không tế bào nhỏ đang điều trị')[0]
        self.assertIn('ktbn', c)
        self.assertEqual(self.state('ung thư phổi không tế bào nhỏ đang điều trị', 'dieu tri', {'dang'}), 'yes')
        self.assertEqual(self.state('ung thư phổi không tế bào nhỏ không hút thuốc đang điều trị', 'dieu tri', {'dang'}), 'yes')
        self.assertEqual(self.state('ung thư phổi không tế bào nhỏ chưa điều trị', 'dieu tri', {'dang'}), 'no')

    def test_stopping_applies_to_treatments_only(self):
        self.assertEqual(self.state('ung thư vú đã ngừng điều trị', 'ung thu vu', F_IS), 'yes')
        m = mentions(clause_list('chưa loại trừ ung thư vú'), 'ung thu vu', F_IS)[0]
        self.assertEqual(m[:2], ('unknown', 'double'))
        self.assertEqual(governed('khong phai ung thu vu', 11, 21, F_IS), ('no', 'khong'))


class Finding1Insulin(Base):
    def test_not_using_insulin_is_not_the_30_day_branch(self):
        for text in ('không còn dùng insulin', 'chưa có chỉ định dùng insulin', 'đã dừng insulin', 'hết dùng insulin', 'không cần insulin', 'chưa phải dùng insulin',
                     'không tiêm insulin', 'trước đây dùng insulin nay đã ngưng'):
            r = self.lab(GDM.format(text))
            self.assertIs(r['facts'].get('insulin'), False, text)
            self.assertEqual(r['status'], 'source_condition_not_met', text)     # 35 days against the ordinary 90 ± 3 branch
            self.assertEqual(r['highlight'], [1], text)

    def test_planned_or_unclear_insulin_is_asked(self):
        for text in ('dự kiến dùng insulin', 'có thể sẽ dùng insulin', 'chưa rõ có dùng insulin', 'không phải không dùng insulin', 'da dung insulin'):
            r = self.lab(GDM.format(text))
            self.assertNotIn('insulin', r['facts'], text)
            self.assertEqual(r['pending'], 'insulin', text)

    def test_using_insulin_still_matches(self):
        for text in ('đang dùng insulin', 'điều trị bằng insulin', 'không dùng thuốc viên mà dùng insulin', 'đã chuyển sang insulin'):
            self.assertEqual(self.lab(GDM.format(text))['status'], 'source_conditions_match', text)


class Finding2FirstTest(Base):
    def test_not_the_first_time_needs_the_previous_date(self):
        for q in ('HbA1c hôm nay để xác định phác đồ cho bệnh nhân đã được chẩn đoán đái tháo đường. Lần này không phải lần đầu.',
                  'HbA1c hôm nay để xác định phác đồ cho bệnh nhân đái tháo đường, chưa phải lần đầu',
                  'HbA1c hôm nay để xác định phác đồ cho bệnh nhân đái tháo đường, không phải chưa từng làm'):
            r = self.lab(q)
            self.assertIs(r['facts'].get('first_test'), False, q)
            self.assertEqual((r['status'], r['pending']), ('needs_info', 'last_date'), q)

    def test_same_in_a_follow_up(self):
        a = self.ask('HbA1c hôm nay để xác định phác đồ cho bệnh nhân đã được chẩn đoán đái tháo đường')
        b = self.lab('Không phải lần đầu', a)
        self.assertEqual((b['status'], b['pending']), ('needs_info', 'last_date'))
        self.assertEqual(self.lab('Lần đầu', a)['status'], 'source_conditions_match')
        self.assertEqual(self.lab('chưa làm lần nào', a)['status'], 'source_conditions_match')

    def test_first_here_but_done_elsewhere(self):
        r = self.lab('HbA1c hôm nay xác định phác đồ đái tháo đường, lần đầu tại viện này nhưng đã làm ở viện khác cách 20 ngày')
        self.assertEqual(r['status'], 'source_condition_not_met')


class Finding3Gene(Base):
    def test_undiagnosed_or_not_excluded_disease_is_asked(self):
        for q in ('Xét nghiệm EGFR cho bệnh nhân chưa có chẩn đoán ung thư phổi không tế bào nhỏ trong điều trị hôm nay',
                  'Xét nghiệm EGFR hôm nay cho bệnh nhân chưa loại trừ ung thư phổi không tế bào nhỏ, đang điều trị',
                  'Xét nghiệm EGFR hôm nay cho bệnh nhân không loại trừ ung thư phổi không tế bào nhỏ, đang điều trị',
                  'Xét nghiệm HER2 hôm nay cho bệnh nhân chưa được chẩn đoán xác định ung thư vú, đang điều trị',
                  'Xét nghiệm BRAF hôm nay cho bệnh nhân td ung thư tuyến giáp đang điều trị'):
            r = self.lab(q)
            self.assertEqual((r['status'], r['pending']), ('needs_info', 'disease'), q)

    def test_ruled_out_disease_is_outside(self):
        self.assertEqual(self.lab('Xét nghiệm EGFR hôm nay cho bệnh nhân đã loại trừ ung thư phổi không tế bào nhỏ')['status'], 'source_condition_not_met')

    def test_negated_purpose(self):
        r = self.lab('Xét nghiệm EGFR hôm nay cho bệnh nhân ung thư phổi không tế bào nhỏ, không nhằm chẩn đoán đột biến trong điều trị')
        self.assertEqual((r['facts']['disease'], r['facts']['purpose'], r['status']), ('nsclc', 'not_mutation', 'source_condition_not_met'))
        for tail in ('chưa điều trị', 'không điều trị', ', không phải trong điều trị', 'đã ngừng điều trị', ', dự kiến điều trị đích'):
            r = self.lab('Xét nghiệm EGFR hôm nay cho bệnh nhân ung thư phổi không tế bào nhỏ ' + tail)
            self.assertEqual((r['facts'].get('disease'), r['pending']), ('nsclc', 'purpose'), tail)

    def test_plain_statements_still_match(self):
        for q in ('Xét nghiệm EGFR hôm nay cho bệnh nhân ung thư phổi không phải tế bào nhỏ đang điều trị',
                  'Xét nghiệm EGFR hôm nay cho bệnh nhân ung thư phổi không tế bào nhỏ không hút thuốc đang điều trị',
                  'Xét nghiệm EGFR hôm nay, bệnh nhân NSCLC giai đoạn IV chưa di căn não, để chọn thuốc điều trị',
                  'Xét nghiệm HER2 hôm nay cho bệnh nhân ung thư vú, chưa hóa trị, chuẩn bị điều trị đích'):
            self.assertEqual(self.lab(q)['status'], 'source_conditions_match', q)
        r = self.lab('Xét nghiệm HER2 hôm nay cho bệnh nhân ung thư vú đã ngừng điều trị')
        self.assertEqual(r['facts']['disease'], 'breast')            # the disease is not "stopped"


class Finding4to8(Base):
    def test_4_kidney_word_does_not_hide_the_mutation_test(self):
        r = self.ask('Xét nghiệm đột biến gen EGFR cho bệnh nhân ung thư phổi không tế bào nhỏ có suy thận, có được BHYT không')
        self.assertEqual(r['lab_results'][0]['id'], 'egfr')
        r = self.ask('Xét nghiệm EGFR hôm nay cho bệnh nhân ung thư phổi không tế bào nhỏ đang điều trị, không có suy thận')
        self.assertEqual(r['lab_results'][0]['status'], 'source_conditions_match')
        self.assertEqual(self.ask('eGFR cho bệnh nhân suy thận có được BHYT không')['status'], 'unknown')
        self.assertEqual(self.ask('eGFR cho bệnh nhân ung thư phổi có suy thận')['status'], 'needs_info')   # really ambiguous: ask

    def test_5_answer_to_the_bots_own_question_keeps_the_test(self):
        a = self.ask('Xét nghiệm EGFR cho bệnh nhân NSCLC hôm nay')
        self.assertEqual(a['lab_results'][0]['pending'], 'purpose')
        b = self.ask('Xét nghiệm để chẩn đoán đột biến trong điều trị', a)
        self.assertEqual((b['lab_results'][0]['id'], b['lab_results'][0]['status']), ('egfr', 'source_conditions_match'))
        a = self.ask('Tôi muốn chỉ định HbA1c hôm nay')
        self.assertEqual(self.lab('Xét nghiệm để theo dõi đái tháo đường', a)['pending'], 'last_date')
        # another test named in the reply is another test
        self.assertEqual(self.ask('Xét nghiệm troponin để chẩn đoán nhồi máu', a)['status'], 'unknown')
        a = self.ask('Xét nghiệm EGFR cho bệnh nhân NSCLC hôm nay')
        self.assertEqual(self.lab('Xét nghiệm HER2 để chẩn đoán đột biến trong điều trị', a)['id'], 'her2')

    def test_6_test_and_drug_joined_by_and(self):
        for q, drug, lab in [('Cả xét nghiệm HER2 và Trastuzumab trong ung thư vú có BHYT không?', 'Trastuzumab', 'her2'),
                             ('Xét nghiệm KRAS và Cetuximab ung thư đại trực tràng đều được BHYT chi trả không?', 'Cetuximab', 'kras'),
                             ('HbA1c và Metformin có được BHYT không', 'Metformin', 'hba1c'),
                             ('Erlotinib cùng xét nghiệm EGFR ung thư phổi không tế bào nhỏ có được BHYT không', 'Erlotinib', 'egfr')]:
            r = self.ask(q)
            self.assertEqual((r.get('domain'), [x['ingredient'] for x in r['results']], [x['id'] for x in r['lab_results']]), ('mixed', [drug], [lab]), q)

    def test_6_and_between_two_drugs_is_not_a_test_request(self):
        for q in ('Trastuzumab và Pertuzumab ung thư vú HER2 dương tính', 'Metformin và Gliclazid đái tháo đường type 2 HbA1c 9%',
                  'Cetuximab và Bevacizumab ung thư đại trực tràng KRAS tự nhiên'):
            self.assertNotIn('lab_results', self.ask(q), q)

    def test_7_general_name_with_another_method(self):
        for q in ('Xét nghiệm HLA bằng kỹ thuật NGS có BHYT không?', 'Xét nghiệm HLA-B27 có được BHYT không'):
            rows = self.ask(q)['lab_results']
            self.assertEqual(sorted(x['id'] for x in rows), ['hla_sso', 'hla_ssp'], q)
            for x in rows:
                self.assertEqual(x['status'], 'needs_review', q)
                self.assertIn('khác với dòng này', x['conclusion'])
                self.assertTrue(any('PCR-SS' in n and 'kỹ thuật khác không thuộc dòng này' in n for n in x['notes']), q)
        self.assertEqual([x['id'] for x in self.ask('Xét nghiệm HLA bằng PCR-SSP')['lab_results']], ['hla_ssp'])
        rows = self.ask('xét nghiệm HLA')['lab_results']                 # no method named: both rows, each with its scope note
        self.assertTrue(all(x['status'] == 'conditions_only' and x['notes'] for x in rows))
        r = self.lab('Xét nghiệm tế bào học cổ tử cung bằng ThinPrep có được BHYT không')
        self.assertEqual((r['id'], r['status']), ('liquiprep', 'needs_review'))

    def test_8_one_damaged_image_stops_only_its_own_rows(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(self.c.data, tmp / 'data', ignore=shutil.ignore_patterns('*.sqlite'))
            (tmp / 'data/sources/labs/vbhn-p50.png').write_bytes(b'damaged')
            other = Corpus(tmp / 'data')
            self.assertEqual(self.ask('HbA1c có điều kiện BHYT gì?', corpus=other)['lab_results'][0]['status'], 'conditions_only')
            self.assertEqual(self.ask('Nhuộm PAS có điều kiện gì', corpus=other)['status'], 'source_unavailable')
            r = self.ask('HbA1c và nhuộm PAS có điều kiện gì', corpus=other)
            self.assertEqual([x['id'] for x in r['lab_results']], ['hba1c'])
            self.assertIn('Nhuộm PAS', r['notice'])
            self.assertFalse(other.labs.file_ok('/sources/labs/vbhn-p50.png'))
            self.assertTrue(other.labs.file_ok('/sources/labs/hba1c-row.png'))
            self.assertFalse(other.labs.integrity_ok())                  # the overall status still reports the damage
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class DiabetesAndPurpose(Base):
    def test_confirmed_or_not(self):
        H = 'HbA1c hôm nay '
        for text, expected in [('theo dõi đái tháo đường type 2 chưa điều trị, lần trước cách 100 ngày', True),
                               ('theo dõi bệnh nhân đái tháo đường không biến chứng, lần trước cách 100 ngày', True),
                               ('theo dõi đái tháo đường type 2, không phải đái tháo đường thai kỳ, lần trước cách 100 ngày', True),
                               ('theo dõi, bệnh nhân không có tiền sử đái tháo đường', False), ('theo dõi bệnh nhân tăng huyết áp không đái tháo đường', False),
                               ('theo dõi, không loại trừ đái tháo đường', None)]:
            self.assertIs(self.lab(H + text)['facts'].get('diabetes'), expected, text)

    def test_purpose(self):
        H = 'HbA1c hôm nay '
        for text, expected in [('không phải để xác định phác đồ mà để theo dõi đái tháo đường, lần trước cách 100 ngày', 'monitoring'),
                               ('để theo dõi chứ không phải sàng lọc, đái tháo đường, lần trước cách 100 ngày', 'monitoring'),
                               ('đái tháo đường, không theo dõi được đường huyết tại nhà, đánh giá kết quả điều trị, lần trước cách 100 ngày', 'monitoring'),
                               ('cho bệnh nhân mới chẩn đoán đái tháo đường để xác định phác đồ, chưa từng làm', 'regimen'),
                               ('chưa rõ mục đích, đái tháo đường', None)]:
            self.assertEqual(self.lab(H + text)['facts'].get('purpose'), expected, text)


if __name__ == '__main__':
    unittest.main()
