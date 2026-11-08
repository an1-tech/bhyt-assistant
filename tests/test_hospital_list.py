"""Hospital public drug list (data/hospital/): every entry kept, only deterministic matches used.

The list (website "Danh sách thuốc", 24 screenshots) prints active-ingredient names in
English spelling, a few product names and some typos. A hospital spelling may find a TT20
row only through the fixed rules of tools/match_hospital_list.py, and the answer says so.
Product names, typos and look-alike names are never mapped automatically.
"""
import hashlib
import json
import unittest
from pathlib import Path

from engine import Corpus
from tools.match_hospital_list import PRODUCT_NAMES, TYPO_SUSPECTS, USABLE, skeleton

ROOT = Path(__file__).resolve().parents[1]
LIST = json.loads((ROOT / "data/hospital/hospital_drug_list.json").read_text(encoding="utf-8"))
MATCH = json.loads((ROOT / "data/hospital/hospital_tt20_match.json").read_text(encoding="utf-8"))


class ListData(unittest.TestCase):
    def test_every_entry_kept(self):
        entries = LIST["entries"]
        self.assertEqual(len(entries), 192)
        self.assertEqual(len({e["id"] for e in entries}), 192)
        self.assertEqual(len([e for e in entries if not e["duplicate_of"]]), 188)
        self.assertEqual(sorted(e["text"] for e in entries if e["duplicate_of"]),
                         ["Abobotulinum Toxin A", "Alendronate", "Fluconazole", "Zopiclon"])
        self.assertEqual([r["id"] for r in MATCH["results"]], [e["id"] for e in entries])

    def test_typos_kept_as_printed(self):
        texts = {e["text"] for e in LIST["entries"]}
        for t in ("Perindorpil", "Mildagliptin/Metformin", "Minagliptin", "Mytomycin C", "Methycobalamin"):
            self.assertIn(t, texts)

    def test_source_file_hash(self):
        raw = ROOT / "data/hospital/raw/Doc1.docx"
        if not raw.exists():
            self.skipTest("raw document not in this checkout")
        self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(), LIST["source_file_sha256"])

    def test_limitations_stated(self):
        text = " ".join(LIST["limitations"])
        for phrase in ("không có biệt dược", "J, Q, U, Y", "không có nghĩa"):
            self.assertIn(phrase, text)


class MatchLevels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()
        cls.by_text = {r["text"]: r for r in MATCH["results"] if not r["duplicate_of"]}

    def test_product_names_and_typos_never_usable(self):
        for t in PRODUCT_NAMES | set(TYPO_SUSPECTS):
            self.assertFalse(self.by_text[t]["usable"], t)
        self.assertEqual(self.by_text["Maxitrol"]["tt20"], [])   # not "Manitol"

    def test_usable_rows_exist_and_are_single(self):
        for r in MATCH["results"]:
            if r["usable"]:
                self.assertIn(r["level"], USABLE)
                self.assertEqual(len(r["tt20"]), 1, r["text"])
                self.assertIn(r["tt20"][0]["key"], self.c.names)

    def test_spelling_level_is_rule_equality(self):
        for r in MATCH["results"]:
            if r["level"] == "spelling":
                names = [r["tt20"][0]["ingredient"]] + [p for p in r["tt20"][0]["ingredient"].replace(")", "(").split("(")[1::2]]
                spellings = [r["name"]] + ([e["note"] for e in LIST["entries"] if e["id"] == r["id"] and e["note"]])
                self.assertTrue(any(skeleton(a) == skeleton(b) for a in spellings for b in names), r["text"])

    def test_expected_levels(self):
        expect = {"Hydroxychloroquine": ("spelling", "Hydroxy cloroquin"), "Mannitol": ("spelling", "Manitol"),
                  "Adrenaline": ("spelling", "Epinephrin (adrenalin)"), "Montelukast": ("salt", "Natri montelukast"),
                  "Amoxicillin/ Clavulanic Acid (tiêm)": ("combination", "Amoxicilin + acid clavulanic"),
                  "Magnesi Lactate/ Vitamin B6": ("combination", "Vitamin B6 + magnesi lactat")}
        for text, (level, ingredient) in expect.items():
            self.assertEqual((self.by_text[text]["level"], self.by_text[text]["tt20"][0]["ingredient"]), (level, ingredient), text)
        self.assertEqual(self.by_text["Acetylcysteine"]["level"], "ambiguous")
        self.assertEqual(self.by_text["Febuxostat"]["level"], "none")
        self.assertEqual(self.by_text["Metronidazole/ Chlorhexidine"]["level"], "parts")

    def test_route_hint_checked(self):
        self.assertEqual(sorted(MATCH["summary"]["route_hint_not_in_tt20"]), ["Alpha Chymotrypsine (Tiêm)", "Glyceryl Trinitrate (Uống)"])


