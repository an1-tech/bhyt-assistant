import unittest
from unittest.mock import Mock, patch

from chat_assist import ChatAssistant
from engine import Corpus


class CA125ChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = Corpus()

    def ask(self, question, previous=None):
        return self.corpus.converse(question, previous['state'] if previous else None)

    def test_named_assay_and_source_branches(self):
        for question, status, highlight in (
            ('CA-125 để chẩn đoán ung thư buồng trứng', 'source_conditions_match', [1, 2]),
            ('CA125 theo dõi điều trị ung thư buồng trứng', 'source_conditions_match', [1, 2]),
            ('CA 125 để chẩn đoán ung thư di căn không rõ u nguyên phát', 'source_conditions_match', [0]),
            ('CA 125 để tầm soát ung thư buồng trứng', 'source_condition_not_met', [0, 1, 2]),
            ('CA 125 theo dõi điều trị ung thư vú', 'source_condition_not_met', [0, 1, 2]),
        ):
            with self.subTest(question=question):
                row = self.ask(question)['lab_results'][0]
                self.assertEqual((row['status'], row['highlight']), (status, highlight))
                self.assertTrue(row['automatic'])
                self.assertEqual(row['review']['kind'], 'unreviewed')
                self.assertIn('tumor_markers.html#source-row', row['citation']['viewer_url'])
                self.assertIn('Buồng trứng', row['conditions'][2])

    def test_followup_and_interval(self):
        start = self.ask('CA 125 có được BHYT chi trả không?')
        self.assertEqual(start['lab_results'][0]['status'], 'needs_info')
        case = self.ask('Để theo dõi điều trị ung thư buồng trứng', start)
        self.assertEqual(case['lab_results'][0]['status'], 'source_conditions_match')
        for question, phrase in [('Lần trước cách 30 ngày thì sao?', 'khoảng cách tối thiểu'),
                                 ('Giá bao nhiêu?', 'giá dịch vụ')]:
            row = self.ask(question, case)['lab_results'][0]
            self.assertEqual(row['status'], 'needs_review')
            self.assertIn(phrase, row['conclusion'])

    def test_source_bound_answer_with_ai_enabled(self):
        provider = Mock(side_effect=AssertionError('Unexpected external call'))
        with patch('chat_assist.enabled', return_value=True):
            reply = ChatAssistant(self.corpus, provider).respond('CA125 để chẩn đoán ung thư buồng trứng')
        provider.assert_not_called()
        self.assertEqual(reply['lab_results'][0]['status'], 'source_conditions_match')

    def test_surveillance_and_uncertain_cases(self):
        row = self.ask('CA 125 theo dõi sau điều trị ung thư buồng trứng, lần trước cách 30 ngày')['lab_results'][0]
        self.assertEqual(row['status'], 'needs_review')
        self.assertIn('khoảng cách tối thiểu', row['conclusion'])
        self.assertIn('sau điều trị', row['conclusion'])
        self.assertFalse(self.ask('Chụp PET/CT khi CA125 tăng để chẩn đoán ung thư buồng trứng có BHYT không?')['lab_results'])
        for question in ('CA 125 cho bệnh nhân đã được chẩn đoán ung thư buồng trứng',
                         'Không làm CA125, theo dõi điều trị ung thư buồng trứng',
                         'CA125 để theo dõi điều trị ung thư buồng trứng đã kết thúc điều trị',
                         'CA125 theo dõi điều trị, chưa rõ có ung thư buồng trứng',
                         'CA125 cho người nhà bị ung thư buồng trứng, để theo dõi điều trị',
                         'CA125 không nhằm chẩn đoán ung thư buồng trứng',
                         'CA125 để tầm soát hoặc chẩn đoán ung thư buồng trứng'):
            with self.subTest(question=question):
                self.assertNotIn(self.ask(question)['lab_results'][0]['status'],
                                 ('source_conditions_match', 'source_condition_not_met'))

    def test_shared_row_does_not_transfer_case(self):
        first = self.ask('CA 125 theo dõi điều trị ung thư buồng trứng')
        for question in ('Còn CA 19-9?', 'CA125 và CEA cho ung thư buồng trứng',
                         'Các xét nghiệm chỉ điểm khối u'):
            with self.subTest(question=question):
                row = self.ask(question, first)['lab_results'][0]
                self.assertEqual(row['status'], 'conditions_only')
                self.assertFalse(row['automatic'])
        for question in ('Ca mới, CA125 để chẩn đoán', 'Ca mới, để chẩn đoán'):
            new = self.ask(question, first)['lab_results'][0]
            self.assertEqual(new['status'], 'needs_info')
            self.assertEqual(new['name'], 'Định lượng CA 125')
            self.assertNotIn('marker_site', new['facts'])
