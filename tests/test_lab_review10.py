"""Trial run of the sample questions (2026-11-11): four defects.

1. "SCC" typed without "xét nghiệm" was not taken as the test.
2. A short answer to the chatbot's own question was not understood unless it was "có" or
   "không": "Đã xác định" left the laboratory path, "không tế bào nhỏ" was asked again.
3. "Để chọn thuốc điều trị", given as the purpose of a gene test, left the laboratory path
   because of the word "thuốc".
4. Two lines of the reading were wrong although the conclusion was right: "để chẩn đoán đái
   tháo đường" shown as a confirmed diagnosis, and "tầm soát cho bệnh nhân ung thư phổi không
   tế bào nhỏ" shown as an unknown disease.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Corpus
from lab_lookup import short_reply

TODAY = dt.date(2026, 11, 11)
MATCH, NOT_MET = 'source_conditions_match', 'source_condition_not_met'
LUNG = 'Xét nghiệm EGFR cho bệnh nhân ung thư phổi'
BREAST = 'Xét nghiệm HER2 cho bệnh nhân ung thư vú'


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()

    def ask(self, q, prev=None):
        with patch('lab_lookup.local_today', return_value=TODAY):
            return self.c.converse(q, prev['state'] if prev else None)

    def lab(self, q, prev=None):
        r = self.ask(q, prev)
        self.assertEqual(r.get('domain'), 'lab', q)
        self.assertTrue(r['lab_results'], q)
        return r['lab_results'][0]


class BareTestName(Base):
    def test_scc_without_the_word_test(self):
        for q in ('SCC cho ung thư cổ tử cung', 'SCC có điều kiện BHYT gì?', 'scc', 'Bệnh nhân ung thư cổ tử cung làm SCC được không?',
                  'Chỉ định SCC cho bệnh nhân ung thư vú'):
            r = self.lab(q)
            self.assertEqual(r['id'], 'scc', q)
            self.assertTrue(any('Chatbot hiểu câu hỏi là về xét nghiệm' in n for n in r['notes']), q)      # the assumption is stated
        self.assertEqual(self.lab('SCC cho ung thư cổ tử cung')['facts']['disease'], 'cervical')
        self.assertEqual(self.lab('Chỉ định SCC cho bệnh nhân ung thư vú')['status'], NOT_MET)

    def test_no_note_when_the_test_is_named_as_one(self):
        for q in ('Xét nghiệm SCC cho ung thư cổ tử cung', 'Định lượng SCC'):
            self.assertFalse(any('Chatbot hiểu câu hỏi là về xét nghiệm' in n for n in self.lab(q)['notes']), q)

    def test_the_same_letters_as_a_disease_or_beside_a_medicine_are_left_alone(self):
        for q in ('SCC thực quản có được BHYT không?', 'Bệnh nhân SCC phổi dùng thuốc gì', 'Pembrolizumab cho SCC đầu cổ',
                  'Bệnh nhân thalassemia truyền máu', 'Trastuzumab cho bệnh nhân SCC cổ tử cung'):
            self.assertNotEqual(self.ask(q).get('domain'), 'lab', q)

    def test_a_medicine_conversation_is_not_taken_over(self):
        drug = self.ask('Trastuzumab ung thư vú HER2 dương tính')
        self.assertNotEqual(self.ask('SCC cho ung thư cổ tử cung', drug).get('domain'), 'lab')


class ShortAnswers(Base):
    def test_what_counts_as_an_answer(self):
        for q, pending, expected in (('co', 'disease', 'yes'), ('da xac dinh', 'disease', 'yes'), ('da duoc chan doan xac dinh roi', 'diabetes', 'yes'),
                                     ('roi', 'diabetes', 'yes'), ('chua chan doan', 'diabetes', 'no'), ('chua', 'disease', 'no'),
                                     ('dang dung', 'insulin', 'yes'), ('khong dung', 'insulin', 'no'), ('chua ro', 'insulin', 'unknown'),
                                     ('da xac dinh', 'insulin', None), ('dang dung', 'disease', None), ('co', 'confirm', None), ('co', None, None),
                                     ('da xac dinh nhung chua dieu tri', 'disease', None)):
            self.assertEqual(short_reply(q, pending), expected, (q, pending))

    def test_lung_cancer_type_given_on_its_own(self):
        for reply, disease, status in (('không tế bào nhỏ, đang điều trị', 'nsclc', MATCH), ('Đã xác định, đang điều trị', 'nsclc', MATCH),
                                       ('Có, đang điều trị', 'nsclc', MATCH), ('tế bào nhỏ', 'sclc', NOT_MET)):
            first = self.ask(LUNG)
            self.assertEqual(first['lab_results'][0]['pending'], 'disease')
            r = self.lab(reply, first)
            self.assertEqual((r['facts']['disease'], r['status']), (disease, status), reply)

    def test_answer_then_the_next_question(self):
        first = self.ask(LUNG)
        for reply in ('Đã xác định', 'Đã xác định rồi', 'Có', 'không tế bào nhỏ'):
            r = self.lab(reply, first)
            self.assertEqual((r['facts']['disease'], r['pending']), ('nsclc', 'purpose'), reply)

    def test_type_stated_in_another_clause_of_the_same_message(self):
        r = self.lab('Xét nghiệm EGFR cho bệnh nhân ung thư phổi, không tế bào nhỏ, đang điều trị')
        self.assertEqual((r['facts']['disease'], r['status']), ('nsclc', MATCH))

    def test_doubtful_type_is_asked_again(self):
        first = self.ask(LUNG)
        for reply in ('không phải không tế bào nhỏ', 'chưa rõ tế bào nhỏ hay không tế bào nhỏ', 'nghi không tế bào nhỏ', 'có thể là tế bào nhỏ'):
            r = self.lab(reply, first)
            self.assertNotIn(r['status'], (MATCH, NOT_MET), reply)
            self.assertNotIn(r['facts'].get('disease'), ('nsclc', 'sclc'), reply)

    def test_three_diseases_in_the_row(self):
        first = self.ask('Xét nghiệm HER2 cho bệnh nhân ung thư phổi')
        self.assertEqual(self.lab('Có', first)['pending'], 'disease')              # "Có" names none of the three
        self.assertEqual(self.lab('không tế bào nhỏ', first)['facts']['disease'], 'nsclc')

    def test_hba1c_answers(self):
        asked = self.ask('HbA1c hôm nay theo dõi, lần trước cách 100 ngày')
        self.assertEqual(asked['lab_results'][0]['pending'], 'diabetes')
        self.assertEqual(self.lab('Đã chẩn đoán xác định', asked)['status'], MATCH)
        self.assertEqual(self.lab('chưa chẩn đoán', asked)['status'], NOT_MET)
        self.assertEqual(self.lab('chưa xác định', asked)['status'], 'needs_confirmation')      # a word of doubt: shown, not concluded
        asked = self.ask('HbA1c theo dõi đái tháo đường thai kỳ, lần trước cách 35 ngày')
        self.assertEqual(asked['lab_results'][0]['pending'], 'insulin')
        self.assertEqual(self.lab('đang dùng', asked)['status'], MATCH)
        self.assertEqual(self.lab('không dùng', asked)['status'], NOT_MET)

    def test_a_short_answer_does_not_skip_a_pending_confirmation(self):
        a = self.ask('HbA1c hôm nay theo dõi đái tháo đường thai kỳ, từ chối insulin, lần trước cách 35 ngày')
        self.assertEqual(a['lab_results'][0]['status'], 'needs_confirmation')
        for reply in ('Đã xác định', 'đang dùng', 'Có'):
            r = self.ask(reply, a)
            decided = [x for x in r.get('lab_results') or [] if x['status'] in (MATCH, NOT_MET)]
            self.assertFalse(decided, reply)


class PurposeWithTheWordMedicine(Base):
    def test_purpose_given_with_the_word_thuoc(self):
        first = self.ask(BREAST)
        self.assertEqual(first['lab_results'][0]['pending'], 'purpose')
        self.assertEqual(self.lab('để chọn thuốc điều trị', first)['status'], MATCH)
        # Words outside the known list ("quá trình") still wait for the reading to be confirmed.
        r = self.lab('để chọn thuốc trong quá trình điều trị', first)
        self.assertEqual((r['facts']['purpose'], r['status']), ('mutation_in_treatment', 'needs_confirmation'))
        self.assertEqual(self.lab('không để chọn thuốc điều trị', first)['pending'], 'purpose')      # negated: asked again

    def test_a_medicine_question_still_leaves(self):
        first = self.ask(BREAST)
        for reply in ('thuốc nào được BHYT?', 'thuốc điều trị có được BHYT không', 'để chọn thuốc Trastuzumab', 'thuốc này có được không'):
            self.assertNotEqual(self.ask(reply, first).get('domain'), 'lab', reply)

    def test_only_right_after_the_chatbot_asked(self):
        answered = self.ask('Xét nghiệm HER2 cho bệnh nhân ung thư vú đang điều trị')
        self.assertEqual(answered['lab_results'][0]['status'], MATCH)
        self.assertNotEqual(self.ask('thuốc điều trị ung thư vú', answered).get('domain'), 'lab')


class Reading(Base):
    def test_ordered_to_diagnose_is_not_a_confirmed_diagnosis(self):
        for q in ('HbA1c để chẩn đoán đái tháo đường lần đầu', 'HbA1c nhằm chẩn đoán xác định đái tháo đường', 'HbA1c hôm nay để chẩn đoán tiểu đường'):
            r = self.lab(q)
            self.assertIs(r['facts'].get('diabetes'), False, q)
            self.assertIn('Đã chẩn đoán xác định đái tháo đường: chưa', r['reading'], q)
            self.assertEqual(r['status'], NOT_MET, q)

    def test_a_diagnosis_already_made_stays_confirmed(self):
        for q in ('HbA1c cho bệnh nhân đã chẩn đoán đái tháo đường, để theo dõi, lần trước cách 100 ngày',
                  'HbA1c cho bệnh nhân được chẩn đoán đái tháo đường type 2, theo dõi, lần trước cách 100 ngày'):
            r = self.lab(q)
            self.assertIs(r['facts'].get('diabetes'), True, q)
            self.assertEqual(r['status'], MATCH, q)

    def test_screening_ordered_for_a_patient_with_the_disease(self):
        for q in ('Xét nghiệm EGFR để tầm soát cho bệnh nhân ung thư phổi không tế bào nhỏ',
                  'Xét nghiệm EGFR sàng lọc ở người bệnh đã chẩn đoán ung thư phổi không tế bào nhỏ'):
            r = self.lab(q)
            self.assertEqual((r['facts']['disease'], r['facts']['purpose'], r['status']), ('nsclc', 'screening', NOT_MET), q)
            self.assertIn('Bệnh: ung thư phổi không tế bào nhỏ', r['reading'], q)

    def test_screening_for_the_disease_still_doubts_it(self):
        for q in ('Xét nghiệm EGFR để tầm soát ung thư phổi không tế bào nhỏ cho bệnh nhân',
                  'Xét nghiệm EGFR tầm soát cho bệnh nhân nghi ung thư phổi không tế bào nhỏ',
                  'Xét nghiệm EGFR tầm soát cho bệnh nhân chưa loại trừ ung thư phổi không tế bào nhỏ'):
            self.assertEqual(self.lab(q)['facts']['disease'], 'unknown', q)


if __name__ == '__main__':
    unittest.main()
