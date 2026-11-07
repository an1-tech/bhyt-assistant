import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen
from clinical_sources import ClinicalSources
from engine import Corpus
from case_workbench import CaseWorkbench
from server import make_server

class ClinicalSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=Corpus();cls.s=cls.c.supplemental;cls.w=CaseWorkbench(cls.c)
        cls.trast="TT20-PLI-0402-R481"

    def result(self,id=None,answers=None):
        return self.w.evaluate({"drug_id":id or self.trast,"answers":answers or {},"facts":{}})

    def clinical(self,r):
        return [c for c in r["citations"] if c.get("kind","").startswith("clinical")]

    def test_full_pdf_page_provenance(self):
        self.assertEqual(len(self.s.documents),6)
        self.assertEqual(len(self.s.pages),204)
        self.assertEqual(sum(c["eligible_reference"] for c in self.s.pages.values()),99)
        for d in self.s.documents:
            self.assertFalse(d["payment_authority"])
            self.assertFalse(d["latest_version_verified"])
            self.assertEqual(d["checked_as_of"],"2026-11-07")

    def test_clinical_data_never_enter_payment_or_ai_index(self):
        ids=set(self.s.by_id)
        self.assertFalse(any(c["document_id"] in ids for c in self.c.chunks))
        self.assertFalse(any(c["document_id"] in ids for c in self.c.chat("Trastuzumab tiêm")["citations"]))

    def test_breast_and_gastric_contexts_do_not_cross(self):
        for indication,doc in (("breast","QD3128_2020"),("gastric","QD3127_2020")):
            r=self.result(answers={"indication":indication,"her2":"positive","extent":"advanced"})
            refs=self.clinical(r)
            self.assertTrue(refs)
            self.assertEqual({c["document_id"] for c in refs},{doc})
            self.assertTrue(all("#page=" in c["local_url"] for c in refs))
            self.assertTrue(all(c["kind"]=="clinical_reference" for c in refs))
            self.assertEqual(r["source_coverage"][1]["status"],"reference")
            self.assertIsNone(r["payment_eligibility"])

    def test_unknown_or_other_indication_does_not_choose_guideline(self):
        for answers in ({},{"indication":"other"}):
            self.assertEqual(self.clinical(self.result(answers=answers)),[])

    def test_scan_and_amendment_are_pointers_only(self):
        row=next(r for r in self.c.rows if r["ingredient"]=="Erlotinib")
        r=self.result(row["record_id"],{"indication":"nsclc","egfr":"positive"})
        refs=self.clinical(r)
        self.assertEqual({c["document_id"] for c in refs},{"QD4825_2018","QD1248_2019"})
        self.assertEqual({c["page"] for c in refs if c["document_id"]=="QD1248_2019"},{1,2})
        self.assertTrue(all(c["kind"]=="clinical_document_pointer" for c in refs))
        self.assertEqual(r["source_coverage"][1]["status"],"pdf_only")
        self.assertEqual(r["candidate_source_rate"]["percentage"],50)

    def test_unsigned_diabetes_files_never_supply_clinical_excerpts(self):
        row=next(r for r in self.c.rows if r["ingredient"]=="Metformin")
        r=self.result(row["record_id"],{"clinical_topic":"t2d"})
        self.assertEqual({c["document_id"] for c in self.clinical(r)},{"QD5481_2020","QD1353_2021"})
        self.assertTrue(all(c["kind"]=="clinical_document_pointer" for c in self.clinical(r)))
        self.assertTrue(all(c["excerpt"].startswith("Chỉ dẫn tài liệu:") for c in self.clinical(r)))
        self.assertEqual(r["source_coverage"][1]["status"],"pending")
        self.assertIsNone(r["candidate_source_rate"])

    def test_new_source_selector_is_validated_and_no_brand_verified(self):
        id="TT20-PLI-0381-R459"
        with self.assertRaises(ValueError):self.result(id,{"clinical_topic":"t2d"})
        r=self.result(id,{"formulation":"liposome","clinical_topic":"breast"})
        self.assertEqual(r["candidate_source_rate"]["percentage"],50)
        self.assertTrue(self.clinical(r))
        self.assertTrue(all(s["status"]=="missing" for s in r["source_coverage"][2:]))

    def check_broken(self,modify=None,broken_pdf=False,broken_chunks=False):
        with tempfile.TemporaryDirectory(dir=self.c.data.parent/"audit") as tmp:
            data=Path(tmp);shutil.copytree(self.c.data/"sources/clinical",data/"sources/clinical")
            shutil.copy2(self.c.data/"clinical_pages.jsonl",data/"clinical_pages.jsonl")
            registry=copy.deepcopy(self.s.registry)
            if modify:modify(registry)
            (data/"supplemental_sources.json").write_text(json.dumps(registry),encoding="utf-8")
            if broken_pdf:
                with (data/registry["documents"][0]["local_file"]).open("ab") as f:f.write(b"changed")
            if broken_chunks:
                with (data/"clinical_pages.jsonl").open("ab") as f:f.write(b"changed")
            with self.assertRaises(ValueError):ClinicalSources(data)

    def test_tampered_pdf_and_chunks_rejected(self):
        self.check_broken(broken_pdf=True);self.check_broken(broken_chunks=True)

    def test_path_escape_and_draft_activation_rejected(self):
        self.check_broken(lambda r:r["documents"][0].update(local_file="../outside.pdf"))
        self.check_broken(lambda r:r["documents"][0].update(status="draft"))

    def test_missing_amendment_rejected(self):
        self.check_broken(lambda r:r["documents"][2].update(related_documents=["UNKNOWN"]))

    def test_source_http_routes_allow_only_registered_pdfs(self):
        server=make_server(0,self.c)
        import threading
        from urllib.error import HTTPError
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base="http://127.0.0.1:"+str(server.server_port)
            for path in self.s.local_files:
                with urlopen(base+path) as f:
                    self.assertEqual(f.headers.get_content_type(),"application/pdf")
                    self.assertEqual(f.read(4),b"%PDF")
            for path in ("/sources/clinical/../../.env","/sources/clinical/not-registered.pdf"):
                with self.assertRaises(HTTPError) as e:urlopen(base+path)
                self.assertEqual(e.exception.code,404)
            with urlopen(base+"/api/metadata") as f:m=json.load(f)
            self.assertEqual(len(m["sources"]),4)
            self.assertEqual(len(m["source_update"]["documents"]),6)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=="__main__":unittest.main()
