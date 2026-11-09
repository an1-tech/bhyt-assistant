"""Direct quotation of the source note in every drug answer.

The quote is the stored TT20 note itself (never re-typed); the parts the answer relies
on are marked by position in that text. A PDF page is given only where it was checked
by eye (data/source_pages.json); other rows open the PDF without a page.
"""
import json
import unittest
from pathlib import Path

from engine import Corpus

ROOT = Path(__file__).resolve().parents[1]
PAGES = json.loads((ROOT / "data/source_pages.json").read_text(encoding="utf-8"))


class Quotes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()

    def quotes(self, q, state=None, i=0):
        r = self.c.converse(q, state or {})
        return r, r["results"][i]["question_answer"]["quotes"]

    def marked(self, quote):
        return [quote["text"][h["start"]:h["end"]] for h in quote["highlights"]]

    def test_quote_is_the_stored_note(self):
        for q in ("Trastuzumab ung thư vú HER2 dương tính", "Oxycodone", "Bevacizumab", "Doxorubicin dạng liposome", "Morphin"):
            r = self.c.converse(q)
            for res in r["results"]:
                for quote in res["question_answer"]["quotes"]:
                    for rid in quote["record_ids"]:
                        self.assertEqual(quote["text"], self.c.by_id[rid].get("conditions_verbatim") or "", q)

    def test_matched_branch_is_marked(self):
        _, qs = self.quotes("Trastuzumab ung thư vú HER2 dương tính")
        self.assertEqual(len(qs), 1)
        self.assertIn("Thanh toán 60% đối với ung thư vú có HER2 dương tính", self.marked(qs[0]))
        self.assertFalse(any("50%" in m for m in self.marked(qs[0])))   # not the gastric branch

    def test_unmet_branch_marks_what_the_source_requires(self):
        r, qs = self.quotes("Trastuzumab ung thư dạ dày HER2 âm tính")
        self.assertEqual(r["results"][0]["question_answer"]["status"], "source_condition_not_met")
        self.assertTrue(any("ung thư dạ dày" in m and "HER2 dương tính" in m for m in self.marked(qs[0])))

    def test_no_branch_chosen_marks_nothing(self):
        _, qs = self.quotes("Trastuzumab")
        self.assertEqual(qs[0]["highlights"], [])
        self.assertIn("Thanh toán 60%", qs[0]["text"])

    def test_formulation_and_rate_only(self):
        _, qs = self.quotes("Doxorubicin dạng liposome")
        self.assertEqual(self.marked(qs[0]), ["thanh toán 50% đối với dạng liposome"])
        _, qs = self.quotes("Everolimus chống thải ghép")
        self.assertEqual(self.marked(qs[0]), ["thanh toán 100% đối với các trường hợp khác"])
        _, qs = self.quotes("Bevacizumab")
        self.assertIn("thanh toán 50%", self.marked(qs[0]))

    def test_checked_page_links_to_that_page(self):
        _, qs = self.quotes("Trastuzumab ung thư vú HER2 dương tính")
        self.assertTrue(qs[0]["page_checked"])
        self.assertEqual(qs[0]["page"], 34)
        self.assertEqual(qs[0]["pdf_url"], "/sources/15-vbhn-byt-2024.pdf#page=34")
        _, qs = self.quotes("Oxycodone")
        self.assertEqual(qs[0]["pdf_url"], "/sources/15-vbhn-byt-2024.pdf#page=8")

    def test_unchecked_row_has_no_page(self):
        _, qs = self.quotes("Paracetamol")
        self.assertFalse(qs[0]["page_checked"])
        self.assertIsNone(qs[0]["page"])
        self.assertNotIn("#page", qs[0]["pdf_url"])
        self.assertTrue(qs[0]["empty"])

    def test_same_note_on_several_routes_is_quoted_once(self):
        _, qs = self.quotes("Morphin")
        stt50 = [q for q in qs if "STT 50" in q["locator"]]
        self.assertEqual(len(stt50), 1)
        self.assertIn("Tiêm / Uống", stt50[0]["locator"])
        self.assertEqual(len(stt50[0]["record_ids"]), 2)

    def test_citation_page_only_when_checked(self):
        r = self.c.converse("Trastuzumab ung thư vú HER2 dương tính")
        tt20 = [c for c in r["citations"] if c["id"] == "TT20-PLI-0402-R481"][0]
        self.assertEqual((tt20["page"], tt20.get("page_checked")), (34, True))
        r = self.c.converse("Paracetamol")
        self.assertTrue(all(c.get("page") is None for c in r["citations"] if c["id"].startswith("TT20-PLI-0056")))

    def test_page_map_only_from_visual_checks(self):
        self.assertEqual(PAGES["pdf"], "/sources/15-vbhn-byt-2024.pdf")
        for rid, entry in PAGES["pages"].items():
            self.assertIn(rid, self.c.by_id)
            self.assertTrue(set(entry["checked_by"]) <= {"rate-verification", "oncology-visual-check"}, rid)
            self.assertTrue(all(isinstance(p, int) and 1 <= p <= 75 for p in entry["pages"]), rid)

    def test_route_unmatched_has_no_quote(self):
        r = self.c.converse("Alpha chymotrypsin tiêm")
        self.assertNotIn("quotes", r["results"][0]["question_answer"])


class ReviewFive(unittest.TestCase):
    """Independent review of the quotation and hospital-list work (2026-11-09)."""
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()

    def ask(self, q, state=None):
        return self.c.converse(q, state or {})

    def test_transition_answer_marks_no_branch(self):
        for q in ("Doxorubicin dạng liposome dùng từ trước năm 2015", "Sorafenib ung thư gan, chuyển tiếp từ 2014"):
            a = self.ask(q)["results"][0]["question_answer"]
            self.assertEqual(a["status"], "transition_requires_review", q)
            self.assertTrue(all(not x["highlights"] for x in a["quotes"]), q)

    def test_glued_names_are_each_checked(self):
        for q in ("Pertuzumab/Trastuzumab ung thư vú HER2 dương tính", "Pertuzumab+Trastuzumab ung thư vú", "Trastuzumab-Pertuzumab ung thư vú"):
            r = self.ask(q)
            self.assertIn("Pertuzumab", r.get("unrecognized") or [], q)
            self.assertIn("Chưa nhận ra trong danh mục: Pertuzumab", r.get("notice", ""), q)
        self.assertIn("Mildagliptin", self.ask("Mildagliptin/Metformin")["unrecognized"])
        self.assertEqual(self.ask("T-DM1 ung thư vú")["unrecognized"], ["T-DM1"])        # a code stays whole
        self.assertFalse(self.ask("Hyoscin-N-Butylbromide").get("unrecognized"))          # hospital spelling

    def test_combination_notice_with_hospital_spelling(self):
        r = self.ask("Metronidazole spiramycin")
        self.assertIn("Spiramycin + metronidazol", r.get("notice", ""))

    def test_one_conversion_sentence_per_medicine(self):
        notes = " ".join(self.ask("Morphine sulfate tiêm tủy sống")["hospital_notes"])
        self.assertEqual(notes.count("Đã quy đổi cách viết"), 1)

    def test_hospital_spelling_without_strength(self):
        r = self.ask("Natri chloride")
        self.assertEqual([x["ingredient"] for x in r["results"]], ["Natri clorid"])
        self.assertIn("“Natri chloride” → “Natri clorid”", " ".join(r["hospital_notes"]))


if __name__ == "__main__":
    unittest.main()
