import json,os,sys,threading,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Corpus
from server import make_server

class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=Corpus()
    def test_complete_counts(self):
        self.assertEqual(len({r['stt'] for r in self.c.drugs}),1037)
        self.assertEqual(len({r['stt'] for r in self.c.radio}),59)
    def test_exact_lookup_preserves_condition(self):
        r=self.c.chat('Trastuzumab có được hưởng BHYT không?')
        self.assertEqual(r['results'][0]['ingredient'],'Trastuzumab')
        self.assertIn('HER2',r['results'][0]['conditions'][0])
        self.assertTrue(any(x.get('page') for x in r['citations']))
    def test_missing_default_flag_does_not_drop_drugs(self):
        self.assertIn('TT20-PLI-0402-R481',self.c.by_chunk)
    def test_fuzzy_is_not_automatic_confirmation(self):
        r=self.c.chat('Trastuzmab');self.assertEqual(r['status'],'ambiguous')
        self.assertIn('Trastuzumab',r['suggestions']);self.assertFalse(r['results'])
    def test_brand_without_verified_mapping(self):
        self.assertEqual(self.c.chat('Kadcyla')['status'],'unknown')
    def test_verified_brand_mapping_resolves_with_source(self):
        r=self.c.converse('Herceptin điều trị ung thư vú có BHYT?')
        self.assertEqual(r['results'][0]['ingredient'],'Trastuzumab')
        self.assertTrue(any('ema.europa.eu' in n and 'Việt Nam' in n for n in r['brand_notes']))
        self.assertEqual(r['status'],'answered');self.assertEqual(r['lookup_status'],'needs_info')
    def test_unverified_alias_entries_are_ignored(self):
        import json,tempfile,shutil
        from pathlib import Path
        with tempfile.TemporaryDirectory(dir=self.c.data.parent/'audit') as tmp:
            data=Path(tmp)
            for f in self.c.data.iterdir():
                if f.is_file():shutil.copy2(f,data/f.name)
            shutil.copytree(self.c.data/'sources',data/'sources')
            (data/'aliases.json').write_text(json.dumps([{'brand':'Fakebrand','ingredient':'Trastuzumab','verified':False,'source_url':'https://example.org'},{'brand':'Nosource','ingredient':'Trastuzumab','verified':True}]),encoding='utf-8')
            c=Corpus(data)
            self.assertEqual(c.aliases,{})
            self.assertFalse(c.resolve('Fakebrand Nosource'))
    def test_route_followup(self):
        r=self.c.chat('Lidocain hydroclodrid');self.assertIn('Khí dung',r['followups'])
        next=self.c.chat('Khí dung',r['state']);self.assertEqual(next['results'][0]['routes'],['Khí dung'])
    def test_clinical_context_does_not_guarantee_coverage(self):
        r=self.c.chat('Trastuzumab');n=self.c.chat('ung thư vú HER2 dương tính',r['state'])
        self.assertEqual(n['status'],'needs_info');self.assertIn('HER2',n['state']['context'])
    def test_new_drug_resets_old_context(self):
        a=self.c.chat('Trastuzumab');b=self.c.chat('ung thư vú HER2 dương tính',a['state']);c=self.c.chat('Atropin sulfat',b['state'])
        self.assertEqual(c['state']['context'],'')
    def test_distinct_drugs_do_not_mix(self):
        r=self.c.chat('Trastuzumab và Abiraterone acetate');self.assertEqual(len(r['results']),2)
        self.assertNotEqual(r['results'][0]['conditions'],r['results'][1]['conditions'])
    def test_mismatched_route(self):
        r=self.c.chat('Trastuzumab uống');self.assertEqual(r['results'][0]['status'],'route_unmatched')
        n=self.c.chat('Tiêm',r['state']);self.assertEqual(n['results'][0]['ingredient'],'Trastuzumab');self.assertEqual(n['results'][0]['routes'],['Tiêm'])
    def test_empty_note_is_not_full_payment(self):
        r=self.c.chat('Anastrozol');self.assertTrue(r['results'][0]['empty_note']);self.assertIn('100%',r['answer'])
    def test_unknown_not_denied(self):
        r=self.c.chat('ZZZ123');self.assertEqual(r['status'],'unknown');self.assertIn('chưa đủ',r['answer'])
    def test_no_repealed_or_deferred_chunks(self):
        self.assertFalse(any(x.get('document_id')=='TT37_2024' and x.get('article')==7 for x in self.c.chunks))
        self.assertFalse(any(x.get('document_id','').startswith('TT20') and x.get('article') in [3,4,5,6] for x in self.c.chunks))
    def test_date_outside_snapshot_rejected(self):
        self.assertEqual(self.c.chat('Trastuzumab',as_of='2027-01-01')['status'],'unsupported_date')
    def test_suggested_pii_not_sent_to_provider(self):
        with patch('engine.api_post') as api:
            self.assertEqual(self.c.chat('mã bệnh án: ABC123')['status'],'private_input');api.assert_not_called()
    def test_utf8_policy_repaired(self):
        rows=[x for x in self.c.chunks if x['document_id']=='CV3293_2025']
        self.assertTrue(any('Bộ Y tế' in x['text'] for x in rows));self.assertFalse(any('Ã¡' in x['text'] for x in self.c.chunks))
    def test_ai_cannot_invent_citations(self):
        fake={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'summary':'Được trả 100%','source_ids':['invented']})}]}]}
        with patch.dict(os.environ,{'BHYT_ENABLE_AI':'1','OPENAI_API_KEY':'test','OPENAI_MODEL':'test'}),patch('engine.api_post',return_value=fake):
            r=self.c.chat('Trastuzumab');self.assertNotIn('ai_explanation',r);self.assertIn('notice',r)
    def test_valid_ai_output_does_not_change_status(self):
        fake={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'summary':'Cần đối chiếu điều kiện trong nguồn.','source_ids':['TT20-PLI-0402-R481']})}]}]}
        with patch.dict(os.environ,{'BHYT_ENABLE_AI':'1','OPENAI_API_KEY':'test','OPENAI_MODEL':'test'}),patch('engine.api_post',return_value=fake):
            r=self.c.chat('Trastuzumab');self.assertEqual(r['mode'],'ai');self.assertEqual(r['status'],'needs_info')
    def test_unsupported_percentage_rejected(self):
        fake={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'summary':'Thanh toán 99.123%','source_ids':['TT20-PLI-0402-R481']})}]}]}
        with patch.dict(os.environ,{'BHYT_ENABLE_AI':'1','OPENAI_API_KEY':'test','OPENAI_MODEL':'test'}),patch('engine.api_post',return_value=fake):
            self.assertNotIn('ai_explanation',self.c.chat('Trastuzumab'))
    def test_invalid_state(self):
        with self.assertRaises(ValueError):self.c.chat('Trastuzumab',state='invalid')

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server(0);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.base='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,path,body=None,token=None):
        headers={}
        if body is not None:headers['Content-Type']='application/json'
        if token:headers['X-Session-Token']=token
        return urlopen(Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers),timeout=10)
    def test_static_assets(self):
        for path in ['/','/app.js','/style.css']:
            with self.request(path) as r:self.assertEqual(r.status,200);self.assertTrue(r.headers['Content-Security-Policy'])
    def test_health_and_chat(self):
        with self.request('/api/health') as r:health=json.load(r)
        self.assertEqual(health['drug_entries'],1037)
        with self.request('/api/chat',{'message':'Trastuzumab'},health['token']) as r:self.assertEqual(json.load(r)['results'][0]['ingredient'],'Trastuzumab')
    def test_csrf_rejected(self):
        with self.assertRaises(HTTPError) as e:self.request('/api/chat',{'message':'Trastuzumab'})
        self.assertEqual(e.exception.code,403)
    def test_path_traversal_not_served(self):
        with self.assertRaises(HTTPError) as e:self.request('/../.env')
        self.assertEqual(e.exception.code,404)
    def test_bad_host_rejected(self):
        with self.assertRaises(HTTPError) as e:urlopen(Request(self.base+'/api/health',headers={'Host':'evil.invalid'}))
        self.assertEqual(e.exception.code,403)

if __name__=='__main__':unittest.main(verbosity=2)
