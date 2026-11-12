"""Browser-test fixture: all OpenAI requests are mocked, never billed."""
import argparse
import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import make_server


def mock_request(name, prompt, data, schema):
    if 'Lỗi API thử nghiệm' in data['question']:
        raise RuntimeError('Simulated outage')
    if name == 'bhyt_intent':
        if data['question'] == 'Trastu K vú BH trả ko?':
            return {'action': 'rephrase', 'question': 'Trastuzumab trong ung thư vú có được BHYT chi trả không?'}
        return {'action': 'unchanged', 'question': data['question']}
    return {'items': [{'key': x['key'], 'wording': 'concise',
                       'important_conditions': list(range(min(2, len(x['conditions']))))}
                      for x in data['items']], 'source_ids': [x['id'] for x in data['sources']]}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--port', type=int, default=8881)
    args = p.parse_args()
    with patch.dict(os.environ, {'BHYT_CHAT_AI': '1', 'OPENAI_API_KEY': 'fixture-only', 'OPENAI_MODEL': 'fixture-only'}), patch('chat_assist.request_json', side_effect=mock_request):
        server = make_server(args.port)
        try: server.serve_forever()
        finally: server.server_close()
