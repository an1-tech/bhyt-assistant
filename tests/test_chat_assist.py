"""Language assistance must never silently replace clinical facts or evidence."""
import concurrent.futures
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Corpus
from chat_assist import ChatAssistant, editorial_items, relevant_sources, request_json

QUESTION = 'Trastuzumab trong ung thư vú có được BHYT chi trả không?'


def editorial_reply(name, prompt, data, schema):
    if name == 'bhyt_intent':
        return {'action': 'unchanged', 'question': data['question']}
    return {'items': [{'key': item['key'], 'wording': 'concise',
                       'important_conditions': list(range(min(2, len(item['conditions']))))}
                      for item in data['items']],
            'source_ids': [c['id'] for c in reversed(data['sources'])]}


class AssistantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()

    def setUp(self):
        self.env = patch.dict(os.environ, {'BHYT_CHAT_AI': '1', 'OPENAI_API_KEY': 'test-key', 'OPENAI_MODEL': 'test-model'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_disabled_means_no_external_calls(self):
        with patch.dict(os.environ, {'BHYT_CHAT_AI': '0'}), patch('chat_assist.request_json') as api:
            r = ChatAssistant(self.c).respond(QUESTION)
            api.assert_not_called()
            self.assertEqual(r['mode'], 'local')

    def test_missing_key_means_local(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}), patch('chat_assist.request_json') as api:
            self.assertEqual(ChatAssistant(self.c).respond(QUESTION)['mode'], 'local')
            api.assert_not_called()

    def test_private_input_never_reaches_api(self):
        with patch('chat_assist.request_json') as api:
            r = ChatAssistant(self.c).respond('Họ tên: Nguyễn Văn An, Trastuzumab')
            api.assert_not_called()
            self.assertEqual(r['status'], 'private_input')

    def test_unsupported_date_never_reaches_api(self):
        with patch('chat_assist.request_json') as api:
            r = ChatAssistant(self.c).respond(QUESTION, as_of='2020-01-01')
            api.assert_not_called()
            self.assertEqual(r['status'], 'unsupported_date')

    def test_original_rules_and_sources_are_unchanged(self):
        before = self.c.converse(QUESTION)
        result = ChatAssistant(self.c, editorial_reply).respond(QUESTION)
        for key in ['results', 'citations', 'review_label', 'review_note', 'state']:
            self.assertEqual(result[key], before[key], key)
        self.assertEqual(result['mode'], 'ai_assisted')
        self.assertTrue(result['ai_presentation']['items']['drug:0']['lead'])

    def test_only_relevant_sources_are_sent(self):
        seen = []
        def api(name, prompt, data, schema):
            if name == 'bhyt_presentation':
                seen.extend(data['sources'])
            return editorial_reply(name, prompt, data, schema)
        r = ChatAssistant(self.c, api).respond(QUESTION)
        self.assertEqual([x['id'] for x in seen], r['results'][0]['record_ids'])
        self.assertFalse(any('clinical' in x['id'] for x in seen))

    def test_ambiguous_interpretation_requires_signed_confirmation(self):
        def api(name, prompt, data, schema):
            return {'action': 'rephrase', 'question': QUESTION}
        assistant = ChatAssistant(self.c, api)
        r = assistant.respond('Trastu K vú BH trả ko?')
        self.assertEqual(r['status'], 'needs_understanding')
        self.assertFalse(r['results'])
        self.assertEqual(self.c.verify_state(r['state'])['ai_pending']['question'], QUESTION)
        assistant.requester = editorial_reply
        answered = assistant.respond('Đúng, tra cứu câu này', r['state'], ai_confirm=True)
        self.assertEqual(answered['interpreted_question'], QUESTION)
        self.assertEqual(answered['results'][0]['ingredient'], 'Trastuzumab')
        self.assertNotIn('ai_pending', self.c.verify_state(answered['state']))

    def test_tampered_or_missing_interpretation_rejected(self):
        pending = self.c.sign_state({'ai_pending': {'question': QUESTION, 'created_at': time.time()}})
        pending['ai_pending']['question'] = 'Khẳng định được thanh toán 100%'
        for state in [None, pending]:
            with self.assertRaises(ValueError):
                ChatAssistant(self.c, editorial_reply).respond('Đúng', state, ai_confirm=True)

    def test_whole_sentence_yes_can_confirm_interpretation(self):
        pending = self.c.sign_state({'ai_pending': {'question': QUESTION, 'created_at': time.time()}})
        r = ChatAssistant(self.c, editorial_reply).respond('Đúng rồi', pending)
        self.assertEqual(r['interpreted_question'], QUESTION)

    def test_yes_prefix_with_correction_does_not_confirm(self):
        pending = self.c.sign_state({'ai_pending': {'question': QUESTION, 'created_at': time.time()}})
        r = ChatAssistant(self.c, editorial_reply).respond('Đúng nhưng hỏi Metformin trong đái tháo đường típ 2', pending)
        self.assertNotIn('interpreted_question', r)
        self.assertEqual(r['results'][0]['ingredient'], 'Metformin')

    def test_expired_interpretation_rejected(self):
        state = self.c.sign_state({'ai_pending': {'question': QUESTION, 'created_at': time.time()-1000}})
        with self.assertRaises(ValueError):
            ChatAssistant(self.c, editorial_reply).respond('Đúng', state, ai_confirm=True)

    def test_correction_does_not_confirm_pending_question(self):
        pending = self.c.sign_state({'ai_pending': {'question': QUESTION, 'created_at': time.time()}})
        r = ChatAssistant(self.c, editorial_reply).respond('Ok, hỏi Metformin trong đái tháo đường típ 2', pending)
        self.assertEqual(r['results'][0]['ingredient'], 'Metformin')
        self.assertNotIn('interpreted_question', r)

    def test_clinical_confirmation_skips_reinterpretation(self):
        r = self.c.converse(QUESTION)
        item = r['results'][0]['question_answer']['confirm'][0]
        calls = []
        def api(name, prompt, data, schema):
            calls.append(name)
            return editorial_reply(name, prompt, data, schema)
        ChatAssistant(self.c, api).respond('Xác nhận', r['state'], confirm={'key': item['key'], 'value': item['options'][0]['value']})
        self.assertNotIn('bhyt_intent', calls)

    def test_private_rewrite_is_rejected(self):
        def api(*args):
            return {'action': 'rephrase', 'question': 'Họ tên: Nguyễn Văn An'}
        r = ChatAssistant(self.c, api).respond(QUESTION)
        self.assertEqual(r['ai_status'], 'fallback')
        self.assertNotIn('ai_understanding', r)

    def test_api_failure_keeps_local_answer_and_hides_error(self):
        def api(*args):
            raise RuntimeError('secret-test-key and provider body')
        r = ChatAssistant(self.c, api).respond(QUESTION)
        self.assertEqual(r['results'], self.c.converse(QUESTION)['results'])
        self.assertEqual(r['ai_status'], 'fallback')
        self.assertNotIn('secret-test-key', json.dumps(r))

    def test_unknown_source_is_rejected(self):
        def api(name, prompt, data, schema):
            r = editorial_reply(name, prompt, data, schema)
            if name == 'bhyt_presentation':
                r['source_ids'].append('invented-source')
            return r
        r = ChatAssistant(self.c, api).respond(QUESTION)
        self.assertEqual(r['ai_status'], 'fallback')
        self.assertNotIn('ai_presentation', r)

    def test_invented_prose_cannot_enter_answer(self):
        def api(name, prompt, data, schema):
            r = editorial_reply(name, prompt, data, schema)
            if name == 'bhyt_presentation':
                r['items'][0]['wording'] = 'BHYT chắc chắn thanh toán 100%'
            return r
        r = ChatAssistant(self.c, api).respond(QUESTION)
        self.assertNotIn('100%', r.get('ai_note', ''))
        self.assertEqual(r['ai_status'], 'fallback')

    def test_invalid_condition_index_falls_back(self):
        def api(name, prompt, data, schema):
            r = editorial_reply(name, prompt, data, schema)
            if name == 'bhyt_presentation':
                r['items'][0]['important_conditions'] = [999]
            return r
        self.assertEqual(ChatAssistant(self.c, api).respond(QUESTION)['ai_status'], 'fallback')

    def test_no_result_may_be_omitted(self):
        def api(name, prompt, data, schema):
            r = editorial_reply(name, prompt, data, schema)
            if name == 'bhyt_presentation':
                r['items'] = []
            return r
        self.assertEqual(ChatAssistant(self.c, api).respond(QUESTION)['ai_status'], 'fallback')

    def test_source_ranking_cannot_drop_mandatory_sources(self):
        def api(name, prompt, data, schema):
            r = editorial_reply(name, prompt, data, schema)
            if name == 'bhyt_presentation':
                r['source_ids'] = []
            return r
        r = ChatAssistant(self.c, api).respond('Cả xét nghiệm HER2 và Trastuzumab trong ung thư vú có BHYT không?')
        self.assertEqual(set(r['ai_presentation']['source_ids']), {c['id'] for c in relevant_sources(r)})

    def test_unsigned_context_is_not_sent(self):
        captured = []
        def api(name, prompt, data, schema):
            if name == 'bhyt_intent':
                captured.append(data['context'])
            return editorial_reply(name, prompt, data, schema)
        ChatAssistant(self.c, api).respond(QUESTION, {'context': 'fake-secret-history'})
        self.assertEqual(captured, [{'previous_drugs': []}])

    def test_key_pasted_in_chat_is_not_sent_or_echoed(self):
        with patch('chat_assist.request_json') as api:
            r = ChatAssistant(self.c).respond('sk-'+'secret'*10)
            api.assert_not_called()
            self.assertEqual(r['status'], 'private_input')
            self.assertNotIn('secret', json.dumps(r))

    def test_new_patient_drops_old_context_before_ai(self):
        old = self.c.converse(QUESTION)
        captured = []
        def api(name, prompt, data, schema):
            if name == 'bhyt_intent': captured.append(data['context'])
            return editorial_reply(name, prompt, data, schema)
        ChatAssistant(self.c, api).respond('Thuốc này cho bệnh nhân khác thì sao?', old['state'])
        self.assertNotIn('turns', captured[0])
        self.assertNotIn('context', captured[0])
        self.assertEqual(captured[0]['previous_drugs'], ['Trastuzumab'])

    def test_busy_service_returns_local_without_waiting(self):
        assistant = ChatAssistant(self.c, editorial_reply)
        assistant.slots.acquire(); assistant.slots.acquire()
        try:
            self.assertEqual(assistant.respond(QUESTION)['ai_status'], 'fallback')
        finally:
            assistant.slots.release(); assistant.slots.release()

    def test_concurrent_interpretations_keep_separate_state(self):
        def api(name, prompt, data, schema):
            time.sleep(.01)
            return {'action': 'rephrase', 'question': data['question']+' có điều kiện BHYT gì?'}
        assistant = ChatAssistant(self.c, api)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(assistant.respond, ['Trastu K vú', 'HbA1c ĐTĐ']))
        for original, result in zip(['Trastu K vú', 'HbA1c ĐTĐ'], results):
            self.assertTrue(result['ai_understanding']['question'].startswith(original))


