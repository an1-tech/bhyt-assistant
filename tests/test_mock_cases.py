"""Mock case set (data/mock_cases.json): every case must come out as the legal text says.

The cases are synthetic and labelled so everywhere; the set measures consistency with the
text, not real payment decisions.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import Corpus
from tools.run_mock_cases import run


class MockCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()
        cls.bundle, cls.rows = run(cls.c)

    def test_set_is_labelled_synthetic(self):
        self.assertIn("GIẢ LẬP", self.bundle["nature"])
        self.assertIn("không phải quyết định", self.bundle["nature"])
        ids = [c["id"] for c in self.bundle["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(c["expected"] in self.bundle["outcomes"] for c in self.bundle["cases"]))

    def test_every_outcome_is_covered(self):
        self.assertEqual({c["expected"] for c in self.bundle["cases"]}, set(self.bundle["outcomes"]))

    def test_chatbot_is_consistent_with_the_text(self):
        for r in self.rows:
            self.assertEqual(r["got"], r["expected"], r["id"] + ": " + r["question"])

    def test_no_identifier_in_any_case(self):
        text = json.dumps(self.bundle, ensure_ascii=False)
        for r in self.rows:
            self.assertNotEqual(self.c.converse(r["question"])["status"], "private_input", r["id"])
        self.assertNotRegex(text, r"\b\d{9,12}\b")


class FacilityNote(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()

    def test_recorded_class_is_shown_as_unverified(self):
        conditions = " ".join(self.c.converse("Bevacizumab")["results"][0]["question_answer"]["conditions"])
        self.assertIn("Vinmec", conditions)
        self.assertIn("tương đương bệnh viện hạng I", conditions)
        self.assertIn("Chưa có văn bản xếp hạng", conditions)

    def test_not_shown_where_the_note_names_no_hospital_class(self):
        conditions = " ".join(self.c.converse("Erlotinib ung thư phổi không tế bào nhỏ EGFR dương tính")["results"][0]["question_answer"]["conditions"])
        self.assertNotIn("Vinmec", conditions)


if __name__ == "__main__":
    unittest.main()
