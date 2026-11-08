"""Match the hospital public drug list against the BHYT catalogue (TT20 Appendix I/II).

Every entry keeps its level; nothing is dropped. The chatbot only uses the levels
marked USABLE (deterministic rules, checked by tests); "review" is a suggestion for
Pharmacy and is never applied automatically.

  exact        the printed name is a catalogue name (or resolves to exactly one)
  spelling     equal after fixed spelling rules applied to both sides
               (y→i, ph→f, th→t, chl→cl, doubled letters, final e, spaces/hyphens,
                "Acid X" ↔ "X acid", the synonym printed in brackets)
  salt         equal after removing salt/ester words on both sides
               ("Montelukast" ↔ "Natri montelukast", "Mometasone" ↔ "Mometason furoat")
  combination  a listed combination with the same parts, in any order
  parts        no listed combination; the parts found separately are recorded
  ambiguous    several catalogue names fit
  review       a close name only (typo, product name, class) — needs Pharmacy
  none         nothing found under this name
Writes data/hospital/hospital_tt20_match.json and prints statistics.

    python tools/match_hospital_list.py
"""
import collections
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import SALT_WORDS, Corpus, normalize  # noqa: E402

USABLE = ("exact", "spelling", "salt", "combination")
EXTRA_SALTS = {"furoat", "furoate", "mofetil", "propionat", "dipropionat", "chloride", "sulfate", "sulphate", "acetate", "maleate",
               "phosphate", "citrate", "lactate", "hydrochloride", "muoi", "sulfonat", "sulfonate"}
STEREO = {"dl", "l", "d", "n"}
# Names on the list that are products/brands, not active ingredients (identified by hand).
# They are kept, never mapped to an ingredient without a verified source.
PRODUCT_NAMES = {"Alvesin", "Aminosteril N-Hepa 8%", "Bernevit", "Broncho Vacxom", "Cerebrolysin", "Fleet Enema", "Gaviscon",
                 "Lipofundin MCT/LCT", "Maxitrol", "Moriamin Forte", "Morihepamin", "Neoamyu", "Neopeptin", "Neopeptin syrup", "Neuroaid"}
# Spelling on the list that looks like a typo; the closest name is only a review suggestion.
TYPO_SUSPECTS = {"Perindorpil": "Perindopril", "Mildagliptin/Metformin": "Vildagliptin + Metformin", "Minagliptin": "Linagliptin?",
                 "Mytomycin C": "Mitomycin", "Methycobalamin": "Methylcobalamin (= Mecobalamin)"}
ROUTE_FAMILY = {"tra mắt": ("mắt",), "nhỏ mắt": ("mắt",), "uống": ("uống",), "tiêm": ("tiêm",), "tiêm tủy sống": ("tiêm",),
                "khí dung": ("hô hấp", "khí dung", "phun", "hít", "xịt"), "miếng dán": ("dán",), "bôi": ("ngoài", "bôi")}


def skeleton(text, drop_salts=False):
    words = normalize(re.sub(r"\([^)]*\)", " ", text)).split()
    words = [w for w in words if not w.isdigit() and w not in STEREO]
    if drop_salts:
        kept = [w for w in words if w not in SALT_WORDS and w not in EXTRA_SALTS]
        words = kept or words
    if words and words[0] == "acid":
        words = words[1:] + ["acid"]
    s = "".join(words).replace("y", "i").replace("ph", "f").replace("th", "t").replace("chl", "cl")
    s = re.sub(r"(.)\1+", r"\1", s)
    return re.sub(r"e(?=acid$|$)", "", s)


class Matcher:
    def __init__(self, corpus):
        self.c = corpus
        self.single, self.combo = collections.defaultdict(set), collections.defaultdict(set)
        self.single_salt = collections.defaultdict(set)
        for key, rows in corpus.names.items():
            name = rows[0]["ingredient"]
            if "+" in name:
                parts = re.sub(r"\([^)]*\)", "", name).split("+")
                self.combo[frozenset(skeleton(p, True) for p in parts if p.strip())].add(key)
                continue
            self.single[skeleton(name)].add(key)
            self.single_salt[skeleton(name, True)].add(key)
            for group in re.findall(r"\(([^)]+)\)", name):      # printed synonyms
                for part in group.split(","):
                    if len(normalize(part)) >= 4:
                        self.single[skeleton(part)].add(key)

    def one(self, name, note=None, fuzzy=True):
        n = normalize(name)
        if n in self.c.names and "+" not in self.c.names[n][0]["ingredient"]:
            return "exact", [n]
        hits = self.c.resolve(name)
        if len(hits) == 1 and "+" not in hits[0][0]["ingredient"]:
            return "exact", [normalize(hits[0][0]["ingredient"])]
        for level, table, text in (("spelling", self.single, name), ("spelling", self.single, note), ("salt", self.single_salt, name)):
            if not text:
                continue
            keys = table.get(skeleton(text, level == "salt"), set())
            if len(keys) == 1:
                return level, sorted(keys)
            if len(keys) > 1:
                return "ambiguous", sorted(keys)
        close = difflib.get_close_matches(skeleton(name), list(self.single), n=1, cutoff=.8) if fuzzy else None
        if close:
            return "review", sorted(self.single[close[0]])
        return "none", []

    def many(self, parts):
        keys = self.combo.get(frozenset(skeleton(p, True) for p in parts), set())
        if len(keys) == 1:
            return "combination", sorted(keys), []
        found = [(p,) + self.one(p) for p in parts]
        return "parts", [], [{"component": p, "level": lvl, "tt20": [self.c.names[k][0]["ingredient"] for k in ks]} for p, lvl, ks in found]


