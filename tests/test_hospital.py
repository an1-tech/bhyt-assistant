import hashlib,json,os,threading,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from engine import Corpus,ROOT
from catalog import catalog,metadata,DEPARTMENTS
from server import make_server

class HospitalCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=Corpus()
    def test_every_printed_name_remains_resolvable(self):
        for rows in self.c.names.values():
            with self.subTest(ingredient=rows[0]['ingredient']):
                self.assertEqual(self.c.resolve(rows[0]['ingredient']),[rows])
    def test_original_source_datasets_are_unchanged(self):
        manifest=json.loads((ROOT/'audit/PACKAGE_SHA256.json').read_text('utf-8'))
        for filename in ['data/drugs_appendix_I.jsonl','data/radiopharmaceuticals_appendix_II.jsonl','data/rag_current.jsonl']:
            self.assertEqual(hashlib.sha256((ROOT/filename).read_bytes()).hexdigest(),manifest[filename])
    def test_common_name_and_printed_synonym(self):
        for name in ['Paracetamol','acetaminophen']:
            r=self.c.chat(name)
            self.assertEqual(r['results'][0]['ingredient'],'Paracetamol (acetaminophen)')
            self.assertIn('Uống',r['followups'])
    def test_combination_does_not_collapse_to_paracetamol(self):
        r=self.c.chat('Paracetamol + codein phosphat')
        self.assertEqual([x['ingredient'] for x in r['results']],['Paracetamol + codein phosphat'])
    def test_suppository_followup_preserves_drug(self):
        first=self.c.chat('Paracetamol');r=self.c.chat('đặt',first['state'])
        self.assertEqual(r['results'][0]['routes'],['Uống, đặt'])
    def test_special_route_has_no_parent_double_match(self):
        self.assertEqual(self.c.detect_route('Tiêm trong dịch kính'),['Tiêm trong dịch kính'])
    def test_every_literal_route_is_detectable(self):
        for route in {part.strip() for r in self.c.rows for part in r['route'].split(',')}:
            self.assertTrue(self.c.detect_route(route),route)
    def test_mixed_routes_ask_for_separate_lookup(self):
        r=self.c.chat('Metformin uống và Trastuzumab tiêm')
        self.assertEqual(r['status'],'needs_info');self.assertFalse(r['results'])
        self.assertIn('Metformin',r['suggestions']);self.assertIn('Trastuzumab',r['suggestions'])
    def test_non_oncology_context_is_retained(self):
        r=self.c.chat('Metformin');n=self.c.chat('đái tháo đường type 2',r['state'])
        self.assertEqual(n['results'][0]['ingredient'],'Metformin')
        self.assertIn('đái tháo đường',n['state']['context'])
        self.assertEqual(n['status'],'needs_info')
    def test_catalog_complete_unique_and_paged(self):
        ids=[]
        for page in range(1,56):
            result=catalog(self.c,page=page)
            ids.extend((x['appendix'],x['stt']) for x in result['items'])
        self.assertEqual(len(ids),1096);self.assertEqual(len(set(ids)),1096)
    def test_pharmacy_and_nuclear_lists_are_separate(self):
        self.assertEqual(catalog(self.c,appendix='I')['total'],1037)
        self.assertEqual(catalog(self.c,appendix='II')['total'],59)
    def test_group_filter_preserves_source_rows(self):
        groups=metadata(self.c)['groups'];total=sum(catalog(self.c,group=g)['total'] for g in groups)
        self.assertEqual(total,1096)
        cardiac=next(g for g in groups if 'tim mạch' in g)
        self.assertGreater(catalog(self.c,group=cardiac)['total'],50)
    def test_unaccented_search_and_empty_result(self):
        self.assertGreater(catalog(self.c,query='metformin')['total'],0)
        self.assertEqual(catalog(self.c,query='ZZZ-NONEXISTENT')['total'],0)
    def test_metadata_reports_review_limits(self):
        m=metadata(self.c);self.assertEqual(len(m['sources']),4)
        self.assertIn('Chưa',m['review_status']);self.assertTrue(m['missing'])
    def test_default_never_calls_paid_api(self):
        with patch.dict(os.environ,{'BHYT_ENABLE_AI':'0'}),patch('engine.api_post') as api:
            self.c.chat('Amlodipin');api.assert_not_called()

class HospitalHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server(0);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.server.server_port)
        with urlopen(cls.base+'/api/health') as r:cls.token=json.load(r)['token']
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def test_every_department_can_lookup_non_oncology_drug(self):
        for department in DEPARTMENTS:
            req=Request(self.base+'/api/chat',data=json.dumps({'message':'Metformin','department':department}).encode(),headers={'Content-Type':'application/json','X-Session-Token':self.token})
            with urlopen(req) as response:r=json.load(response)
            self.assertEqual(r['department'],department);self.assertEqual(r['results'][0]['ingredient'],'Metformin')
    def test_catalog_metadata_and_fonts(self):
        for path in ['/api/metadata','/api/catalog?q=metformin','/fonts/geist-400.ttf','/fonts/geist-600.ttf']:
            with urlopen(self.base+path) as r:self.assertEqual(r.status,200);self.assertTrue(r.read())
    def test_bad_page_gets_validation_error(self):
        with self.assertRaises(HTTPError) as e:urlopen(self.base+'/api/catalog?page=nope')
        self.assertEqual(e.exception.code,400)
    def test_unknown_department_gets_validation_error(self):
        req=Request(self.base+'/api/chat',data=json.dumps({'message':'Metformin','department':'invented'}).encode(),headers={'Content-Type':'application/json','X-Session-Token':self.token})
        with self.assertRaises(HTTPError) as e:urlopen(req)
        self.assertEqual(e.exception.code,400)
    def test_only_allowlisted_source_files_are_served(self):
        with urlopen(self.base+'/sources/37-2024-tt-byt.pdf') as r:
            self.assertEqual(r.headers.get_content_type(),'application/pdf');self.assertEqual(r.read(4),b'%PDF')
        with self.assertRaises(HTTPError) as e:urlopen(self.base+'/sources/../../.env')
        self.assertEqual(e.exception.code,404)

if __name__=='__main__':unittest.main()
