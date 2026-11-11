"""One review status per reply.

The notes said "đã thẩm định" while the footer said "Chờ bệnh viện thẩm định" and the copied
text said "chưa được bệnh viện thẩm định". Each part of a reply now states the review status
of exactly what it shows, and the footer and the copied text are built from those statements.
"""
import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import Corpus
from server import make_server

ATTESTED = 'Dược/BHYT đã thẩm định điều kiện (theo xác nhận của nhóm dự án)'
UNREVIEWED = 'Phần đối chiếu chưa được Dược/BHYT thẩm định'
SOURCE_TEXT = 'Trích nguyên văn nguồn'
PARTLY = 'Thẩm định một phần, xem ghi chú từng mục'
OLD_BLANKETS = ('Chờ bệnh viện thẩm định', 'chưa được bệnh viện thẩm định', 'chờ bệnh viện thẩm định')


class ReviewStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()

    def test_label_follows_what_the_reply_shows(self):
        for q, label in [('Trastuzumab ung thư vú HER2 dương tính', ATTESTED), ('Bevacizumab', ATTESTED), ('Paracetamol', SOURCE_TEXT),
                         ('Định lượng BNP', ATTESTED), ('Định lượng CRP', SOURCE_TEXT), ('HbA1c có điều kiện BHYT gì?', UNREVIEWED),
                         ('Xét nghiệm EGFR hôm nay cho bệnh nhân ung thư phổi không tế bào nhỏ đang điều trị', UNREVIEWED),
                         ('Cả xét nghiệm HER2 và Trastuzumab trong ung thư vú có BHYT không?', PARTLY), ('Trastuzumab và Paracetamol', ATTESTED)]:
            self.assertEqual(self.c.converse(q).get('review_label'), label, q)

    def test_note_is_the_same_text_as_each_part(self):
        r = self.c.converse('Cả xét nghiệm HER2 và Trastuzumab trong ung thư vú có BHYT không?')
        drug = r['results'][0]['question_answer']
        lab = r['lab_results'][0]
        self.assertIn(drug['review']['text'], drug['scope'])
        self.assertIn(drug['review']['text'], r['review_note'])
        self.assertIn(lab['review']['text'], r['review_note'])
        self.assertIn('theo xác nhận của nhóm dự án', drug['review']['text'])       # how the review is known stays visible
        self.assertIn('chưa nằm trong phạm vi', lab['review']['text'])

    def test_no_reply_carries_an_old_blanket_sentence(self):
        for q in ('Trastuzumab ung thư vú HER2 dương tính', 'Paracetamol', 'Định lượng BNP', 'HbA1c có điều kiện BHYT gì?', 'Xét nghiệm troponin',
                  'Cả xét nghiệm HER2 và Trastuzumab trong ung thư vú có BHYT không?', 'HbA1c hôm nay theo dõi đái tháo đường, lần trước cách 120 ngày'):
            text = json.dumps(self.c.converse(q), ensure_ascii=False)
            for old in OLD_BLANKETS:
                self.assertNotIn(old, text, q)

    def test_no_label_when_nothing_was_looked_up(self):
        for q in ('Xét nghiệm troponin có được BHYT không?', 'Gaviscon'):
            self.assertNotIn('review_label', self.c.converse(q), q)

    def test_page_and_bundled_sources_do_not_hard_code_a_status(self):
        script = (ROOT / 'web/app.js').read_text(encoding='utf-8')
        bundle = (ROOT / 'data/lab_services.json').read_text(encoding='utf-8')
        for old in OLD_BLANKETS:
            self.assertNotIn(old, script)
            self.assertNotIn(old, bundle)
        self.assertIn('data.review_label', script)
        self.assertIn('data.review_note', script)

    def test_source_catalogue_states_scope_and_missing_record(self):
        server = make_server(0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f'http://127.0.0.1:{server.server_port}/api/metadata') as response:
                meta = json.load(response)
        finally:
            server.shutdown(); server.server_close(); thread.join()
        self.assertIn('đã thẩm định ngày 11/11/2026', meta['review_status'])
        self.assertIn('28 nhánh điều kiện', meta['review_status'])
        self.assertIn('Chưa lưu biên bản', meta['review_status'])
        self.assertIn('chưa nằm trong phạm vi', meta['lab_source']['review_status'])


class RefusalsAreAnswered(unittest.TestCase):
    """A refused POST got a reset connection now and then instead of its status code: the server
    answered before reading the body. Every refusal must arrive as a clean HTTP error."""

    def test_refused_posts_always_get_their_status(self):
        from urllib.error import HTTPError
        from urllib.request import Request
        server = make_server(0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        body = json.dumps({'message': 'Trastuzumab ung thư vú ' * 40}).encode()
        try:
            for path, headers, expected in (('/api/chat', {'Content-Type': 'application/json'}, 403),
                                            ('/api/chat', {'Content-Type': 'application/json', 'X-Session-Token': 'sai'}, 403)):
                for _ in range(60):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(Request(base + path, data=body, headers=headers))
                    self.assertEqual(error.exception.code, expected)
        finally:
            server.shutdown(); server.server_close(); thread.join()


class OversizedRefusals(unittest.TestCase):
    """A refused request far larger than the limit was still reset now and then: only the first
    20 KB of it was read. The rest is now read and discarded, or the connection closed gently."""

    @classmethod
    def setUpClass(cls):
        cls.server = make_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        with urlopen(cls.base + '/api/health') as response:
            cls.token = json.load(response)['token']

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def refused(self, size, headers, times):
        from urllib.error import HTTPError
        from urllib.request import Request
        body = json.dumps({'message': 'x' * size}).encode()
        codes = []
        for _ in range(times):
            try:
                urlopen(Request(self.base + '/api/chat', data=body, headers={'Content-Type': 'application/json', **headers}), timeout=30)
                codes.append(200)
            except HTTPError as error:
                codes.append(error.code)
        return set(codes)

    def test_half_megabyte(self):
        self.assertEqual(self.refused(500_000, {}, 25), {403})
        self.assertEqual(self.refused(500_000, {'X-Session-Token': self.token}, 25), {413})

    def test_several_megabytes(self):
        self.assertEqual(self.refused(3_000_000, {}, 10), {403})
        self.assertEqual(self.refused(3_000_000, {'X-Session-Token': self.token}, 10), {413})

    def test_beyond_what_the_server_will_read(self):
        self.assertEqual(self.refused(20_000_000, {}, 2), {403})
        self.assertEqual(self.refused(20_000_000, {'X-Session-Token': self.token}, 2), {413})

    def test_an_ordinary_question_still_works_afterwards(self):
        from urllib.request import Request
        request = Request(self.base + '/api/chat', data=json.dumps({'message': 'Paracetamol'}).encode(),
                          headers={'Content-Type': 'application/json', 'X-Session-Token': self.token})
        with urlopen(request) as response:
            self.assertEqual(json.load(response)['results'][0]['ingredient'], 'Paracetamol (acetaminophen)')


class SourceLabel(unittest.TestCase):
    def test_lab_source_is_named_in_one_place_only(self):
        script = (ROOT / 'web/app.js').read_text(encoding='utf-8')
        start = script.index('function sourceStamp(data)')
        end = script.index('\n', start)
        outside = script[:start] + script[end:]
        self.assertNotIn('Nguồn xét nghiệm kiểm tra', outside)        # footer and copied text both call sourceStamp()
        self.assertEqual(outside.count('sourceStamp(data)'), 2)
        self.assertIn("data.domain==='lab'||data.domain==='mixed'", script[start:end])


if __name__ == '__main__':
    unittest.main()
