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

    def test_psa_and_other_markers_in_one_question(self):
        for question in ('CEA, SCC và PSA có BHYT không?', 'CEA, SCC, PSA có BHYT không?'):
            result = self.ask(question)
            self.assertEqual(set(result['state']['lab_guide']['tests']), {'psa_total', 'psa_free'})
            self.assertEqual({r['id'] for r in result['lab_results']}, {'tumor_markers', 'scc'})
            self.assertIn('angiang.gov.vn', str(result['lab_guidance']))
        self.assertEqual(self.ask('SCC có BHYT?')['lab_results'][0]['id'], 'scc')
        screening = self.ask('PSA để tầm soát có BHYT không?')
        free = self.ask('Tự do', screening)
        self.assertEqual(free['state']['lab_guide']['tests'], ['psa_free'])
        self.assertIn('Chưa đủ căn cứ', free['answer'])
        self.assertIn('23.0138.1554', str(free['lab_guidance']))
        self.assertNotIn('23.0139.1553', str(free['lab_guidance']))
        self.assertNotIn('lab_guide', self.ask('PET/CT khi PSA tăng')['state'])
        prostate = self.ask('Các xét nghiệm trong ung thư tuyến tiền liệt để theo dõi?')
        self.assertTrue(any('PSA' in text for text in prostate['suggested_followups']))

    def test_molecular_and_marker_navigation(self):
        result = self.ask('Các xét nghiệm sinh học phân tử và đột biến gen trong ung thư?')
        self.assertEqual({r['id'] for r in result['lab_results']}, {'egfr', 'kras', 'braf', 'her2'})
        panel = self.ask('Giải trình tự gen bằng panel NGS cho u đặc được chi trả không?')
        self.assertIn('Chưa đủ căn cứ', panel['answer'])
        self.assertFalse(panel['lab_results'])
        markers = self.ask('Các xét nghiệm chỉ điểm khối u')
        self.assertEqual(markers['lab_results'][0]['id'], 'tumor_markers')
        self.assertIn('SCC', str(markers['suggested_followups']))
        self.assertIn('sàng lọc', str(self.ask('CA 125 để tầm soát ung thư buồng trứng')['lab_results'][0]['notes']))

    def test_method_and_prognostic_purpose(self):
        cases = [('HER2 bằng ISH cho bệnh nhân ung thư vú đang điều trị hôm nay', 'khuếch đại'),
                 ('BRAF chỉ để tiên lượng cho người bệnh ung thư đại trực tràng đang điều trị hôm nay', 'tiên lượng')]
        for question, wording in cases:
            row = self.ask(question)['lab_results'][0]
            self.assertEqual(row['status'], 'needs_review')
            self.assertIn(wording, row['conclusion'])

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
