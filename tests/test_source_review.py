import copy
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from engine import Corpus, read_jsonl
from source_review import apply_source_review, effective_fingerprint

class SourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=Corpus()
        cls.raw=read_jsonl(cls.c.data/"rag_current.jsonl")
        cls.manifest=cls.c.data/"source_review.json"

    def test_star_symbol_and_reference_year_match_images(self):
        text=self.c.by_chunk["TT37_2024-P8-S0-1"]["text"]
        self.assertNotIn("dấu sao ($)",text)
        self.assertNotIn("dấu sao (#)",text)
        self.assertEqual(text.count("dấu sao (*)"),2)
        cv=self.c.by_chunk["CV3293_2025-UTF8-C3"]["text"]
        self.assertNotIn("20/2021/TT-BYT",cv)
        self.assertIn("20/2022/TT-BYT",cv)

    def test_decay_example_and_fraction_not_corrupted(self):
        text=self.c.by_chunk["TT37_2024-P20-S0-1"]["text"]
        for token in ("I-131","100%","50%","25%","T1/2"):
            self.assertIn(token,text)
        for token in ("509","5€","1009"):
            self.assertNotIn(token,text)
        self.assertIn("HCĐD là ¼",self.c.by_chunk["TT37_2024-P19-S0-1"]["text"])

    def test_source_review_is_non_mutating_and_complete(self):
        before=copy.deepcopy(self.raw)
        corrected=apply_source_review(self.raw,self.manifest)
        self.assertEqual(before,self.raw)
        changed={c["id"] for c,src in zip(corrected,self.raw) if c["text"]!=src["text"]}
        approved={p["id"] for p in json.loads(self.manifest.read_text(encoding="utf8"))["patches"]}
        self.assertEqual(changed,approved)
        self.assertEqual(len(changed),17)
        for c in corrected:
            if c["kind"] in ("drug_row","radiopharmaceutical_row"):
                self.assertEqual(c,next(x for x in self.raw if x["id"]==c["id"]))

    def test_stale_source_fails_closed(self):
        raw=copy.deepcopy(self.raw)
        next(c for c in raw if c["id"]=="TT37_2024-P8-S0-1")["text"]+=" changed"
        with self.assertRaisesRegex(ValueError,"stale"):
            apply_source_review(raw,self.manifest)

    def test_edit_count_mismatch_fails_closed(self):
        manifest=json.loads(self.manifest.read_text(encoding="utf8"))
        manifest["patches"][0]["edits"][0]["count"]+=1
        with tempfile.TemporaryDirectory(dir=self.c.data.parent/"audit/source-review") as tmp:
            f=Path(tmp)/"review.json"
            f.write_text(json.dumps(manifest),encoding="utf8")
            with self.assertRaisesRegex(ValueError,"mismatch"):
                apply_source_review(self.raw,f)

    def test_old_embedding_fingerprint_skips_paid_api(self):
        with tempfile.TemporaryDirectory(dir=self.c.data.parent/"audit/source-review") as tmp:
            f=Path(tmp)/"old.sqlite"
            with sqlite3.connect(f) as db:
                db.execute("create table metadata(key text,value text)")
                db.executemany("insert into metadata values(?,?)",[("corpus_sha256",self.c.source_fingerprint),("model","test"),("complete","true")])
            db.close()
            with patch.object(self.c,"semantic_path",f), patch.dict(os.environ,{"OPENAI_API_KEY":"test-only","OPENAI_EMBEDDING_MODEL":"test"}), patch("engine.api_post") as api:
                self.assertEqual(self.c.semantic_search("thuốc"),[])
                api.assert_not_called()
        self.assertNotEqual(self.c.fingerprint,self.c.source_fingerprint)
        modified=copy.deepcopy(self.c.chunks)
        modified[0]["text"]+=" changed"
        self.assertNotEqual(effective_fingerprint(modified),self.c.fingerprint)

    def test_transition_review_is_visible_and_skips_ai(self):
        with patch.dict(os.environ,{"BHYT_ENABLE_AI":"1","OPENAI_API_KEY":"test-only","OPENAI_MODEL":"test"}), patch("engine.api_post") as api:
            for drug in ("Doxorubicin","Erlotinib","Gefitinib","Sorafenib","Everolimus","Paclitaxel"):
                result=self.c.chat(drug)
                self.assertIn("Điều 8",result["notice"],drug)
                self.assertNotIn("ai_explanation",result)
            api.assert_not_called()

    def test_citation_exposes_correction_evidence(self):
        citation=self.c.citation(self.c.by_chunk["TT37_2024-P8-S0-1"])
        self.assertEqual(citation["source_review"]["evidence"]["page"],8)
        self.assertEqual(citation["source_review"]["hospital_validation"],"pending")

    def test_all_recorded_rate_checks_still_match(self):
        checks=json.loads((self.c.data.parent/"audit/source-review/rate-verification.json").read_text(encoding="utf8"))
        self.assertEqual(len(checks),59)
        for check in checks:
            note=self.c.by_id[check["record_id"]]["conditions_verbatim"]
            self.assertEqual(hashlib.sha256(note.encode()).hexdigest(),check["note_sha256"])
