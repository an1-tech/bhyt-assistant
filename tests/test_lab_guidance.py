"""Test source-backed laboratory navigation through the public chat entry point."""
import unittest
from unittest.mock import Mock, patch

from chat_assist import ChatAssistant
from engine import Corpus


class LabGuidanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = Corpus()

    def ask(self, question, previous=None):
        return self.corpus.converse(question, previous['state'] if previous else None)

    def test_named_aliases_and_sources(self):
        for names in ('AST, ALT', 'GOT, GPT', 'SGOT/SGPT'):
            with self.subTest(names=names):
                result = self.ask(names + ' được chi trả bảo hiểm y tế trong những trường hợp nào?')
                self.assertEqual(result['state']['lab_guide']['tests'], ['ast', 'alt'])
                self.assertIn('23.0020.1493', str(result['lab_guidance']))
                self.assertIn('23.0019.1493', str(result['lab_guidance']))
                for source in ('kcb.vn', 'chinhphu.vn', 'vinmec.com', 'thainguyen.gov.vn'):
                    self.assertIn(source, str(result['lab_guidance']))
                self.assertIn('Chưa đủ căn cứ', result['answer'])
        self.assertEqual(self.ask('Mã 23.0020.1493 có BHYT?')['state']['lab_guide']['tests'], ['ast'])

    def test_doctors_general_question_and_followups(self):
        question = 'Điều kiện thanh toán bảo hiểm y tế cho xét nghiệm'
        for suffix in ('', ' : câu trả lời yes or no, và trong những trường hợp nào'):
            self.assertEqual(self.ask(question + suffix)['state']['lab_guide']['topic'], 'general')
        result = self.ask(question, self.ask('HbA1c có điều kiện BHYT gì?'))
        self.assertEqual(result['lab_results'][0]['id'], 'hba1c')
        result = self.ask('để theo dõi viêm gan B cấp', self.ask('GOT GPT'))
        self.assertIn('Bước tiếp theo', str(result['lab_guidance']))

    def test_exclusion_limited_to_named_technique(self):
        specific = self.ask('Xét nghiệm ANA 17 profile test có được BHYT không?')
        self.assertIn('tạm thời chưa thanh toán', specific['answer'])
        self.assertIn('#page=52', str(specific['lab_guidance']))
        self.assertNotIn('tạm thời chưa thanh toán', self.ask('Xét nghiệm ANA có BHYT?')['answer'])
        denial = self.ask('Không phải ANA 17 profile mà là ANA đơn lẻ')
        self.assertEqual(denial['state']['lab_guide']['topic'], 'clarify_test')

    def test_specimen_and_screening_survive_general_followup(self):
        for question in ('Creatinin niệu', 'Xét nghiệm glucose mao mạch', 'AST khám sức khỏe'):
            with self.subTest(question=question):
                result = self.ask(question)
                for reply in (result, self.ask('tại Vinmec', result)):
                    self.assertIn('Chưa đủ căn cứ', reply['answer'])
                    if 'khám' not in question:
                        self.assertNotIn('.1494', str(reply['lab_guidance']))

    def test_discovery_by_indication(self):
        for indication, source in [('viêm gan B cấp','kcb.vn'), ('bệnh thận mạn','kdigo.org'),
                                   ('đái tháo đường','nih.gov')]:
            result = self.ask('Các xét nghiệm trong ' + indication)
            self.assertIn(source, str(result['lab_guidance']))
            self.assertTrue(result['suggested_followups'])
        panel = self.ask('BHYT cho xét nghiệm men gan')
        ggt = self.ask('GGT máu', panel)
        self.assertIn('23.0077.1518', str(ggt['lab_guidance']))
        toxicity = self.ask('để theo dõi độc tính thuốc', self.ask('GOT GPT'))
        self.assertIn('Tổn thương gan do thuốc', str(toxicity['lab_guidance']))

    def test_site_purpose_and_exact_source(self):
        start = self.ask('các xét nghiệm chỉ định trong dịch vụ ung thư')
        self.assertNotIn('site', start['state']['lab_guide'])
        breast = self.ask('Ung thư vú', start)
        therapeutic = self.ask('để chọn thuốc', breast)
        self.assertIn('/her2.html', str(therapeutic['lab_guidance']))
        self.assertNotIn('/egfr.html', str(therapeutic['lab_guidance']))
        monitoring = self.ask('Để theo dõi', therapeutic)
        row = next(s for s in monitoring['lab_guidance'] if 'tumor_markers.html' in str(s))
        self.assertIn('CA 15-3: Vú', row['text'])
        self.assertNotIn('Buồng trứng', row['text'])
        screening = self.ask('Để sàng lọc', breast)
        self.assertNotIn('/her2.html', str(screening['lab_guidance']))
        self.assertNotIn('site', self.ask('Ung thư tủy xương', breast)['state']['lab_guide'])
        self.assertNotIn('purpose', self.ask('Ung thư gan', therapeutic)['state']['lab_guide'])
        self.assertIn('/pivka.html', str(self.ask('Ung thư gan', start)['lab_guidance']))

    def test_payment_topics_show_conditions_rates_and_original_sources(self):
        for question, expected in [('Xét nghiệm nào cho suy tim?', ['bnp', 'probnp']),
                                   ('Xét nghiệm nào trong nhiễm khuẩn huyết?', ['crp', 'procalcitonin']),
                                   ('Những xét nghiệm trước ghép tạng?', ['hla_sso', 'hla_ssp']),
                                   ('Xét nghiệm nào khi tiêu chảy sau kháng sinh?', ['cdiff']),
                                   ('Xét nghiệm nào cho bệnh lý globulin miễn dịch đơn dòng?', ['serum_ife'])]:
            with self.subTest(question=question):
                result = self.ask(question)
                self.assertEqual([r['id'] for r in result['lab_results']], expected)
                for row in result['lab_results']:
                    self.assertEqual(row['conditions'], self.corpus.labs.services[row['id']]['conditions'])
                    self.assertEqual(row['rate'], self.corpus.labs.services[row['id']]['rate'])
                    self.assertIn('viewer_url', row['citation'])

    def test_specific_and_mixed_requests(self):
        for question in ('Truyền glucose 5%', 'đau gót chân', 'Mô hình GPT',
                         'xét nghiệm XYZZY trong ung thư', 'Trastuzumab ung thư vú có BHYT?'):
            self.assertNotIn('lab_guidance', self.ask(question), question)
        result = self.ask('AST và HbA1c có điều kiện BHYT gì?')
        self.assertEqual(result['lab_results'][0]['id'], 'hba1c')
        self.assertEqual(self.ask('ALT, HbA1c có BHYT?')['state']['lab_guide']['tests'], ['alt'])
        self.assertIn('chưa', result['review_note'])
        both = self.ask('Cả thuốc Metformin và xét nghiệm AST có BHYT không?')
        self.assertEqual(both['domain'], 'mixed')
        self.assertTrue(both['results'])
        self.assertIn('AST', both['lab_guide_lead'])

    def test_signed_state_privacy_and_deterministic_answers(self):
        result = self.ask('AST')
        result['state']['lab_guide']['tests'] = ['ana17']
        self.assertNotIn('lab_guidance', self.ask('tại Vinmec', result))
        self.assertNotIn('lab_guidance', self.ask('AST, số điện thoại 0912345678'))
        requester = Mock(side_effect=AssertionError('unexpected provider request'))
        with patch('chat_assist.enabled', return_value=True):
            result = ChatAssistant(self.corpus, requester).respond('AST, ALT có BHYT?')
        self.assertEqual(result['status'], 'lab_guidance')
        requester.assert_not_called()
