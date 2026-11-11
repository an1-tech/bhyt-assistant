"""Fourth external review (2026-11-11): two confirmed defects.

1. A message that only began with "Đúng" / "Ok" was taken as the confirmation and the rest of
   it (a correction, or another question) was ignored.
2. Per-request state was kept on objects shared by all requests, so a second request running
   in between could make the first one skip the pending confirmation.
"""
import datetime as dt
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Corpus
from lab_lookup import LabLookup

TODAY = dt.date(2026, 11, 10)
CONFIRM = 'Đúng, đối chiếu theo các dữ kiện này'
REFUSED = 'HbA1c hôm nay theo dõi đái tháo đường thai kỳ, từ chối insulin'
DECIDED = ('source_conditions_match', 'source_condition_not_met')


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()

    def ask(self, q, prev=None, confirm=None):
        with patch('lab_lookup.local_today', return_value=TODAY):
            return self.c.converse(q, prev['state'] if prev else None, None, confirm)

    def pending(self):
        a = self.ask(REFUSED + ', lần trước cách 35 ngày')
        self.assertEqual(a['lab_results'][0]['status'], 'needs_confirmation')
        return a


class ConfirmationIsTheWholeMessage(Base):
    def test_plain_confirmations(self):
        for text in (CONFIRM, 'Đúng', 'đúng rồi', 'Chính xác', 'Xác nhận', 'OK', 'Đồng ý', 'Đúng, đối chiếu'):
            r = self.ask(text, self.pending())['lab_results'][0]
            self.assertEqual(r['status'], 'source_conditions_match', text)
            self.assertTrue(r['conclusion'].startswith('Theo các dữ kiện bạn vừa xác nhận'), text)

    def test_correction_that_starts_with_a_confirmation_word_is_read(self):
        for text in ('Đúng nhưng bệnh nhân không dùng insulin', 'Ok, nhưng không dùng insulin', 'Đúng rồi, trừ việc bệnh nhân không còn dùng insulin',
                     'Chính xác, chỉ sửa: không dùng insulin'):
            b = self.ask(text, self.pending())
            r = b['lab_results'][0]
            self.assertIs(r['facts']['insulin'], False, text)
            self.assertEqual(r['status'], 'needs_confirmation', text)       # the corrected reading is shown again
            self.assertIn('Insulin: không dùng', r['reading'], text)
            self.assertEqual(self.ask(CONFIRM, b)['lab_results'][0]['status'], 'source_condition_not_met', text)

    def test_change_of_subject_that_starts_with_ok_is_not_a_confirmation(self):
        r = self.ask('Ok, hỏi Trastuzumab trong ung thư vú', self.pending())
        self.assertNotIn('lab_results', r)
        self.assertEqual([x['ingredient'] for x in r['results']], ['Trastuzumab'])
        r = self.ask('Đúng, còn xét nghiệm EGFR cho ung thư phổi không tế bào nhỏ thì sao', self.pending())
        self.assertEqual([x['id'] for x in r['lab_results']], ['egfr'])

    def test_confirmation_with_extra_content_never_concludes_from_the_old_reading(self):
        for text in ('Đúng nhưng lần trước cách 20 ngày', 'Ok lần trước cách 20 ngày', 'Đúng, bệnh nhân khác'):
            r = self.ask(text, self.pending())
            status = (r.get('lab_results') or [{}])[0].get('status')
            self.assertNotEqual(status, 'source_conditions_match', text)


class NoRequestStateOnSharedObjects(Base):
    def test_second_request_in_between_cannot_clear_the_pending_confirmation(self):
        """Request B runs entirely between the moment A read its facts and the moment A decides."""
        a = self.ask(REFUSED)
        self.assertEqual(a['state']['lab']['unread'], ['từ', 'chối'])
        original = LabLookup.evaluate
        fired = []

        def evaluate(labs, sid, facts, case, errors, today):
            if not fired:
                fired.append(True)
                other = self.c.converse('HbA1c hôm nay theo dõi đái tháo đường, lần trước cách 120 ngày')     # conversation B
                self.assertEqual(other['lab_results'][0]['status'], 'source_conditions_match')
            return original(labs, sid, facts, case, errors, today)

        with patch.object(LabLookup, 'evaluate', evaluate), patch('lab_lookup.local_today', return_value=TODAY):
            b = self.c.converse('Lần trước cách 35 ngày', a['state'])
        self.assertTrue(fired)
        self.assertEqual(b['lab_results'][0]['status'], 'needs_confirmation')
        self.assertEqual(b['state']['lab']['unread'], ['từ', 'chối'])

    def test_nothing_about_a_request_is_left_on_the_shared_objects(self):
        a = self.ask(REFUSED)
        self.ask('Lần trước cách 35 ngày', a)
        d = self.ask('Trastuzumab ung thư vú')
        item = d['results'][0]['question_answer']['confirm'][0]
        self.ask(item['label'], d, {'key': item['key'], 'value': 'met'})
        self.assertFalse(hasattr(self.c.labs, '_same_case'))
        self.assertFalse(hasattr(self.c._indication_chat, '_new_turn'))

    def test_many_conversations_at_once(self):
        results, errors = {}, []

        def worker(n):
            try:
                with patch('lab_lookup.local_today', return_value=TODAY):
                    if n % 2:
                        a = self.c.converse(REFUSED)
                        results[n] = self.c.converse('Lần trước cách 35 ngày', a['state'])['lab_results'][0]['status']
                    else:
                        results[n] = self.c.converse('HbA1c hôm nay theo dõi đái tháo đường, lần trước cách 120 ngày')['lab_results'][0]['status']
            except Exception as error:          # pragma: no cover
                errors.append(error)
        threads = [threading.Thread(target=worker, args=(n,)) for n in range(24)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        for n, status in results.items():
            self.assertEqual(status, 'needs_confirmation' if n % 2 else 'source_conditions_match', n)

    def test_drug_fact_replaced_by_this_requests_own_text(self):
        d = self.ask('Trastuzumab ung thư vú')
        item = d['results'][0]['question_answer']['confirm'][0]
        e = self.ask(item['label'], d, {'key': item['key'], 'value': 'met'})
        r = self.ask('Nếu HER2 âm tính thì sao?', e)
        self.assertEqual(r['results'][0]['question_answer']['status'], 'source_condition_not_met')


if __name__ == '__main__':
    unittest.main()
