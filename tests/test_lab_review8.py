"""Third external review (2026-11-11): four confirmed defects.

1. Facts confirmed for one patient were kept for "bệnh nhân khác".
2. An unconfirmed reading could be skipped by answering the next question.
3. Known words do not make a sentence understood ("dùng insulin trong năm trước").
4. Reasons such as "Áp dụng nhánh …" were shown while the reading was still unconfirmed.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Corpus
from lab_lookup import unread_words

TODAY = dt.date(2026, 11, 10)
CONFIRM = 'Đúng, đối chiếu theo các dữ kiện này'
DECIDED = ('source_conditions_match', 'source_condition_not_met')
REFUSED = 'HbA1c hôm nay theo dõi đái tháo đường thai kỳ, từ chối insulin'


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()

    def ask(self, q, prev=None, confirm=None):
        with patch('lab_lookup.local_today', return_value=TODAY):
            return self.c.converse(q, prev['state'] if prev else None, None, confirm)

    def lab(self, q, prev=None):
        return self.ask(q, prev)['lab_results'][0]

    def her2(self, r):
        return r['results'][0]['question_answer']['requirements'][0]


class AnotherPatient(Base):
    def confirmed_her2(self):
        a = self.ask('Trastuzumab ung thư vú')
        item = a['results'][0]['question_answer']['confirm'][0]
        b = self.ask(item['label'], a, {'key': item['key'], 'value': 'met'})
        self.assertEqual((self.her2(b)['status'], self.her2(b)['source']), ('met', 'confirmed'))
        return b

    def test_confirmed_fact_is_not_carried_to_another_patient(self):
        b = self.confirmed_her2()
        for q in ('Trastuzumab cho bệnh nhân khác ung thư vú có BHYT không?', 'Ca mới: Trastuzumab ung thư vú', 'Một bệnh nhân khác, Trastuzumab ung thư vú',
                  'Trường hợp khác: Trastuzumab ung thư vú', 'Bệnh nhân thứ hai dùng Trastuzumab ung thư vú'):
            r = self.ask(q, b)
            self.assertEqual(self.her2(r)['status'], 'not_stated', q)
            self.assertNotIn('all_requirements_met', r['results'][0]['question_answer'], q)
            self.assertEqual(r['state'].get('facts'), {}, q)

    def test_same_patient_keeps_the_fact(self):
        b = self.confirmed_her2()
        self.assertEqual(self.her2(self.ask('Trastuzumab ung thư vú thì tỷ lệ bao nhiêu?', b))['status'], 'met')

    def test_text_of_the_previous_patient_is_dropped_too(self):
        a = self.ask('Trastuzumab ung thư vú HER2 dương tính')
        self.assertEqual(self.her2(a)['status'], 'met')
        r = self.ask('Còn bệnh nhân khác thì sao?', a)
        self.assertEqual([x['ingredient'] for x in r['results']], ['Trastuzumab'])
        self.assertNotIn('all_requirements_met', r['results'][0]['question_answer'])

    def test_lab_facts_of_the_previous_patient_are_dropped(self):
        a = self.ask('HbA1c hôm nay theo dõi đái tháo đường, lần trước cách 120 ngày')
        self.assertEqual(a['lab_results'][0]['status'], 'source_conditions_match')
        r = self.lab('Bệnh nhân khác, HbA1c hôm nay theo dõi đái tháo đường', a)
        self.assertEqual(r['pending'], 'last_date')
        self.assertNotIn('last_date', r['facts'])


class UnconfirmedReadingStays(Base):
    def test_follow_up_cannot_skip_the_confirmation(self):
        a = self.ask(REFUSED)
        first = a['lab_results'][0]
        self.assertEqual((first['status'], first['pending']), ('needs_info', 'last_date'))
        self.assertEqual(a['state']['lab']['unread'], ['từ', 'chối'])
        self.assertTrue(any('chưa hiểu chắc' in n for n in first['notes']))
        b = self.ask('Lần trước cách 35 ngày', a)
        r = b['lab_results'][0]
        self.assertEqual((r['status'], r['pending']), ('needs_confirmation', 'confirm'))
        self.assertIn('“từ”, “chối”', r['conclusion'])
        self.assertEqual(self.lab(CONFIRM, b)['status'], 'source_conditions_match')

    def test_button_shown_then_ignored(self):
        a = self.ask(REFUSED + ', lần trước cách 35 ngày')
        self.assertEqual(a['lab_results'][0]['status'], 'needs_confirmation')
        b = self.ask('Lần trước cách 36 ngày', a)
        self.assertEqual(b['lab_results'][0]['status'], 'needs_confirmation')
        c = self.ask('Lần trước cách 40 ngày', b)
        self.assertEqual(c['lab_results'][0]['status'], 'needs_confirmation')

    def test_confirmation_clears_it_and_a_new_case_starts_clean(self):
        a = self.ask(REFUSED + ', lần trước cách 35 ngày')
        b = self.ask(CONFIRM, a)
        self.assertEqual((b['state']['lab']['unread'], b['state']['lab']['doubt']), ([], None))
        self.assertIn(self.lab('Lần trước cách 20 ngày', b)['status'], DECIDED)
        r = self.lab('HbA1c hôm nay theo dõi đái tháo đường, lần trước cách 120 ngày', a)      # named again: a new case
        self.assertEqual(r['status'], 'source_conditions_match')

    def test_doubt_voiced_earlier_stays_too(self):
        a = self.ask('HbA1c hôm nay theo dõi đái tháo đường, hình như đã làm rồi')
        b = self.lab('Lần trước cách 120 ngày', a)
        self.assertEqual(b['status'], 'needs_confirmation')


class NothingReadsLikeAConclusionWhileWaiting(Base):
    def test_reasons_and_marks_are_held_back(self):
        for q, prev in ((REFUSED + ', lần trước cách 35 ngày', None), (REFUSED, None)):
            r = self.lab(q, prev)
            self.assertEqual(r['reasons'], [], q)
            self.assertEqual(r['highlight'], [], q)
            self.assertNotIn('Áp dụng nhánh', r['conclusion'] + ' '.join(r['notes']), q)
        a = self.ask(REFUSED + ', lần trước cách 35 ngày')
        r = self.lab(CONFIRM, a)
        self.assertTrue(any('Áp dụng nhánh' in x for x in r['reasons']))        # shown once confirmed
        self.assertEqual(r['highlight'], [2])


class KnownWordsWrongReading(Base):
    def test_time_words_count_only_inside_a_date_expression(self):
        self.assertEqual(unread_words('lần trước cách 35 ngày'), [])
        self.assertEqual(unread_words('lần trước làm ngày 01/08/2026, hôm nay'), [])
        self.assertEqual(unread_words('dùng insulin trong năm trước'), ['năm', 'trước'])
        self.assertEqual(unread_words('để sàng lọc hoặc theo dõi'), ['hoặc'])
        self.assertEqual(unread_words('nếu dùng insulin sau sinh'), ['nếu', 'sau', 'sinh'])
        self.assertEqual(unread_words('chưa từng làm'), [])

    def test_past_use_is_not_present_use(self):
        base = 'HbA1c hôm nay theo dõi đái tháo đường thai kỳ, {}, lần trước cách 35 ngày'
        for text in ('dùng insulin trong năm trước', 'dùng insulin năm ngoái', 'insulin tháng trước', 'dùng insulin trước khi mang thai', 'dùng insulin ở thai kỳ trước'):
            r = self.lab(base.format(text))
            self.assertNotIn(r['status'], DECIDED, text)
            self.assertNotIn('Insulin: đang dùng', r.get('reading', []), text)

    def test_two_purposes_are_asked(self):
        for text in ('để sàng lọc hoặc theo dõi đái tháo đường', 'để theo dõi hay xác định phác đồ cho bệnh nhân đái tháo đường',
                     'vừa đánh giá kết quả điều trị vừa điều chỉnh phác đồ đái tháo đường'):
            r = self.lab(f'HbA1c hôm nay {text}, lần trước cách 100 ngày')
            self.assertEqual((r['facts']['purpose'], r['status'], r['pending']), ('ambiguous', 'needs_info', 'purpose'), text)
        a = self.ask('HbA1c hôm nay để theo dõi hay xác định phác đồ cho bệnh nhân đái tháo đường, lần trước cách 100 ngày')
        b = self.ask('Để đánh giá kết quả điều trị', a)
        self.assertEqual(b['lab_results'][0]['facts']['purpose'], 'monitoring')
        self.assertEqual(b['lab_results'][0]['status'], 'needs_confirmation')      # "hay" from the first turn is still unconfirmed
        self.assertEqual(self.lab(CONFIRM, b)['status'], 'source_conditions_match')


if __name__ == '__main__':
    unittest.main()