def route_ok(hint, routes):
    if not hint:
        return None
    fam = ROUTE_FAMILY.get(hint.lower())
    if not fam:   # "Uống, Tiêm"
        return all(route_ok(h.strip(), routes) for h in hint.split(","))
    return any(f in r.lower() for r in routes for f in fam)


def main():
    c = Corpus()
    # Match against TT20 only, never against the spellings learnt from an earlier run of this tool.
    for alias in c.hospital_aliases:
        c.aliases.pop(alias, None)
    c.hospital_combos = []
    m = Matcher(c)
    doc = json.loads((ROOT / "data/hospital/hospital_drug_list.json").read_text(encoding="utf-8"))
    results = []
    for e in doc["entries"]:
        parts_detail = []
        if e["text"] in PRODUCT_NAMES:
            kind = "product_name"
            # A product name never maps automatically and never by a similar-looking name
            # ("Maxitrol" is not "Manitol"); only a catalogue name that prints it is a suggestion
            # ("Peptid (Cerebrolysin concentrate)").
            level, keys = m.one(e["name"], e.get("note"), fuzzy=False)
            word = " " + normalize(e["name"]) + " "
            printed = sorted(k for k, rows in c.names.items() if word in " " + normalize(rows[0]["ingredient"]) + " ")
            level, keys = ("review", keys or printed) if (keys or printed) else ("none", [])
        elif len(e["components"]) > 1:
            kind = "combination"
            level, keys, parts_detail = m.many(e["components"])
        else:
            kind = "ingredient"
            level, keys = m.one(e["name"], e.get("note"))
        if e["text"] in TYPO_SUSPECTS and level not in USABLE:
            level = "review"
        rows = [r for k in keys for r in c.names[k]]
        routes = sorted({r["route"] for r in rows})
        rec = {"id": e["id"], "text": e["text"], "name": e["name"], "kind": kind, "level": level, "usable": level in USABLE,
               "duplicate_of": e["duplicate_of"], "route_hint": e["route_hint"],
               "tt20": [{"key": k, "ingredient": c.names[k][0]["ingredient"], "stt": c.names[k][0]["stt"],
                         "appendix": c.names[k][0].get("appendix", "I"), "record_ids": [r["record_id"] for r in c.names[k]],
                         "routes": sorted({r["route"] for r in c.names[k]}),
                         "has_conditions": any(r.get("conditions_verbatim") for r in c.names[k])} for k in keys],
               "route_hint_in_tt20": route_ok(e["route_hint"], routes) if keys and level in USABLE else None}
        if parts_detail:
            rec["parts"] = parts_detail
        if e["text"] in TYPO_SUSPECTS:
            rec["typo_suspect"] = TYPO_SUSPECTS[e["text"]]
        results.append(rec)
    uniq = [r for r in results if not r["duplicate_of"]]
    stats = collections.Counter(r["level"] for r in uniq)
    out = {"version": 2, "source_list": "data/hospital/hospital_drug_list.json", "usable_levels": list(USABLE),
           "method": "tools/match_hospital_list.py (quy tắc chính tả cố định; 'review' chỉ là gợi ý cần Dược xem, không tự áp dụng)",
           "summary": {"entries": len(results), "unique": len(uniq), "by_level": dict(stats),
                       "by_kind": dict(collections.Counter(r["kind"] for r in uniq)),
                       "usable": sum(r["usable"] for r in uniq),
                       "with_conditions": sum(r["usable"] and any(t["has_conditions"] for t in r["tt20"]) for r in uniq),
                       "route_hint_not_in_tt20": [r["text"] for r in uniq if r["route_hint_in_tt20"] is False]},
           "results": results}
    (ROOT / "data/hospital/hospital_tt20_match.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False))
    for lvl in ("spelling", "salt", "combination", "ambiguous", "review", "parts", "none"):
        print(f"--- {lvl}:", [r["text"] + (" → " + " | ".join(t["ingredient"] for t in r["tt20"]) if r["tt20"] else "")
                               + (" [" + "; ".join(f'{p["component"]}:{p["level"]}' for p in r.get("parts", [])) + "]" if r.get("parts") else "")
                               for r in uniq if r["level"] == lvl])


if __name__ == "__main__":
    main()