class Chat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Corpus()

    def ask(self, q, state=None):
        return self.c.converse(q, state or {})

    def notes(self, r):
        return " ".join(r.get("hospital_notes", []))

    def test_spelling_conversion_is_stated(self):
        r = self.ask("Hydroxychloroquine có được BHYT không")
        self.assertEqual([x["ingredient"] for x in r["results"]], ["Hydroxy cloroquin"])
        self.assertIn("Đã quy đổi cách viết “Hydroxychloroquine” → “Hydroxy cloroquin”", self.notes(r))
        self.assertIn("không xác nhận thuốc đang được cung ứng hay được BHYT thanh toán", self.notes(r))

    def test_presence_shown_for_vietnamese_spelling_without_conversion(self):
        r = self.ask("Aciclovir")
        self.assertIn("“Acyclovir (Tra mắt)”, “Acyclovir (Uống)”", self.notes(r))
        self.assertNotIn("quy đổi", self.notes(r))
        self.assertNotIn("quy đổi", self.notes(self.ask("Paracetamol")))   # already a printed synonym

    def test_absence_from_list_says_nothing(self):
        r = self.ask("Trastuzumab ung thư vú HER2 dương tính")
        self.assertTrue(r["results"])
        self.assertNotIn("hospital_notes", r)

    def test_combination_needs_a_joiner(self):
        r = self.ask("Amoxicillin/ Clavulanic Acid tiêm")
        self.assertEqual([x["ingredient"] for x in r["results"]], ["Amoxicilin + acid clavulanic"])
        self.assertFalse(r.get("unrecognized"))
        r = self.ask("amoxicillin clavulanic acid")
        self.assertFalse(r["results"])        # no joiner: choices, not a conclusion
        self.assertIn("Amoxicilin + acid clavulanic", r["suggestions"])

    def test_combination_beats_its_part(self):
        r = self.ask("Alverine/ Simethicone")
        self.assertEqual([x["ingredient"] for x in r["results"]], ["Alverin citrat + simethicon"])
        r = self.ask("Alverine")
        self.assertEqual([x["ingredient"] for x in r["results"]], ["Alverin citrat"])

    def test_product_name_never_mapped(self):
        for q in ("Gaviscon", "Maxitrol có được BHYT không", "Neopeptin syrup"):
            r = self.ask(q)
            self.assertFalse(r["results"], q)
            self.assertIn("là tên sản phẩm", self.notes(r), q)
            self.assertNotIn("Manitol", json.dumps(r, ensure_ascii=False), q)
        self.assertEqual(len(self.ask("Neopeptin syrup")["hospital_notes"]), 1)   # not also "Neopeptin"

    def test_typo_is_only_a_suggestion(self):
        r = self.ask("Perindorpil")
        self.assertFalse(r["results"])
        self.assertIn("chỉ là gợi ý, cần Dược xác nhận", self.notes(r))

    def test_unlisted_ingredient_keeps_caveat(self):
        r = self.ask("Febuxostat có được BHYT không")
        self.assertEqual(r["status"], "unknown_drug")
        self.assertIn("không tìm thấy tên hoạt chất này trong Phụ lục I/II TT20", self.notes(r))
        self.assertIn("chưa đủ để kết luận thuốc không được BHYT thanh toán", self.notes(r))

    def test_mixed_known_and_unlisted(self):
        r = self.ask("Sildenafil và Metformin")
        self.assertEqual([x["ingredient"] for x in r["results"]], ["Metformin"])
        self.assertIn("Sildenafil", r["unrecognized"])
        self.assertIn("“Sildenafil” có trong danh sách", self.notes(r))

    def test_partial_combination(self):
        r = self.ask("Metronidazole/ Chlorhexidine")
        self.assertIn("TT20 không có dòng phối hợp này", self.notes(r))
        self.assertIn("Chlorhexidine", r["unrecognized"])

    def test_route_mismatch_noted(self):
        r = self.ask("Alpha Chymotrypsine tiêm")
        self.assertIn("danh sách bệnh viện ghi đường “Tiêm”, còn dòng TT20 chỉ có: Uống", self.notes(r))

    def test_private_input_has_no_hospital_notes(self):
        r = self.ask("Nguyễn Văn An 0912345678 dùng Febuxostat")
        self.assertEqual(r["status"], "private_input")
        self.assertNotIn("hospital_notes", r)

    def test_hospital_spelling_in_followup(self):
        r = self.ask("Capecitabine")
        r2 = self.ask("ung thư vú", r["state"])
        self.assertEqual([x["ingredient"] for x in r2["results"]], ["Capecitabin"])


if __name__ == "__main__":
    unittest.main()
