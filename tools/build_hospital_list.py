"""Hospital public drug list (website "Danh sách thuốc", 24 screenshots in Doc1.docx).

The source document holds only images, so the entries below were transcribed by
reading each screenshot (data/hospital/raw/images/NN.png, document order). Text is
kept exactly as printed, including duplicates and spelling as shown. This script
parses route hints and combination parts and writes data/hospital/hospital_drug_list.json.

    python tools/build_hospital_list.py
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/hospital/raw/Doc1.docx"

# (image number, letter, page, [entries exactly as printed, row by row left→right])
PAGES = [
    (1, "A", 1, ["Abobotulinum Toxin A", "Abobotulinum Toxin A", "Acarbose", "Acenocoumarol", "Acetazolamide", "Acetyl-Dl-Leucine",
                 "Acetylcysteine", "Acid Folic", "Acid Thioctic", "Acid Ursodeoxycholic", "Acyclovir (Tra mắt)", "Acyclovir (Uống)",
                 "Adalimumab", "Adapalene", "Adapalene/ Clindamycin", "Adenosine", "Adrenaline", "Afatinib", "Albendazole", "Albumin",
                 "Alendronate", "Alendronate", "Alfuzosin", "Alimemazine"]),
    (2, "A", 2, ["Allopurinol", "Alpha Chymotrypsine (Tiêm)", "Alpha Chymotrypsine (Uống)", "Alprostadil", "Alteplase", "Alverine",
                 "Alverine/ Simethicone", "Alvesin", "Ambroxol", "Amikacin", "Aminophyllin", "Aminosteril N-Hepa 8%", "Amiodarone",
                 "Amlodipine", "Amoxicillin/ Clavulanic Acid (tiêm)", "Amphotericin B lipid complex", "Anastrozole", "Atorvastatin",
                 "Atosiban", "Azithromycin (Uống)"]),
    (3, "B", 1, ["Bambuterol", "Bernevit", "Betahistin", "Bevacizumab", "Bisoprolol", "Broncho Vacxom", "Budesonide (Khí dung)"]),
    (4, "C", 1, ["Capecitabine", "Carvedilol", "Caspofungin", "Ceftriaxone", "Celecoxib", "Cerebrolysin", "Cilostazol", "Clopidogrel",
                 "Clotrimazole", "Colchicine"]),
    (5, "D", 1, ["Dabigatran", "Dapagliflozin", "Desloratadine", "Diacerein", "Diclofenac (Tiêm)", "Diphenhydramine"]),
    (6, "E", 1, ["Enoxaparin", "Entecavir", "Ertapenem", "Esomeprazole", "Etoricoxib", "Ezetimibe"]),
    (7, "F", 1, ["Febuxostat", "Felodipine", "Fenofibrate", "Fentanyl (Miếng dán)", "Fexofenadin", "Fleet Enema", "Fluconazole", "Fluconazole"]),
    (8, "G", 1, ["Gabapentin", "Ganciclovir", "Gaviscon", "Gliclazide", "Glyceryl Trinitrate (Uống)", "Goserelin"]),
    (9, "H", 1, ["Haloperidol", "Hydroxychloroquine", "Hyoscin-N-Butylbromide"]),
    (10, "I", 1, ["Ibuprofen", "Indapamide", "Irbesartan", "Ivabradine"]),
    (11, "K", 1, ["Ketorolac (Tiêm)"]),
    (12, "L", 1, ["Lactulose", "Levetiracetam", "Levodopa/Benserazide", "Levothyroxine", "Linezolid", "Lipofundin MCT/LCT", "Lisinopril",
                  "Loperamide", "Loratadine", "Losartan"]),
    (13, "M", 1, ["Magnesi Lactate/ Vitamin B6", "Magnesi Sulfate", "Magnesi Sulfate/ Saccharomyces Cerevisiae", "Mannitol", "Maxitrol",
                  "Mebendazole", "Mebeverine", "Meloxicam", "Menotrophin", "Mephenesin", "Mepivacaine", "Mercaptopurine", "Meropenem",
                  "Mesalazine", "Mesna", "Metformin", "Methotrexate", "Methycobalamin", "Methyldopa", "Methylergometrine Maleate",
                  "Methylprednisolone", "Metoclopramide", "Metoprolol", "Metronidazole (Tiêm)"]),
    (14, "M", 2, ["Metronidazole/ Chlorhexidine", "Metronidazole/ Spiramycin", "Midazolam", "Mifepristone", "Mildagliptin/Metformin",
                  "Milrinone", "Minagliptin", "Minoxidil", "Mirtazapine", "Misoprostol", "Mometasone (bôi)", "Montelukast", "Moriamin Forte",
                  "Morihepamin", "Morphine", "Morphine Sulfate (Tiêm Tủy Sống)", "Moxifloxacin (Nhỏ Mắt)", "Moxifloxacin (Uống, Tiêm)",
                  "Moxifloxacin/ Dexamethasone", "Mucopolysaccharide Polysulfate", "Mupirocin", "Mycophenolate Mofetil", "Mytomycin C"]),
    (15, "N", 1, ["Naproxen", "Natri chloride 0,45%", "Natri chloride 10%", "Natri Hyaluronate", "Natri hypochloride",
                  "Natri polystyrene sulfonate", "Natri sulphacetamide", "Neoamyu", "Neopeptin", "Neopeptin syrup", "Nepafenac",
                  "Nepidermin (rhEGF)", "Neuroaid"]),
    (16, "O", 1, ["Ondansetron", "Oseltamivir", "Oxycodone"]),
    (17, "P", 1, ["Pantoprazole", "Paracetamol", "Perindorpil", "Piracetam (Tiêm)", "Pregabalin", "Protamine"]),
    (18, "R", 1, ["Rabeprazole", "Racecadotril", "Rivaroxaban", "Rosuvastatin"]),
    (19, "S", 1, ["Sildenafil", "Sitagliptin"]),
    (20, "T", 1, ["Ticagrelor", "Tiotropium"]),
    (21, "V", 1, ["Valsartan", "Vitamin K1 (Phytonadione)", "Vitamin K2 (Menatetrenone)"]),
    (22, "W", 1, ["Warfarin"]),
    (23, "X", 1, ["Xanh methylen", "Xylometazoline"]),
    (24, "Z", 1, ["Zoledronic Acid", "Zolpidem", "Zopiclon", "Zopiclon"]),
]
ROUTE_WORDS = {"tra mắt", "uống", "tiêm", "khí dung", "miếng dán", "bôi", "nhỏ mắt", "tiêm tủy sống", "uống, tiêm"}


def parse(text):
    name, route, note = text, None, None
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", text)
    if m:
        inner = m.group(2).strip()
        if inner.lower() in ROUTE_WORDS:
            name, route = m.group(1).strip(), inner
        else:
            note = inner   # synonym or form, e.g. "(Phytonadione)", "(rhEGF)"
    parts = [p.strip() for p in re.split(r"\s*/\s*", name) if p.strip()]
    return name, route, note, parts


def main():
    entries, seen = [], {}
    for image, letter, page, items in PAGES:
        for pos, text in enumerate(items, 1):
            name, route, note, parts = parse(text)
            key = text.lower()
            entry = {"id": f"HL-{image:02d}-{pos:02d}", "text": text, "name": name, "route_hint": route, "note": note,
                     "components": parts if len(parts) > 1 else [name], "letter": letter, "page": page,
                     "image": f"data/hospital/raw/images/{image:02d}.png", "position": pos,
                     "duplicate_of": seen.get(key)}
            seen.setdefault(key, entry["id"])
            entries.append(entry)
    doc = {"version": 1,
           "source": "Website bệnh viện, mục \"Danh sách thuốc\" (24 ảnh chụp màn hình trong Doc1.docx do người dùng cung cấp, 08/11/2026)",
           "source_file_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest() if RAW.exists() else None,
           "transcription": "Chép tay từ ảnh (tài liệu chỉ có ảnh, không có chữ). Giữ nguyên chính tả và các dòng trùng.",
           "limitations": ["Danh sách tra cứu thông tin thuốc trên website, không phải danh mục trúng thầu: không có biệt dược, hàm lượng, số đăng ký.",
                           "24 ảnh là toàn bộ danh sách công khai; website không có thuốc nào bắt đầu bằng J, Q, U, Y (người cung cấp xác nhận ngày 11/11/2026).",
                           "Không có tên trong danh sách này không có nghĩa bệnh viện không dùng thuốc đó."],
           "entries": entries}
    out = ROOT / "data/hospital/hospital_drug_list.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(entries)} entries, {len({e['text'].lower() for e in entries})} unique texts -> {out}")


if __name__ == "__main__":
    main()
