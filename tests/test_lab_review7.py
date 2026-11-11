"""Second external review of the lab lookup (2026-11-11) and the change of principle it led to.

Reading negation clause by clause fixed the examples of the first review, and other
phrasings still slipped through — in the second review and in my own sweep. So a conclusion
("khớp" / "không khớp") is now given straight from free text only when every word of the
question is accounted for and nothing voices doubt. Otherwise the chatbot shows how it read
the facts and waits for a one-click confirmation; it never guesses.
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
from lab_lookup import unread_words

TODAY = dt.date(2026, 11, 10)
CONFIRM = 'Đúng, đối chiếu theo các dữ kiện này'
G = 'HbA1c hôm nay theo dõi đái tháo đường thai kỳ, {}, lần trước cách 35 ngày'
H = 'HbA1c hôm nay {}'
E = 'Xét nghiệm EGFR hôm nay cho bệnh nhân {}'
DECIDED = ('source_conditions_match', 'source_condition_not_met')


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()

    def ask(self, q, prev=None, corpus=None):
        with patch('lab_lookup.local_today', return_value=TODAY):
            return (corpus or self.c).converse(q, prev['state'] if prev else None)

    def lab(self, q, prev=None):
        return self.ask(q, prev)['lab_results'][0]


class Findings(Base):
    def test_1_uncertain_purpose_is_asked(self):
        r = self.lab('Xét nghiệm EGFR hôm nay cho bệnh nhân NSCLC, có thể nhằm chẩn đoán đột biến')
        self.assertEqual((r['status'], r['pending']), ('needs_info', 'purpose'))
        self.assertNotIn('purpose', r['facts'])

    def test_2_long_negation_and_corrected_diagnosis(self):
        for q in (E.format('chưa có đủ bằng chứng để chẩn đoán xác định ung thư phổi không tế bào nhỏ, đang điều trị'),
                  'Xét nghiệm EGFR hôm nay, trước đây chẩn đoán NSCLC nhưng nay xác định không phải NSCLC, đang điều trị',
                  E.format('ung thư phổi không tế bào nhỏ đã được chẩn đoán loại trừ, đang điều trị'),
                  E.format('ung thư phổi không tế bào nhỏ hay tế bào nhỏ chưa phân biệt được, đang điều trị')):
            r = self.lab(q)
            self.assertEqual((r['facts']['disease'], r['pending']), ('unknown', 'disease'), q)

    def test_3_unconfirmed_gestational_diabetes_is_asked(self):
        r = self.lab('HbA1c hôm nay theo dõi đái tháo đường, chưa xác định có đái tháo đường thai kỳ, đang dùng insulin, lần trước cách 35 ngày')
        self.assertEqual((r['facts']['gestational'], r['status'], r['pending']), ('unknown', 'needs_info', 'gestational'))
        self.assertIs(r['facts']['diabetes'], True)
        a = self.ask('HbA1c hôm nay theo dõi đái tháo đường, chưa xác định có đái tháo đường thai kỳ, đang dùng insulin, lần trước cách 35 ngày')
        self.assertEqual(self.lab('Có', a)['status'], 'source_conditions_match')          # 35 days, 30-day branch
        self.assertEqual(self.lab('Không', a)['status'], 'source_condition_not_met')      # 35 days, ordinary branch
        for text in ('có thể là đái tháo đường thai kỳ', 'nghi đái tháo đường thai kỳ', 'trước đây đái tháo đường thai kỳ'):
            r = self.lab(f'HbA1c hôm nay theo dõi đái tháo đường, {text}, đang dùng insulin, lần trước cách 35 ngày')
            self.assertNotIn(r['status'], DECIDED, text)
        r = self.lab('HbA1c hôm nay theo dõi đái tháo đường, không phải đái tháo đường thai kỳ, đang dùng insulin, lần trước cách 35 ngày')
        self.assertIs(r['facts']['gestational'], False)

    def test_4_first_time_here_is_not_first_time_ever(self):
        for text in ('lần đầu tại bệnh viện này', 'lần đầu khám tại đây', 'bệnh nhân khám lần đầu', 'lần đầu trong năm nay', 'lần đầu sau khi đổi thuốc',
                     'chưa từng làm tại viện này', 'không rõ đã từng làm chưa'):
            r = self.lab(H.format('để xác định phác đồ cho bệnh nhân đái tháo đường, ' + text))
            self.assertNotIn(r['facts'].get('first_test'), (True,), text)
            self.assertNotIn(r['status'], DECIDED, text)
        for text in ('lần đầu làm HbA1c', 'làm lần đầu', 'chưa từng làm'):
            self.assertEqual(self.lab(H.format('để xác định phác đồ cho bệnh nhân đái tháo đường, ' + text))['status'], 'source_conditions_match', text)

    def test_5_screening_negated_or_corrected(self):
        r = self.lab('Xét nghiệm EGFR hôm nay cho bệnh nhân NSCLC, không tầm soát mà chẩn đoán đột biến trong điều trị')
        self.assertEqual((r['facts']['purpose'], r['status']), ('mutation_in_treatment', 'source_conditions_match'))
        a = self.ask('Xét nghiệm EGFR hôm nay cho bệnh nhân NSCLC để tầm soát')
        self.assertEqual(a['lab_results'][0]['facts']['purpose'], 'screening')
        b = self.lab('Không, để chẩn đoán đột biến trong điều trị', a)
        self.assertEqual(b['facts']['purpose'], 'mutation_in_treatment')
        r = self.lab(E.format('ung thư phổi không tế bào nhỏ, vừa tầm soát vừa chẩn đoán đột biến trong điều trị'))
        self.assertNotIn(r['status'], DECIDED)

    def test_6_both_asked_even_with_a_marker_phrase(self):
        r = self.ask('Cả xét nghiệm HER2 và Trastuzumab cho bệnh nhân ung thư vú chưa có kết quả xét nghiệm có BHYT không?')
        self.assertEqual((r['domain'], [x['ingredient'] for x in r['results']], [x['id'] for x in r['lab_results']]), ('mixed', ['Trastuzumab'], ['her2']))

    def test_7_hla_locus_named_in_the_row_is_the_row(self):
        r = self.lab('Định type HLA-B bằng PCR-SSP có điều kiện BHYT gì?')
        self.assertEqual((r['id'], r['status']), ('hla_ssp', 'conditions_only'))
        self.assertEqual(self.lab('Xét nghiệm HLA-B27 có được BHYT không')['status'], 'needs_review')

    def test_8_damaged_lab_source_is_said_in_a_mixed_answer(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(self.c.data, tmp / 'data', ignore=shutil.ignore_patterns('*.sqlite'))
            (tmp / 'data/sources/labs/her2-row.png').write_bytes(b'damaged')
            other = Corpus(tmp / 'data')
            r = self.ask('Cả xét nghiệm HER2 và Trastuzumab trong ung thư vú có BHYT không?', corpus=other)
            self.assertEqual([x['ingredient'] for x in r['results']], ['Trastuzumab'])
            self.assertEqual(r['lab_results'], [])
            self.assertIn('Xét nghiệm đột biến gen Her 2', r['notice'])
            self.assertIn('tệp nguồn', r['notice'])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Confirmation(Base):
    def test_unread_words(self):
        self.assertEqual(unread_words('HbA1c hôm nay để đánh giá kết quả điều trị đái tháo đường, lần trước làm ngày 01/08/2026, BHYT có thanh toán không?', ['hba1c']), [])
        self.assertEqual(unread_words('theo dõi đái tháo đường thai kỳ, từ chối insulin'), ['từ', 'chối'])
        self.assertEqual(unread_words('ung thư phổi (chẩn đoán tuyến trước, chưa hội chẩn lại)'), ['hội'])     # "hội" is not "hỏi"
        self.assertEqual(unread_words('me benh nhan bi dai thao duong'), ['me'])                                # typed without diacritics
        self.assertEqual(unread_words('NSCLC giai đoạn IV'), [])

    def test_conclusion_waits_for_confirmation_when_words_are_unread(self):
        a = self.ask(G.format('từ chối insulin'))
        r = a['lab_results'][0]
        self.assertEqual((r['status'], r['pending']), ('needs_confirmation', 'confirm'))
        self.assertEqual(a['status'], 'needs_info')
        self.assertEqual(r['unread'], ['từ', 'chối'])
        self.assertIn('“từ”, “chối”', r['conclusion'])
        self.assertIn('Insulin: đang dùng', r['reading'])            # the misreading is in plain sight
        self.assertEqual(r['highlight'], [])
        b = self.lab('Không, bệnh nhân không dùng insulin', a)       # corrected instead of confirmed
        self.assertIs(b['facts']['insulin'], False)
        self.assertEqual(b['status'], 'source_condition_not_met')

    def test_confirming_gives_the_conclusion_without_reading_again(self):
        a = self.ask(E.format('ung thư phổi không tế bào nhỏ tái phát đang điều trị bước 2'))
        self.assertEqual(a['lab_results'][0]['status'], 'needs_confirmation')
        self.assertEqual(a['lab_results'][0]['reading'], ['Bệnh: ung thư phổi không tế bào nhỏ', 'Mục đích: chẩn đoán đột biến gen trong điều trị'])
        b = self.ask(CONFIRM, a)
        r = b['lab_results'][0]
        self.assertEqual(r['status'], 'source_conditions_match')
        self.assertTrue(r['conclusion'].startswith('Theo các dữ kiện bạn vừa xác nhận:'))
        self.assertEqual(r['facts'], a['lab_results'][0]['facts'])
        self.assertIsNone(b['state']['lab']['pending'])

    def test_confirmation_words_mean_nothing_without_a_pending_reading(self):
        r = self.ask(CONFIRM)
        self.assertNotIn('lab_results', r)
        a = self.ask('HbA1c có điều kiện BHYT gì?')
        self.assertNotIn('lab_results', self.ask(CONFIRM, a))
        a = self.ask(G.format('từ chối insulin'))
        a['state']['lab']['facts']['insulin'] = False                # tampered state is dropped by the signature check
        self.assertNotIn('lab_results', self.ask(CONFIRM, a))

    def test_doubt_anywhere_forbids_a_direct_conclusion(self):
        for q in (H.format('theo dõi đái tháo đường, lần trước hình như cách 100 ngày'), H.format('cho bệnh nhân đái tháo đường, có lẽ để theo dõi, lần trước cách 100 ngày'),
                  E.format('ung thư phổi không tế bào nhỏ, chưa chắc sẽ điều trị')):
            self.assertNotIn(self.lab(q)['status'], DECIDED, q)

    def test_plain_questions_are_still_answered_directly(self):
        for q, status in [('HbA1c hôm nay để đánh giá kết quả điều trị đái tháo đường, lần trước làm ngày 01/08/2026, BHYT có thanh toán không?', 'source_conditions_match'),
                          ('HbA1c hôm nay theo dõi đái tháo đường, lần trước cách 60 ngày', 'source_condition_not_met'),
                          (G.format('đang dùng insulin'), 'source_conditions_match'), (G.format('không còn dùng insulin'), 'source_condition_not_met'),
                          (E.format('ung thư phổi không tế bào nhỏ đang điều trị'), 'source_conditions_match'),
                          ('Xét nghiệm HER2 cho bệnh nhân ung thư đại trực tràng đang điều trị hôm nay có được BHYT không?', 'source_condition_not_met'),
                          ('Xét nghiệm KRAS hôm nay cho bệnh nhân ung thư đại trực tràng giai đoạn IV đang điều trị', 'source_conditions_match')]:
            r = self.lab(q)
            self.assertEqual(r['status'], status, q)
            self.assertTrue(r['reading'], q)


class NeverDecidedFromUnclearText(Base):
    """My own sweep after the review: none of these may be answered "khớp" or "không khớp"
    without a confirmation or a question back."""
    CASES = [
        G.format('từ chối insulin'), G.format('gia đình không đồng ý dùng insulin'), G.format('bác sĩ khác nói có dùng insulin nhưng hồ sơ chưa ghi'),
        G.format('từng dùng insulin'), G.format('trước đây dùng insulin'), G.format('hình như có dùng insulin'), G.format('chắc là dùng insulin'),
        G.format('không thấy ghi nhận dùng insulin'), G.format('dùng insulin hay không chưa rõ'), G.format('thuốc viên, insulin thì chưa'),
        H.format('theo dõi đái tháo đường (chẩn đoán ở tuyến trước, chưa xác nhận lại), lần trước cách 100 ngày'),
        H.format('theo dõi, mẹ bệnh nhân bị đái tháo đường, lần trước cách 100 ngày'), H.format('theo dõi, tiền sử gia đình đái tháo đường, lần trước cách 100 ngày'),
        H.format('theo dõi đái tháo đường, lần trước cách 100 ngày nhưng kết quả bị hủy'), H.format('theo dõi đái tháo đường, lần trước cách gần 100 ngày'),
        H.format('theo dõi đái tháo đường, lần trước chưa đến 100 ngày'), H.format('theo dõi đái tháo đường, lần trước không quá 100 ngày'),
        H.format('theo dõi đái tháo đường, lần trước khoảng hơn 3 tháng'), H.format('cho bệnh nhân đái tháo đường theo yêu cầu của người bệnh, lần trước cách 100 ngày'),
        H.format('kiểm tra sức khỏe định kỳ cho bệnh nhân đái tháo đường, lần trước cách 100 ngày'),
        E.format('ung thư phổi không tế bào nhỏ (chẩn đoán tuyến trước, chưa hội chẩn lại) đang điều trị'), E.format('có người nhà bị ung thư phổi không tế bào nhỏ, đang điều trị'),
        E.format('ung thư phổi không tế bào nhỏ, người bệnh từ chối điều trị'), E.format('ung thư phổi không tế bào nhỏ đã điều trị xong, kiểm tra lại'),
        E.format('ung thư phổi biểu mô tuyến đang điều trị'), E.format('ung thư phổi, sinh thiết chưa có kết quả, đang điều trị'),
        E.format('nghi ung thư phổi không tế bào nhỏ đang điều trị lao'), E.format('di căn phổi từ ung thư vú, đang điều trị'),
        E.format('ung thư phổi không tế bào nhỏ, để nghiên cứu'), E.format('ung thư phổi không tế bào nhỏ, theo yêu cầu người bệnh'),
        'Xét nghiệm HER2 hôm nay cho bệnh nhân ung thư vú hoặc ung thư buồng trứng chưa rõ nguyên phát, đang điều trị',
        'Xét nghiệm KRAS hôm nay cho bệnh nhân polyp đại tràng chưa ung thư hóa, đang điều trị', 'Xét nghiệm BRAF hôm nay cho bệnh nhân u tuyến giáp lành tính, đang điều trị',
    ]

    def test_sweep(self):
        for q in self.CASES:
            r = self.lab(q)
            self.assertNotIn(r['status'], DECIDED, q)
            self.assertTrue(r['pending'] or r['status'] == 'needs_review', q)


if __name__ == '__main__':
    unittest.main()