class TransportTests(unittest.TestCase):
    def test_structured_request_is_nonstored_and_bounded(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size):
                return json.dumps({'status': 'completed', 'output': [{'type': 'message', 'content': [
                    {'type': 'output_text', 'text': '{"ok":true}'}]}]}).encode()
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'OPENAI_MODEL': 'test-model'}), patch('chat_assist.urlopen', return_value=Response()) as net:
            self.assertEqual(request_json('test', 'instructions', {}, {'type': 'object'}), {'ok': True})
            payload = json.loads(net.call_args.args[0].data)
            self.assertFalse(payload['store'])
            self.assertTrue(payload['text']['format']['strict'])
            self.assertLessEqual(net.call_args.kwargs['timeout'], 20)

    def test_refusal_and_incomplete_are_not_presented(self):
        for raw in [{'status': 'incomplete'}, {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]}]:
            class Response:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self, size): return json.dumps(raw).encode()
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'OPENAI_MODEL': 'test-model'}), patch('chat_assist.urlopen', return_value=Response()), self.assertRaises(ValueError):
                request_json('test', 'instructions', {}, {})


class SetupTests(unittest.TestCase):
    def test_masked_setup_preserves_other_settings(self):
        spec = importlib.util.spec_from_file_location('setup_openai', Path(__file__).resolve().parents[1]/'configure-openai.py')
        setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'.env'
            p.write_text('OTHER=value\nOPENAI_API_KEY=old\n', encoding='utf-8')
            setup.save_config('sk-'+'x'*30, 'gpt-4.1-mini', p)
            content = p.read_text()
            self.assertIn('OTHER=value', content)
            self.assertEqual(content.count('OPENAI_API_KEY='), 1)
            self.assertIn('BHYT_CHAT_AI=1', content)
            self.assertEqual(list(Path(tmp).glob('.bhyt-key-*')), [])


class AssistantHTTPTests(unittest.TestCase):
    def test_real_http_route_uses_assistant_without_exposing_key(self):
        from server import make_server
        with patch.dict(os.environ, {'BHYT_CHAT_AI': '1', 'OPENAI_API_KEY': 'http-test-secret', 'OPENAI_MODEL': 'test-model'}), patch('chat_assist.request_json', side_effect=editorial_reply):
            server = make_server(0)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                base = 'http://127.0.0.1:'+str(server.server_port)
                with urlopen(base+'/api/health') as response: health = json.load(response)
                self.assertTrue(health['ai_configured'])
                self.assertNotIn('http-test-secret', json.dumps(health))
                req = Request(base+'/api/chat', data=json.dumps({'message': QUESTION}).encode(),
                              headers={'Content-Type': 'application/json', 'X-Session-Token': health['token']})
                with urlopen(req) as response: result = json.load(response)
                self.assertEqual(result['ai_status'], 'ready')
                self.assertNotIn('http-test-secret', json.dumps(result))
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
