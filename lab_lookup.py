"""Source-bound laboratory lookup; no model calls, no patient records.

"Xét nghiệm này, cho bệnh này, với mục đích này, ở thời điểm này, BHYT có thanh toán không?"
Every laboratory row with its own payment condition (TT39/2024 appendix and the rows of
17/VBHN-BYT that TT39 did not amend) is quoted verbatim. Selected rules are compared
with the facts of a case, all others return the source text and say so:
  hba1c  purpose, confirmed diabetes, interval since the last test
  gene   disease within the row's scope + "chẩn đoán đột biến gen trong điều trị"
  scope  disease within the row's list (the remaining conditions stay with the reader)
  CA 125  indication within the shared tumor-marker row, only for this named assay
Routes service coverage separately from drug-marker conditions. Clinical facts are
per-turn/per-service and carried only in the engine's signed browser state.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import unicodedata
from pathlib import Path
from lab_guidance import GENERAL, LabGuidance


def norm(value):
    text = unicodedata.normalize('NFD', str(value).lower().replace('đ', 'd'))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in text if not unicodedata.combining(c))).split())


def has(q, pattern):
    return bool(re.search(pattern, q))


def local_today():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).date()


# ---- How a fact is read ----------------------------------------------------------------
# A keyword ("insulin", "lần đầu", "ung thư vú", "điều trị") is looked at inside its own clause:
#   'no'       a negation governs it (only filler words in between, or "… đã ngừng" after it)
#   'unknown'  doubt, plan, question, double negation, or a negation that may or may not govern it
#   'yes'      otherwise
# Anything but a plain 'yes'/'no' is asked back, never guessed.
CLAUSE_SPLIT = re.compile(r'[,;!?\n]+|\.(?=\s|$)|\s+(?:nhưng|nhung|mà|tuy nhiên|tuy nhien)\s+')
STOPPED = re.compile(r'\b(?:dừng|ngừng|ngưng|hết|thôi|bỏ|cắt|nghỉ)\b')      # with diacritics: "dừng" is not "dùng"
NEGATORS = ('khong', 'chua', 'chang', 'ko', 'ngung', 'loaitru', 'stopx')
# Doubt, plan or an earlier state: the fact is not affirmed now.
HEDGE = (r'\b(?:du kien|du dinh|co the|se|sap|can nhac|chua ro|khong ro|chua biet|khong biet|chua chac|khong chac|co le|hinh nhu|dang cho|cho ket qua|'
         r'khong nho|khong thay|khong ghi|chua thay|chua ghi|truoc day|truoc kia|da tung|chac|gia dinh|nguoi nha|nghi ngo|nghi)\b')
SUSPECT = HEDGE[:-3] + r'|nguy co|tam soat|sang loc)\b'
SUSPICION = ('nghi ngo', 'nghi', 'nguy co', 'tam soat', 'sang loc')
# Words of doubt that forbid a "khớp" conclusion wherever they stand in the message.
DOUBT = r'\b(?:co the|chua ro|khong ro|chua chac|khong chac|co le|hinh nhu|nghi ngo|chua xac dinh|chua loaitru|khong loaitru|chua biet|khong biet|dang cho|cho ket qua|chua du|khong du)\b'


def clause_list(message):
    """Normalised clauses. Names that contain "không" ("không tế bào nhỏ", "không phụ thuộc
    insulin", "không Hodgkin") and "loại trừ" become single tokens, so that the "không" inside
    a name is never read as a negation of what follows."""
    out = []
    for raw in CLAUSE_SPLIT.split(unicodedata.normalize('NFC', str(message).lower())):
        c = norm(STOPPED.sub(' stopx ', raw))
        c = re.sub(r'\bkhong (?:phai )?te bao nho\b', 'ktbn', c)
        c = re.sub(r'\bkhong phu thuoc insulin\b', 'type2x', c)
        c = re.sub(r'\bkhong hodgkin\b', 'nonhodgkin', c)
        c = re.sub(r'\bloai tru\b', 'loaitru', c)
        if c:
            out.append(c)
    return out


def governed(clause, start, end, fillers, hedge=HEDGE, stoppable=False):
    """(state, word) for the keyword at clause[start:end], read against everything before it
    in the clause. `stoppable`: the keyword is a treatment, so "… đã ngừng" after it negates
    it (never said of a disease)."""
    before = clause[:start].split()
    after = clause[end:].split()
    if stoppable and re.match(r'(?:(?:thi|la|nay|hien|tai|da|roi|nua|cung|tam|moi|vua|dang) )*(?:stopx|ngung)\b', ' '.join(after[:6])):
        return 'no', 'stopx'                                  # "trước đây dùng insulin nay đã ngưng"
    m = re.search(hedge, ' '.join(before))
    if m:
        return 'unknown', m.group(0)
    if stoppable and re.match(r'(?:\w+ ){0,3}(?:nam truoc|nam ngoai|thang truoc|tuan truoc|truoc day|truoc kia|luc truoc|hoi truoc|dot truoc|thai ky truoc|lan mang thai truoc|truoc khi|truoc do)\b', ' '.join(after)):
        return 'unknown', 'past'                              # "dùng insulin trong năm trước": then, not now
    if re.fullmatch(r'(?:(?:thi|la|hay) )*(?:khong|chua)(?: (?:a|nhi|vay|nua))?', ' '.join(after)):
        return 'unknown', 'question'                          # "… dùng insulin không?"
    neg = [i for i, w in enumerate(before) if w in NEGATORS]
    if not neg:
        # "từng dùng insulin", "đã điều trị xong": said of the past, not of now.
        return ('unknown', 'past') if 'tung' in before or re.match(r'(?:\w+ ){0,2}xong\b', ' '.join(after)) else ('yes', None)
    if len(neg) > 1:
        return 'unknown', 'double'                            # "chưa loại trừ", "không phải không"
    between = before[neg[-1] + 1:]
    if all(w in fillers for w in between):
        return 'no', before[neg[-1]]                          # however long: "chưa có đủ bằng chứng để chẩn đoán xác định …"
    if between[-1] in ('dang', 'da'):
        return 'yes', None                                    # "… không hút thuốc đang điều trị": the negation ended earlier
    return 'unknown', 'far'                                   # a negation earlier in the clause that may or may not reach it


def mentions(clauses, pattern, fillers, hedge=HEDGE, stoppable=False):
    """[(state, word, clause, match)] for every occurrence of the keyword."""
    out = []
    for c in clauses:
        for m in re.finditer(r'\b(?:' + pattern + r')\b', c):
            out.append(governed(c, m.start(), m.end(), fillers, hedge, stoppable) + (c, m))
    return out


def verdict(found):
    """One answer for a fact named several times: any doubt or contradiction is 'unknown'."""
    states = {x[0] for x in found}
    return None if not states else 'unknown' if 'unknown' in states or len(states) > 1 else states.pop()


# Every word a question may contain without changing its reading. A conclusion ("khớp" /
# "không khớp") is given directly only when the question consists of these words alone; any
# other word ("từ chối", "mẹ", "hủy", "hội chẩn" …) means the reading is shown and confirmed
# first. Kept with diacritics, so that "hội" (hội chẩn) is not "hỏi".
ACCOUNTED = set("""
xét nghiệm xn định lượng dịch vụ chỉ định làm lại muốn tôi cần cho bệnh nhân bn người trường hợp ca này hiện tại đang đã được có không
bhyt bảo hiểm y tế quỹ thanh toán chi trả điều kiện gì thế nào là thì và với để nhằm trong của ở ạ nhé xin hỏi bác sĩ cả hai đều
thuốc mới vừa rồi nữa thêm về việc một các những bị mắc nên cũng vậy sao còn vì do mà nhưng chứ loại đến tới
đái tháo đường đtđ tiểu thai kỳ insulin dùng sử dụng tiêm trị bằng theo dõi đánh giá kết quả đáp ứng hiệu kiểm soát huyết xác chọn lập chỉnh thay đổi phác đồ
tầm sàng lọc chẩn đoán ban đầu đột biến gen gene tìm phát hiện thực đo chưa chẳng ko ngừng ngưng dừng hết thôi bỏ trừ phải rõ biết chắc nhớ dự kiến
thể sẽ sắp cân nhắc lẽ chờ thấy ghi đây nghi ngờ nguy cơ tiền mục đích type typ tuýp týp tuyp giai đoạn tái tiến triển
ung thư phổi tế bào nhỏ nsclc sclc utp vú dạ dày đại trực tràng tuyến giáp cổ tử cung vòm mũi họng thanh quản hạ khoang miệng xoang mặt âm hộ dương vật da
""".split())
ACCOUNTED_PLAIN = {norm(w) for w in ACCOUNTED}
# Time words are accounted for only as part of one of these expressions ("lần trước cách 35
# ngày", "hôm nay", "ngày 01/08/2026"). Left on their own they qualify a fact — "dùng insulin
# trong năm trước" — and the reading must be confirmed. "hoặc", "hay", "nếu", "khi", "sau",
# "trước" are never accounted for: they make a statement conditional or a choice.
TIME_EXPRESSIONS = re.compile(
    r'\blan truoc(?: (?:lam|thuc hien|xet nghiem|do|la|vao|luc))*(?: ngay)?(?= zzdate| cach|$)|\blan (?:truoc|nay)\b|\blan dau(?: tien)?\b|\blan thu (?:\d+|hai|ba|tu)\b'
    r'|\b(?:lan )?gan nhat\b|\bhom nay\b|\bngay mai\b|\bhien nay\b|\bnay\b|\b(?:ngay )?zzdate\b|\btruoc (?:day|kia)\b|\bchua tung\b|\blan nao\b'
    r'|\b(?:cach(?: day)? )?(?:(?:khoang|gan|hon|chua den|chua toi|khong qua|it nhat|toi da|duoi|tren) )?\d+ (?:ngay|tuan|thang)(?: truoc| roi)?\b')


def unread_words(message, aliases=()):
    """Words of the question that nothing in this module accounts for, as typed."""
    text = unicodedata.normalize('NFC', str(message).lower())
    text = re.sub(r'\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}', ' zzdate ', text)
    tokens = re.findall(r'[^\W_]+', text)
    plain, starts, at = [], [], 0
    for w in tokens:
        n = norm(w) or w
        starts.append(at); plain.append(n); at += len(n) + 1
    joined = ' '.join(plain)
    used = [False] * len(tokens)
    for m in TIME_EXPRESSIONS.finditer(joined):
        for i, a in enumerate(starts):
            if m.start() <= a < m.end():
                used[i] = True
    known = {w for a in aliases for w in a.split()}
    out = []
    for w, n, consumed in zip(tokens, plain, used):
        if consumed or w.isdigit() or len(w) == 1 or re.fullmatch(r'[ivx]+', w) or n in known or w == 'zzdate':
            continue
        if w in ACCOUNTED or (w.isascii() and w in ACCOUNTED_PLAIN):
            continue
        out.append(w)
    return list(dict.fromkeys(out))


NEW_CASE = r'\b(?:(?:benh nhan|nguoi benh|bn|ca|truong hop|nguoi) (?:khac|thu (?:hai|ba|tu|\d+)|tiep theo|ke tiep)|(?:ca|truong hop) moi|mot (?:benh nhan|ca|truong hop|nguoi) (?:khac|moi))\b'
# A confirmation is the whole message and nothing else. "Đúng nhưng bệnh nhân không dùng
# insulin" corrects a fact and "Ok, hỏi Trastuzumab …" changes the subject: both are read.
CONFIRMATION = r'(?:dung|dung roi|dung vay|chinh xac|xac nhan|ok|dong y)(?: (?:roi|vay|a|nhe))?(?: doi chieu(?: theo(?: cac)? du kien(?: nay| tren)?)?)?'

F_USE = {'den', 'toi', 'co', 'con', 'can', 'phai', 'duoc', 'chi', 'dinh', 'dung', 'su', 'tiem', 'dieu', 'tri', 'bang', 'voi', 'thuoc', 'them', 'nua', 'tung', 'dang'}
F_IS = {'phai', 'la', 'bi', 'mac', 'co', 'cho', 'benh', 'nhan', 'nguoi', 'truong', 'hop', 'duoc', 'chan', 'doan', 'xac', 'dinh', 'ro', 'ket', 'luan',
        'khang', 'tung', 'tien', 'su', 'du', 'tieu', 'chuan', 'ly', 'bang', 'chung', 'de', 'can', 'cu', 'co so', 'so', 'ghi', 'nhan', 'phat', 'hien', 'thay',
        'dau', 'hieu', 'cua', 've', 'mot', 'nao', 'hinh', 'anh', 'giai', 'phau', 'mo', 'hoc'}
F_GESTATIONAL = F_IS | {'dai', 'thao', 'duong', 'dtd', 'tieu'}
F_PURPOSE = {'phai', 'la', 'de', 'nham', 'muc', 'dich', 'dung', 'lam', 'trong', 'qua', 'trinh', 'dang', 'duoc', 'co', 'cho', 'viec'}

# Diseases named in a question; the more specific pattern comes first.
DISEASES = [
    ('nsclc', 'ung thư phổi không tế bào nhỏ', r'nsclc|ung thu phoi ktbn|utp ktbn'),      # after clause_list()
    ('sclc', 'ung thư phổi tế bào nhỏ', r'sclc|ung thu phoi te bao nho'),
    ('lung_unspecified', 'ung thư phổi (chưa nêu thể bệnh)', r'ung thu phoi'),
    ('breast', 'ung thư vú', r'ung thu vu'),
    ('gastric', 'ung thư dạ dày', r'ung thu da day'),
    ('colorectal', 'ung thư đại trực tràng', r'ung thu (?:dai truc trang|dai trang|truc trang)'),
    ('thyroid', 'ung thư tuyến giáp', r'ung thu tuyen giap'),
    ('cervical', 'ung thư cổ tử cung', r'ung thu co tu cung'),
    ('nasopharynx', 'ung thư vòm mũi họng', r'ung thu vom(?: mui hong| hong)?'),
    ('larynx', 'ung thư thanh quản - hạ họng', r'ung thu (?:thanh quan|ha hong)'),
    ('oral', 'ung thư khoang miệng', r'ung thu (?:khoang )?mieng'),
    ('sinus', 'ung thư xoang mặt', r'ung thu xoang'),
    ('esophagus', 'ung thư thực quản', r'ung thu thuc quan'),
    ('vulva', 'ung thư âm hộ', r'ung thu am ho'),
    ('penis', 'ung thư dương vật', r'ung thu duong vat'),
    ('skin', 'ung thư da', r'ung thu da(?! day)'),
    ('other', 'bệnh ung thư khác', r'ung thu (?:gan|tuy|buong trung|tuyen tien liet|than|bang quang|nao|xuong|mau|hach|tinh hoan|tu cung)|u lympho|lo xe mi|bach cau cap|bach cau man'),
]
DISEASE_LABEL = {k: label for k, label, _ in DISEASES}
DIABETES = r'(?:dai thao duong|dtd|tieu duong)'
# Other tests a doctor may name; never answered with another service's rule.
COMMON_TESTS = (r'\b(?:troponin|creatinin|ure mau|glucose|duong huyet|duong mau|men gan|ast|alt|got|gpt|ggt|bilirubin|cholesterol|triglycerid|mo mau|lipid mau|'
                r'tsh|ft3|ft4|d dimer|psa|afp|ferritin|inr|dong mau|dien giai do|khi mau|nuoc tieu|hbsag|anti hcv|anti hbs|cay mau|vitamin d|acid uric|'
                r'sinh hoa|huyet hoc|vi sinh|nhom mau|mau lang|ngs)\b')
OTHER_SERVICES = (r'\b(?:sieu am|x quang|xquang|cat lop vi tinh|ct scanner|ct scan|chup ct|mri|cong huong tu|pet ct|pet|noi soi|dien tim|dien tam do|dien nao|'
                  r'do loang xuong|loc mau|chup mach|phuc hoi chuc nang|cham cuu)\b')
COVERAGE = r'\b(?:bhyt|bao hiem|thanh toan|chi tra|dieu kien|co duoc|duoc khong)\b'
YES_NO = ('co', 'dung', 'dung roi', 'khong', 'chua', 'chua ro', 'khong ro')

CA125 = r'\bca ?125\b'
OTHER_MARKER = r'\b(?:cea|ca ?15 ?3|ca ?19 ?9|ca ?72 ?4|he4|roma|afp)\b'
CUP = r'(?:ung thu )?di can (?:khong ro|chua ro|chua xac dinh(?: duoc)?) (?:vi tri |vi tri cua )?(?:u |o |nguon )?nguyen phat'
CA125_PURPOSES = {
    'screening': ('tầm soát', r'tam soat|sang loc'),
    'post_treatment': ('giám sát sau điều trị', r'theo doi sau (?:khi )?(?:ket thuc |hoan tat )?(?:dieu tri|hoa tri|xa tri)|(?:tim|phat hien|theo doi) tai phat'),
    'monitoring': ('theo dõi điều trị', r'theo doi (?:dap ung |ket qua |qua trinh )?dieu tri|danh gia (?:dap ung|ket qua) dieu tri'),
    'diagnosis': ('chẩn đoán', r'chan doan'),
}
CA125_SITES = {'ovarian': 'ung thư buồng trứng', 'cup': 'ung thư di căn chưa rõ u nguyên phát',
               'other': 'vị trí ung thư khác đã nêu'}
CA125_INTERVAL = 'Dòng này không nêu khoảng cách tối thiểu giữa hai lần định lượng CA 125.'


def extract_ca125(message, facts):
    # Mask “không rõ” only inside the name of this indication, not genuine uncertainty.
    clauses = [re.sub(r'\b' + CUP + r'\b', ' cupmarker ', c).strip() for c in clause_list(message)]
    purpose = []
    for key, (_, pattern) in CA125_PURPOSES.items():
        # A prior diagnosis is a fact about the patient, not the purpose of this order.
        parts = [re.sub(r'\bda (?:duoc )?chan doan\b', 'da mac', c) for c in clauses] if key == 'diagnosis' else clauses
        status = verdict(mentions(parts, pattern, F_PURPOSE))
        if status:
            purpose.append((key, status))
    if purpose:
        positive = [key for key, status in purpose if status == 'yes']
        facts['marker_purpose'] = positive[0] if len(positive) == 1 and all(s != 'unknown' for _, s in purpose) else 'unknown'
    sites = []
    for key, pattern in [('ovarian', r'ung thu buong trung|ut buong trung'), ('cup', 'cupmarker')]:
        status = verdict(mentions(clauses, pattern, F_IS))
        if status:
            sites.append((key, status))
    other_clauses = [c.replace('ung thu buong trung', '') for c in clauses]
    other_sites = [mention for _, _, pattern in DISEASES for mention in mentions(other_clauses, pattern, F_IS)]
    if other_sites:
        sites.append(('other', verdict(other_sites)))
    if sites:
        facts['marker_site'] = sites[0][0] if len(sites) == 1 and sites[0][1] == 'yes' else 'unknown'
    q = norm(message)
    if has(q, r'\b(?:da ket thuc|da hoan tat|ket thuc dot) dieu tri\b') and facts.get('marker_purpose') == 'monitoring':
        facts['marker_purpose'] = 'post_treatment'
    if has(q, r'\b(?:khong|chua) (?:phai |lam |chi dinh |dinh luong |xet nghiem )*ca ?125\b'):
        facts['assay_unclear'] = True
    facts['interval'] = has(q, r'\b(?:tan suat|bao lau|bao nhieu (?:ngay|lan)|lan (?:truoc|hai|thu|2)|lam lai|lap lai|dinh ky|\d+ (?:ngay|tuan|thang))\b')
    facts['price'] = has(q, r'\b(?:ty le|phan tram|muc huong|muc gia|bao nhieu tien|gia bao nhieu|don gia)\b') or '%' in message
    if has(q, r'\b(?:pcr|ngs|hoa mo mien dich|dich (?:mang|bung)|nuoc tieu)\b') or has(q, OTHER_SERVICES):
        facts['method_query'] = True


def evaluate_ca125(facts, result):
    purpose, site = facts.get('marker_purpose'), facts.get('marker_site')
    indication = ('CA 125 có hai nhánh trong dòng nguồn: chẩn đoán ung thư di căn chưa rõ u nguyên phát '
                  '(điểm a), hoặc chẩn đoán, theo dõi điều trị ung thư buồng trứng (điểm b).')
    if facts.get('assay_unclear'):
        return result('needs_info', 'Bác sĩ đang hỏi BHYT cho chính xét nghiệm CA 125 hay một dịch vụ khác? Vui lòng ghi rõ tên dịch vụ cần tra.', 'marker_context')
    if facts.get('method_query'):
        return result('needs_review', 'Cần đối chiếu tên kỹ thuật và bệnh phẩm trên phiếu với dịch vụ chỉ điểm khối u trong nguồn.')
    if purpose == 'screening':
        return result('source_condition_not_met', 'Tầm soát không thuộc hai chỉ định CA 125 nêu ở điểm a và b. '
                      'Nếu làm theo chương trình sàng lọc, cần kiểm tra căn cứ riêng của chương trình.'
                      + (' ' + CA125_INTERVAL if facts.get('interval') else ''), highlight=[0, 1, 2])
    if site == 'other' and purpose in ('diagnosis', 'monitoring'):
        return result('source_condition_not_met', 'Vị trí ung thư vừa nêu không khớp nhánh buồng trứng của CA 125. '
                      'Điểm a áp dụng riêng cho chẩn đoán ung thư di căn chưa rõ u nguyên phát. '
                      'Chưa đủ căn cứ xác nhận chi trả cho ca này.', highlight=[0, 1, 2])
    matched = False
    if site == 'ovarian' and purpose in ('diagnosis', 'monitoring'):
        text = 'Chỉ định CA 125 để ' + CA125_PURPOSES[purpose][0] + ' ung thư buồng trứng phù hợp điểm b của dòng nguồn.'
        mark = [1, 2]
        matched = True
    elif site == 'cup' and purpose == 'diagnosis':
        text = 'Chỉ định CA 125 để chẩn đoán ung thư di căn chưa rõ u nguyên phát phù hợp điểm a của dòng nguồn.'
        mark = [0]
        matched = True
    else:
        text, mark = indication, [0, 1, 2]
    if facts.get('interval') or facts.get('price') or purpose == 'post_treatment':
        limits = []
        if purpose == 'post_treatment':
            limits.append('Cần làm rõ mục đích giám sát sau điều trị. Điểm c về tái phát sau điều trị là của CA 19-9, không áp sang CA 125.')
        if facts.get('interval'):
            limits.append(CA125_INTERVAL)
        if facts.get('price'):
            limits.append('Cột giá dẫn tới giá dịch vụ xét nghiệm bằng kỹ thuật hóa sinh, không ấn định tỷ lệ hưởng cá nhân.')
        return result('needs_review', ' '.join([indication, *limits]), highlight=mark)
    if matched:
        return result('source_conditions_match', text + ' Cần đối chiếu các điều kiện chung trước khi xác nhận chi trả.', highlight=mark)
    if not purpose:
        return result('needs_info', text + ' Bác sĩ chỉ định để chẩn đoán, theo dõi điều trị hay tầm soát?', 'marker_purpose', mark)
    return result('needs_info', text + ' Bác sĩ cho biết bệnh cảnh và mục đích cụ thể của lần chỉ định này?', 'marker_context', mark)


class LabLookup:
    def __init__(self, data_dir):
        self.data = Path(data_dir)
        self.guidance = LabGuidance(self.data)
        path = self.data / 'lab_services.json'
        self.bundle = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'services': [], 'source': {}}
        self.services = {s['id']: s for s in self.bundle['services']}
        self.source = self.bundle['source']
        self.documents = self.bundle.get('documents') or ({'tt39': self.source} if self.source else {})
        self._hashes = {}
        attestation = self.data / 'review_attestation.json'
        self.attestation = json.loads(attestation.read_text(encoding='utf-8')) if attestation.exists() else None
        # What is said about the rows read from the scan: reviewed (as attested) or still waiting.
        self.scan_status = self.attestation['statement'] if self.attestation else 'Chưa được thẩm định; hãy đối chiếu ảnh trang trước khi dùng.'
        # Names as printed are usable aliases too.
        self.alias_index = []
        for s in self.services.values():
            strong = {norm(a) for a in s.get('aliases', [])} | {norm(s['name']), norm(s.get('official_name', s['name']))}
            for a in strong:
                if a:
                    self.alias_index.append((a, s['id'], 'strong'))
            for kind in ('explicit', 'loose'):
                for a in s.get(kind + '_aliases', []):
                    if norm(a) not in strong:
                        self.alias_index.append((norm(a), s['id'], kind))

    # ---- sources ------------------------------------------------------------------
    def doc(self, service):
        return self.documents.get(service.get('doc', 'tt39'), self.source)

    def _hash_ok(self, url, expected):
        path = self.data / url.removeprefix('/')
        if not path.is_file():
            return False
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        if key not in self._hashes:
            self._hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        return self._hashes[key] == expected

    def integrity_ok(self, service=None):
        """The PDF and row images of one service (or of all) are the files that were checked."""
        if not self.source:
            return False
        rows = [s for s in self.services.values() if service in (None, s['id'])]
        files = {(self.doc(s)['local_url'], self.doc(s)['sha256']) for s in rows}
        if service is None:
            files.add((self.source['local_url'], self.source['sha256']))
        for s in rows:
            for image in s.get('images') or [{'url': s['image_url'], 'sha256': s['image_sha256']}]:
                files.add((image['url'], image['sha256']))
        return all(self._hash_ok(url, expected) for url, expected in files)

    def file_ok(self, url):
        """One row/page image is the file that was checked (other files do not matter)."""
        for s in self.services.values():
            for image in s.get('images') or [{'url': s['image_url'], 'sha256': s['image_sha256']}]:
                if image['url'] == url:
                    return self._hash_ok(url, image['sha256'])
        return False

    def served_files(self):
        """Local files the server may send: source PDFs and row/page images."""
        files = {}
        for d in list(self.documents.values()) + self.source.get('related_documents', []):
            if d.get('local_url'):
                files[d['local_url']] = 'application/pdf'
        for s in self.services.values():
            for image in s.get('images') or [{'url': s['image_url']}]:
                files[image['url']] = 'image/png'
        return files

    def metadata(self):
        rows = list(self.services.values())
        return {**self.source, 'service_count': len(rows), 'integrity_ok': self.integrity_ok(),
                'text_layer_count': sum(s.get('transcription', 'text_layer') == 'text_layer' for s in rows),
                'scan_read_count': sum(s.get('transcription') == 'scan_read' for s in rows),
                'documents': [{k: d.get(k) for k in ('document_id', 'title', 'local_url', 'official_url', 'review_status', 'effective_from', 'checked_as_of')}
                              for d in self.documents.values()],
                'services': [{'id': s['id'], 'name': s['name'], 'viewer_url': s['viewer_url'], 'transcription': s.get('transcription', 'text_layer'),
                              'automatic': bool(s.get('rule'))} for s in rows]}

    # ---- routing ------------------------------------------------------------------
    def match_services(self, q, explicit):
        """Services named in the question. A name inside a longer matched name of another
        service is dropped ("Pro-BNP" is not also "BNP")."""
        found = []
        for alias, sid, kind in self.alias_index:
            if kind == 'explicit' and not explicit:
                continue
            for m in re.finditer(r'\b' + re.escape(alias) + r'\b', q):
                found.append((m.start(), m.end(), sid, kind))
        kept = [x for x in found if not any(y[2] != x[2] and y[0] <= x[0] and x[1] <= y[1] and (y[1] - y[0]) > (x[1] - x[0]) for y in found)]
        ids = list(dict.fromkeys(x[2] for x in sorted(kept)))
        for sid in list(ids):   # the general sequencing row yields to the specific sequencing rows
            if any(o in ids for o in self.services[sid].get('yields_to', [])) or (sid == 'gene_sequencing' and any(
                    i != sid and 'giai trinh tu' in norm(self.services[i]['name']) for i in ids)):
                ids.remove(sid)
        loose = {sid for sid in ids if all(x[3] == 'loose' for x in kept if x[2] == sid)}
        # "HLA bằng PCR-SSP": the row named by its own method wins over a row that only shares
        # the general word.
        strong = [sid for sid in ids if sid not in loose]
        for sid in sorted(loose):
            words = {q[a:b] for a, b, i, _ in kept if i == sid}
            if any(words & {alias for alias, other, _ in self.alias_index if other == o} for o in strong):
                ids.remove(sid); loose.discard(sid)
        spans = {sid: [(x[0], x[1]) for x in kept if x[2] == sid] for sid in ids}
        return ids, loose, spans

    def route(self, message, state, drug_hits, drug_words=()):
        q = norm(message)
        scc_test = not drug_hits and has(q, r'^scc(?:$| (?:co (?:duoc|bhyt)|duoc|bhyt|thanh toan|chi tra)\b)|\b(?:cea|psa|ca ?125)\b.*\bscc\b|\bscc\b.*\b(?:cea|psa|ca ?125)\b')
        matches = self.match_services(q, scc_test or has(q, r'\b(?:xet nghiem|dinh luong|dich vu|xn)\b'))
        named = matches[0]
        row_route = self._row_route(message, state, drug_hits, drug_words, matches)
        parts = re.split(r'[,;/+]', message)
        list_items = [norm(part) for part in parts] if len(parts) > 1 else []
        guide = self.guidance.match(q, state, row_route, drug_hits, named, list_items)
        if guide:
            route = dict(row_route or {}, guide=guide)
            route.setdefault('ids', [])
            # A prior pending service must not consume a new topic.
            route['ids'] = [sid for sid in route['ids'] if sid in named]
            if guide['topic'] == 'payment_topic':
                route['ids'] = guide['group']['rows']
            elif guide['topic'] == 'markers':
                route['ids'] = ['tumor_markers']
            elif guide['topic'] == 'molecular':
                route['ids'] = ['egfr', 'kras', 'braf', 'her2']
            elif guide['topic'] == 'panel':
                route['ids'] = []
            both = drug_hits and has(q, r'\b(?:ca thuoc|va thuoc|va xet nghiem)\b')
            route['kind'] = 'mixed' if both else 'lab'
            return route
        if GENERAL.fullmatch(q) and state.get('lab', {}).get('id') in self.services and not named:
            return {'ids': [state['lab']['id']], 'kind': 'lab'}
        return row_route

    def _row_route(self, message, state, drug_hits, drug_words, matches):
        """None means leave the established drug chat path entirely unchanged."""
        q = norm(message)
        lab_state = state.get('lab', {})
        renal = has(q, r'\b(?:do loc cau than|muc loc cau than|creatinin|ckd epi|ml phut|ml min|suy than|benh than man|chuc nang than)\b')
        explicit_test = has(q, r'\b(?:xet nghiem|dinh luong|dich vu|xn)\b')
        ids, loose, spans = matches
        if ids == ['tumor_markers'] and has(q, CA125) and re.match(r'^(?:chi dinh |dieu kien (?:bhyt )?cho )?(?:chup |sieu am |noi soi |pet ct\b)', q):
            return {'ids': [], 'kind': 'other_service'}
        drug_question = has(q, r'\b(?:thuoc nay|thuoc do|bhyt (?:cua|cho) thuoc|thuoc (?:nay |do )?(?:co duoc|duoc|co bhyt))\b')
        marker = has(q, r'\b(?:ket qua|duong tinh|am tinh|chua co|chua xet nghiem|chua lam|cho xet nghiem|cho ket qua|can xet nghiem|de nghi xet nghiem|chi dinh xet nghiem)\b')
        test_focus = has(q, r'\b(?:bhyt (?:cua|cho) (?:xet nghiem|xn)|(?:xet nghiem|dich vu|xn|dinh luong).{0,80}(?:co duoc|co bhyt|thanh toan|chi tra|dieu kien)|chi phi xet nghiem)\b')
        both = bool(drug_hits or state.get('selected_ids') or has(q, r'\bthuoc\b')) and has(q, r'\b(?:ca hai|ca thuoc va|ca xet nghiem va|va (?:thuoc|erlotinib|gefitinib|afatinib|osimertinib)|va (?:ca )?xet nghiem)\b')
        if not ids and lab_state.get('pending') == 'confirm' and lab_state.get('id') in self.services and re.fullmatch(CONFIRMATION, q):
            return {'ids': [lab_state['id']], 'kind': 'lab', 'confirmed': True}
        markers = [i for i in ids if self.services[i].get('marker')]
        # "Cả xét nghiệm HER2 và Trastuzumab …", "HbA1c và Metformin …": a medicine and a test joined
        # by "và/cùng/lẫn", whatever the medicine is. The test must be an operand of the conjunction
        # (not a result such as "HER2 dương tính" elsewhere in a medicine question).
        if drug_hits and ids and not both:
            joined = False
            for i in ids:
                for start, end in spans[i]:
                    left, right = q[:start], q[end:]
                    if has(right, r'^(?: \w+){0,3} (?:va|cung|lan)(?: ca)?(?: thuoc)? \w') or has(left, r'\b(?:va|cung|lan)(?: ca)?(?: viec)?(?: lam)?(?: (?:xet nghiem|dinh luong|xn))?(?: dot bien(?: gen)?)? $'):
                        joined = True
            # "Cả … và …" asks for both whatever else the sentence says ("… chưa có kết quả xét nghiệm").
            explicit_both = has(q, r'\bca\b.{0,60}\b(?:va|lan|cung)\b|\bca hai\b|\bdeu (?:duoc|co)\b')
            both = joined and (explicit_both or not (markers and marker))
        # "Xét nghiệm đột biến gen EGFR … có suy thận" is the mutation test; a kidney word only
        # redirects when nothing says mutation, and asks when a cancer is named as well.
        mutation = has(q, r'\b(?:dot bien|gen|gene)\b')
        cancer = has(q, r'\b(?:ung thu|nsclc|utp)\b')
        lower_e = bool(re.search(r'\beGFR\b', message))
        if renal and 'egfr' in ids and not mutation and (lower_e or not cancer):
            return {'ids': [], 'kind': 'ambiguous_egfr' if cancer else 'renal'}
        if 'egfr' in ids and re.search(r'\beGFR\b', message) and not mutation and not cancer and not drug_hits:
            return {'ids': [], 'kind': 'ambiguous_egfr'}
        # Insulin used to describe the HbA1c exception is not a second coverage question.
        only_insulin_context = 'hba1c' in ids and has(q, r'\bthai ky\b') and not both
        if markers and not both:
            # EGFR / HER2 / KRAS / BRAF named as the condition of a medicine stay with the medicine.
            if drug_question or (drug_hits and marker and not test_focus):
                return None
            if state.get('selected_ids') and not test_focus and (not explicit_test or marker):
                return None
            if drug_hits and not test_focus:      # "Trastuzumab ung thư vú không xét nghiệm HER2"
                return None
        others = [i for i in ids if i not in markers]
        if others and not both and not only_insulin_context:
            # "Metformin đái tháo đường HbA1c 9%", "HbA1c 8% thì dùng thuốc gì": a result value
            # in a medicine question is not a request to order the test.
            drugish = bool(drug_hits or drug_words) or drug_question or has(q, r'\bthuoc (?:gi|nao)\b')
            value = any(has(q[end:end + 24], r'^ (?:cao|thap|tang|giam|binh thuong|la \d|bang \d|tren \d|duoi \d|\d)') for i in others for _, end in spans[i])
            case_words = has(q, r'\b(?:hom nay|lan truoc|cach day|chi dinh|lam lai|lan dau|lan thu|chua tung|lan nay)\b')
            starts = any(start == 0 for i in others for start, _ in spans[i])
            if drugish and not test_focus and (value or not (explicit_test or case_words or starts)):
                return None
        if ids:
            return {'ids': ids, 'kind': 'mixed' if both and not only_insulin_context else 'lab', 'loose': sorted(loose)}
        if state.get('selected_ids') and not test_focus and has(q, r'\b(?:fish|ihc|her2|her 2|egfr|kras|nras|ras|co can xet nghiem|ket qua xet nghiem)\b'):
            return None
        # "Định lượng albumin máu có được BHYT không" asks about a test even though albumin is also a medicine.
        lab_start = has(q, r'^(?:xet nghiem|dinh luong|xn|chi dinh xet nghiem|lam xet nghiem)\b') and not drug_question and not has(q, r'\b(?:truoc khi dung|khi dung|dang dung|dieu tri bang|thuoc)\b')
        if (drug_hits or drug_question or has(q, r'\bthuoc\b')) and not lab_start:
            return None
        named_other = has(q, COMMON_TESTS)
        if explicit_test or named_other:
            # A newly named test that is not in the lists must never reuse another service's rule.
            # "Xét nghiệm để chẩn đoán đột biến trong điều trị" answers the bot's own question
            # about the test under discussion; "xét nghiệm ABC …" names another test.
            referring = has(q, r'\b(?:(?:xet nghiem|xn|dinh luong) (?:nay|do|lai|lan|de|nham|la|duoc|hom nay|cho benh nhan|da|se|dang|thi|khi|truoc|tren)|lan truoc|lan dau|lan thu|dinh luong lai)\b')
            if named_other or not (lab_state and referring):
                return {'ids': [], 'kind': 'unsupported'}
        if has(q, OTHER_SERVICES) and has(q, COVERAGE) and not state.get('selected_ids'):
            return {'ids': [], 'kind': 'other_service'}
        followup = has(q, r'\b(?:dieu kien|quy dinh|nguon|ngay|tuan|thang|lan truoc|lan dau|lan thu|dai thao duong|dtd|thai ky|insulin|phac do|theo doi|danh gia|dieu tri|chan doan|ung thu|nsclc|te bao nho|tam soat|sang loc|khong ro|chua ro|khong nho|khong biet|khong dung|chua dung|chua lam|chua tung|da lam|da xet nghiem)\b') or has(message, r'\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}')
        if lab_state.get('id') in self.services and followup:
            return {'ids': [lab_state['id']], 'kind': 'lab'}
        if lab_state.get('assay') == 'ca125' and (has(q, NEW_CASE) or has(q, r'\b(?:tan suat|bao lau|phan tram|muc gia|gia bao nhieu|di can|buong trung)\b')):
            return {'ids': ['tumor_markers'], 'kind': 'lab'}
        if lab_state.get('pending') in ('insulin', 'diabetes', 'disease', 'purpose', 'gestational') and q in YES_NO:
            return {'ids': [lab_state['id']], 'kind': 'lab'}
        return None

    # ---- answer -------------------------------------------------------------------
    def citation(self, row):
        d = self.doc(row)
        excerpt = row['quote'] + ('\nTỷ lệ, mức giá thanh toán: ' + ' '.join(row['rate']) if row.get('rate') else '')
        return {'id': 'LAB-' + row['id'], 'document_id': d['document_id'],
                'document_title': d['title'], 'locator': row['locator'],
                'page': row['page'], 'page_checked': True, 'excerpt': excerpt,
                'source_url': d['source_url'], 'official_url': d['official_url'],
                'local_url': d['local_url'], 'viewer_url': row['viewer_url'],
                'transcription': row.get('transcription', 'text_layer'),
                'effective_from': d['effective_from'], 'checked_as_of': d['checked_as_of']}

    @staticmethod
    def reading(row, f):
        """The facts as the chatbot read them, in plain words, so a misreading is visible."""
        day = lambda iso: '/'.join(reversed(iso.split('-')))
        out = []
        if f.get('ca125'):
            purpose = CA125_PURPOSES.get(f.get('marker_purpose'))
            return ['Xét nghiệm: CA 125', 'Mục đích: ' + (purpose[0] if purpose else 'chưa rõ'),
                    'Bệnh cảnh: ' + CA125_SITES.get(f.get('marker_site'), 'chưa xác định')]
        if row.get('rule') == 'hba1c':
            out.append('Mục đích: ' + {'regimen': 'xác định phác đồ điều trị', 'monitoring': 'đánh giá kết quả điều trị', 'screening': 'sàng lọc/chẩn đoán ban đầu', 'ambiguous': 'chưa rõ (câu hỏi nêu hơn một mục đích)'}.get(f.get('purpose'), 'chưa nêu'))
            out.append('Đã chẩn đoán xác định đái tháo đường: ' + {True: 'có', False: 'chưa'}.get(f.get('diabetes'), 'chưa nêu'))
            if 'gestational' in f:
                out.append('Đái tháo đường thai kỳ: ' + {True: 'có', False: 'không'}.get(f['gestational'], 'chưa rõ'))
            if 'insulin' in f:
                out.append('Insulin: ' + ('đang dùng' if f['insulin'] else 'không dùng'))
            if f.get('first_test') is True:
                out.append('Lần trước: chưa từng làm HbA1c')
            elif f.get('last_date'):
                out.append('Lần trước: ' + day(f['last_date']))
            elif f.get('last_range'):
                out.append(f"Lần trước: khoảng {f['last_range'][2]} tháng trước (chưa có ngày chính xác)")
            if f.get('planned_date'):
                out.append('Lần này: ' + day(f['planned_date']))
        else:
            if 'disease' in f:
                out.append('Bệnh: ' + (DISEASE_LABEL.get(f['disease']) or {'unknown': 'chưa xác định'}.get(f['disease'], 'bệnh khác, ngoài phạm vi của dòng')))
            if row.get('rule') == 'gene':
                out.append('Mục đích: ' + {'mutation_in_treatment': 'chẩn đoán đột biến gen trong điều trị', 'screening': 'tầm soát/sàng lọc',
                                           'not_mutation': 'không nhằm chẩn đoán đột biến gen'}.get(f.get('purpose'), 'chưa nêu'))
        return out

    def source_links(self):
        return [{'label': d['title'], 'url': d['local_url']} for d in self.documents.values()]

    def answer(self, message, state, route, today=None):
        if 'guide' in route:
            result = self.guidance.answer(norm(message), route['guide'], state.get('lab_guide', {}), self)
            if route['ids']:
                # Conditions for a second service are shown without attributing case facts to it.
                row_route = {k:v for k,v in route.items() if k != 'guide'}
                rows = self.answer('', {}, row_route, today)
                result['lab_results'] = rows['lab_results']
                result['citations'] = rows['citations']
                if rows.get('notice') or rows['status'] == 'source_unavailable':
                    result['notice'] = rows.get('notice') or rows['answer']
            return result
        today = today or local_today()
        base = dict(snapshot=self.source.get('checked_as_of'), mode='local', domain='lab',
                    answer='', results=[], lab_results=[], citations=[], suggestions=[], followups=[], state={})
        if route['kind'] == 'ambiguous_egfr':
            return base | {'status': 'needs_info', 'answer': 'Bạn đang hỏi xét nghiệm đột biến gen EGFR trong ung thư, hay eGFR là mức lọc cầu thận? Hãy nêu rõ để tra đúng dịch vụ.'}
        if route['kind'] == 'renal':
            return base | {'status': 'unknown', 'answer': 'eGFR về mức lọc cầu thận không phải xét nghiệm đột biến gen EGFR. Bộ dữ liệu này chưa có quy tắc BHYT cho dịch vụ thận đang hỏi.'}
        if route['kind'] == 'other_service':
            return base | {'status': 'unknown', 'lab_links': self.source_links(),
                           'answer': 'Chatbot mới nạp các dòng xét nghiệm. Nhiều dịch vụ chẩn đoán hình ảnh, thăm dò chức năng và thủ thuật cũng có điều kiện thanh toán riêng trong Thông tư 39/2024 và bản hợp nhất 17/VBHN-BYT nhưng chưa được nạp; hãy mở hai tài liệu dưới đây để đối chiếu. Chưa nạp không có nghĩa là BHYT không chi trả.'}
        if route['kind'] == 'unsupported':
            n = len(self.services)
            return base | {'status': 'unknown', 'lab_links': self.source_links(),
                           'answer': f'Chưa thấy xét nghiệm đang hỏi trong {n} dòng xét nghiệm có điều kiện thanh toán riêng đã nạp (Thông tư 39/2024 và bản hợp nhất 17/VBHN-BYT). '
                                     'Cần đối chiếu đúng tên kỹ thuật, điều kiện chung và các trường hợp loại trừ trong văn bản. '
                                     'Chatbot khớp theo tên nên có thể sót tên gọi khác: không tìm thấy ở đây không có nghĩa là BHYT không chi trả, cũng chưa khẳng định xét nghiệm này không có điều kiện. '
                                     'Bác sĩ có thể gửi mã dịch vụ hoặc tên đầy đủ, loại mẫu và phương pháp trên phiếu chỉ định.'}
        # A damaged file stops only the services that cite it, not the whole laboratory module.
        usable = [sid for sid in route['ids'] if self.integrity_ok(sid)]
        broken = [self.services[sid]['name'] for sid in route['ids'] if sid not in usable]
        if broken:
            base['notice'] = 'Chưa trả lời cho xét nghiệm: ' + '; '.join(broken) + ' — tệp nguồn của dòng này bị thiếu hoặc đã thay đổi, cần đối chiếu lại.'
        if not usable:
            return base | {'status': 'source_unavailable', 'answer': 'Nguồn của xét nghiệm đang hỏi bị thiếu hoặc đã thay đổi. Cần đối chiếu lại tài liệu trước khi trả lời điều kiện BHYT.'}
        single = len(route['ids']) == 1
        for sid in usable:
            row = self.services[sid]
            prev = state.get('lab', {}) if single else {}
            confirmed = bool(route.get('confirmed'))
            if confirmed:      # the user confirmed the reading shown last turn: nothing is read again
                facts, case, errors, same_case = dict(prev.get('facts', {})), bool(prev.get('case')), [], True
            else:
                facts, case, errors, same_case = self.extract(message, sid, prev, today)
            if not single:
                # Dates/purposes in a multi-service question cannot be attributed safely.
                facts, case, errors = {k: v for k, v in facts.items() if k == 'foreign_method'}, False, []
            a = self.evaluate(sid, facts, case, errors, today)
            rule_active = bool(row.get('rule') or facts.get('ca125'))
            if rule_active and facts:
                a['reading'] = self.reading(row, facts)
            # Words the chatbot could not account for, and voiced doubt, stay with the case over
            # the following turns: a later "lần trước cách 35 ngày" cannot slip past them. Only
            # an explicit confirmation of the reading clears them.
            unread, doubt = [], None
            if rule_active and not confirmed:
                carried = prev if same_case else {}
                aliases = [norm(x) for x in row.get('aliases', []) + [row['name']]]
                doubt_text = ' ; '.join(clause_list(message))
                if facts.get('ca125'):
                    aliases.append('buong trung di can nguyen phat u ut')
                    doubt_text = re.sub(r'\b' + CUP + r'\b', 'cupmarker', doubt_text)
                unread = list(dict.fromkeys(list(carried.get('unread', [])) + unread_words(message, aliases)))
                found = re.search(DOUBT, doubt_text)
                doubt = found.group(0).replace('loaitru', 'loại trừ') if found else carried.get('doubt')
            if unread or doubt:
                why = ('còn những từ chatbot chưa hiểu chắc: ' + ', '.join('“' + w + '”' for w in unread[:8])) if unread else 'có phần chưa chắc chắn (“' + doubt + '”)'
                # Nothing that reads like a conclusion is shown while the reading is unconfirmed.
                a = {**a, 'reasons': [], 'highlight': []}
                if a['status'] in ('source_conditions_match', 'source_condition_not_met'):
                    a = {**a, 'status': 'needs_confirmation', 'pending': 'confirm', 'unread': unread,
                         'conclusion': 'Chatbot chưa kết luận vì trong câu hỏi ' + why + '. Hãy xem phần “Chatbot hiểu dữ kiện như sau”: nếu đúng, bấm “Đúng, đối chiếu theo các dữ kiện này”; nếu chưa đúng, hãy nêu lại dữ kiện.'}
                else:
                    a = {**a, 'unread': unread, 'unconfirmed_note': 'Trong câu hỏi ' + why + '. Chatbot sẽ chờ bạn xác nhận cách hiểu dữ kiện trước khi kết luận.'}
            elif confirmed and a['status'] in ('source_conditions_match', 'source_condition_not_met'):
                a = {**a, 'conclusion': 'Theo các dữ kiện bạn vừa xác nhận: ' + a['conclusion'][0].lower() + a['conclusion'][1:]}
            notes = []
            if sid == 'tumor_markers' and has(norm(message), r'\b(?:tam soat|sang loc)\b'):
                notes.append('Dòng này quy định chẩn đoán và theo dõi theo từng nhánh. Riêng với sàng lọc người chưa có triệu chứng, cần kiểm tra chương trình và căn cứ thanh toán áp dụng.')
            if sid in route.get('loose', []) and row.get('name_note'):
                notes.append(row['name_note'])
            if row.get('transcription') == 'scan_read':
                notes.append('Nguyên văn dòng này được chép từ ảnh trang của bản hợp nhất 17/VBHN-BYT (bản scan, Đỗ Quốc An đọc). ' + self.scan_status)
            if row.get('source_note'):
                notes.append(row['source_note'])
            if a.get('unconfirmed_note'):
                notes.insert(0, a.pop('unconfirmed_note'))
            if row.get('transcription') == 'scan_read':
                review = {'kind': 'attested' if self.attestation else 'unreviewed', 'text': 'Nguyên văn chép từ bản scan. ' + self.scan_status}
            elif rule_active:
                review = {'kind': 'unreviewed', 'text': 'Nguyên văn lấy từ lớp chữ của phụ lục Thông tư 39/2024. Phần đối chiếu ca bệnh do nhóm dự án xây dựng, chưa nằm trong phạm vi Dược/BHYT thẩm định.'}
            else:
                review = {'kind': 'source_text', 'text': 'Nguyên văn lấy từ lớp chữ của phụ lục Thông tư 39/2024.'}
            base['lab_results'].append({'id': sid, 'name': 'Định lượng CA 125' if facts.get('ca125') else row['name'], **a, 'conditions': row['conditions'],
                                        'rate': row.get('rate') or [], 'rate_mode': row.get('rate_mode'), 'notes': notes,
                                        'transcription': row.get('transcription', 'text_layer'), 'automatic': rule_active,
                                        'citation': self.citation(row), 'facts': facts, 'review': review,
                                        'scope': 'Đối chiếu điều kiện riêng của dịch vụ theo nguồn; chưa xác nhận mức hưởng cá nhân, giá hay phạm vi hợp đồng của bệnh viện.'})
            base['citations'].append(self.citation(row))
            if single:
                base['state'] = {'lab': {'id': sid, 'facts': facts, 'case': case, 'pending': a.get('pending'), 'date': today.isoformat(),
                                         'unread': unread, 'doubt': doubt}}
                if facts.get('ca125'):
                    base['state']['lab']['assay'] = 'ca125'
        statuses = [r['status'] for r in base['lab_results']]
        base['status'] = 'needs_info' if 'needs_info' in statuses or 'needs_confirmation' in statuses else 'answered'
        base['answer'] = '\n\n'.join(r['name'] + ': ' + r['conclusion'] for r in base['lab_results'])
        base['source_checked_as_of'] = self.source['checked_as_of']
        return base

    # ---- facts of the case --------------------------------------------------------
    @staticmethod
    def diseases_in(clauses, monitoring_is_doubt=True):
        """[(key, state)] with state 'named' | 'negated' | 'unknown', in reading order.
        "chưa có chẩn đoán …", "nghi ngờ …", "chưa loại trừ …" are unknown; only a plain
        "không phải / không bị / loại trừ …" is negated."""
        out = []
        for n, c in enumerate(clauses):
            taken = []
            for key, _, pattern in DISEASES:
                for m in re.finditer(r'\b(?:' + pattern + r')\b', c):
                    if any(a <= m.start() < b for a, b in taken):
                        continue
                    taken.append((m.start(), m.end()))
                    state, word = governed(c, m.start(), m.end(), F_IS, SUSPECT)
                    if monitoring_is_doubt and has(c[:m.start()], r'\b(?:theo doi|td) $'):
                        state = 'unknown'                      # "theo dõi K phổi": suspected, not diagnosed
                    if has(c[m.end():], r'\b(?:loaitru|(?:chua|khong) (?:phan biet|xac dinh|chac|khang dinh|ro|co ket qua|ket luan|hoi chan)|hay (?:la )?(?:ung thu|te bao|sclc|nsclc))\b'):
                        state = 'unknown'                      # "… đã được chẩn đoán loại trừ", "… hay tế bào nhỏ chưa phân biệt được"
                    result = 'named' if state == 'yes' else 'negated' if state == 'no' and word != 'chua' else 'unknown'
                    out.append((n, m.start(), key, result))
        # One state per disease: stated in one clause and denied or doubted in another
        # ("trước đây chẩn đoán NSCLC nhưng nay xác định không phải NSCLC") is unknown.
        merged = {}
        for _, _, key, result in sorted(out):
            merged[key] = result if merged.get(key, result) == result else 'unknown'
        return list(merged.items())

    def extract(self, message, sid, prev, today):
        q = norm(message)
        row = self.services[sid]
        named = any(sid == i for i in self.match_services(q, True)[0])
        continuation = not named or has(q, r'^(?:con|vay|neu|the|lan truoc|lan nay)\b')
        same = prev.get('id') == sid and continuation and not has(q, NEW_CASE)
        f = dict(prev.get('facts', {})) if same else {}
        if sid == 'tumor_markers':
            if has(q, OTHER_MARKER):
                return ({'multiple_markers': True} if has(q, CA125) else {}), False, [], False
            if has(q, CA125) or (not named and prev.get('assay') == 'ca125'):
                f['ca125'] = True
                extract_ca125(message, f)
                return f, True, [], same
            return {}, False, [], False
        errors = []
        case = bool(prev.get('case')) if same else False
        if same and q in YES_NO:
            key = prev.get('pending')
            value = True if q in ('co', 'dung', 'dung roi') else False if q in ('khong', 'chua') else None
            if key in ('insulin', 'diabetes', 'gestational'):
                if value is None:
                    f.pop(key, None)
                else:
                    f[key] = value
            if key == 'disease':
                scope = row.get('scope', [])
                # "Có" only identifies the disease when the row names a single one.
                f['disease'] = scope[0] if value is True and len(scope) == 1 else 'other' if value is False else 'unknown'
            if key == 'purpose' and row.get('rule') == 'gene':
                if value is True:
                    f['purpose'] = 'mutation_in_treatment'
                else:
                    f.pop('purpose', None)
        generic = has(q, r'\b(?:dieu kien (?:bhyt|thanh toan|chung)|quy dinh|noi chung|can dieu kien|dieu kien gi)\b')
        case_requested = has(q, r'\b(?:hom nay|ngay mai|chi dinh lai|lam lai|lan truoc|cach day|truoc do|benh nhan|nguoi benh|truong hop nay|ca nay|da duoc chan doan|da chan doan|lan dau|lan thu|chua tung)\b')
        if case_requested:
            case = True
        # The question names a method or test other than the one this row is about.
        foreign = bool(row.get('foreign') and has(q, row['foreign']))
        if row.get('rule') == 'gene':
            if sid == 'her2' and has(q, r'\b(?:ish|cish|sish|fish|ihc|lai tai cho|hoa mo mien dich)\b'):
                f['non_mutation_method'] = True
            if has(q, r'\b(?:chi (?:de |nham )?tien luong|tien luong don thuan)\b'):
                f['prognosis_only'] = True
        if generic and not case_requested and not (f.get('non_mutation_method') or f.get('prognosis_only')) and not (row.get('special') and has(q, row['special'])) and not has(q, r'\b(?:tam soat|sang loc|ngs|pcr|panel|gia|ty le|phan tram)\b'):
            return ({'foreign_method': True} if foreign else {}), False, [], same
        clauses = clause_list(message)
        if row.get('rule') == 'hba1c':
            self.extract_hba1c(message, q, clauses, f, prev if same else {}, today, errors)
        elif row.get('rule') in ('gene', 'scope'):
            self.extract_disease(q, clauses, f, row)
        f.pop('foreign_method', None)
        if foreign:
            f['foreign_method'] = True
        return f, case, errors, same

    def extract_disease(self, q, clauses, f, row):
        found = self.diseases_in(clauses, monitoring_is_doubt=row.get('rule') == 'gene')
        named = [k for k, s in found if s == 'named']
        scope = row.get('scope', [])
        if named:
            inside = [k for k in named if k in scope]
            # Several diseases in one question: decide only when they agree.
            f['disease'] = named[0] if len(named) == 1 else inside[0] if len(inside) == len(named) else 'other' if not inside else 'unknown'
        elif any(s == 'unknown' for _, s in found):
            f['disease'] = 'unknown'
        elif found:
            f['disease'] = 'other'
        if has(q, r'\b(?:chua ro|khong ro).{0,20}(?:the benh|mo benh hoc|loai ung thu)\b'):
            f['disease'] = 'unknown'
        # Purpose. Screening only when plainly stated; "không tầm soát mà …" and a later
        # correction replace it. A purpose counts only when every mention of it is plain.
        screening = verdict(mentions(clauses, r'tam soat|sang loc', F_PURPOSE))
        if screening == 'yes':
            f['purpose'] = 'screening'
        elif screening in ('no', 'unknown') and f.get('purpose') == 'screening':
            f.pop('purpose')
        if row.get('rule') == 'gene':
            mutation = mentions(clauses, r'chan doan dot bien|(?:tim|xac dinh|phat hien) dot bien', F_PURPOSE)
            treatment = mentions(clauses, r'dieu tri', F_PURPOSE)
            stated = [x[0] for x in mutation + treatment]
            if screening == 'yes' and 'yes' in stated:
                f.pop('purpose', None)                         # "vừa tầm soát vừa chẩn đoán đột biến": ask
            elif screening == 'yes':
                pass
            elif any(x[0] == 'no' for x in mutation):
                f['purpose'] = 'not_mutation'                  # "không nhằm chẩn đoán đột biến …"
            elif stated and all(x == 'yes' for x in stated):
                f['purpose'] = 'mutation_in_treatment'         # replaces an earlier "tầm soát"
            elif stated:
                f.pop('purpose', None)                         # "có thể nhằm …", "chưa điều trị": ask
            # Method, sample, repetition or price are not in the row: an explicit limitation.
            f.pop('special_question', None)
            if has(q, row.get('special') or r'\b(?:ngs|pcr|panel|sinh thiet long|mau|huyet tuong|lan thu|lan 2|lan hai|lan 3|lam lai|lap lai|nhac lai|bao nhieu lan|gia|phan tram|ty le)\b'):
                f['special_question'] = True

    def extract_hba1c(self, message, q, clauses, f, prev, today, errors):
        # Purpose: only a plainly stated purpose counts; a negated one is dropped.
        kinds = {
            'screening': r'tam soat|sang loc|chan doan ban dau|(?<!da )(?<!duoc )(?<!moi )(?<!vua )chan doan (?:xac dinh )?' + DIABETES + r'|(?:de|nham) chan doan(?! dot bien)',
            'regimen': r'(?:xac dinh|chon|lap|dieu chinh|thay doi|doi) phac do',
            'monitoring': r'theo doi|danh gia (?:ket qua |dap ung |hieu qua )?dieu tri|kiem soat duong huyet'}
        # A purpose stated plainly once counts ("không theo dõi được tại nhà, đánh giá kết quả điều trị").
        stated = {k: {x[0] for x in mentions(clauses, pattern, F_PURPOSE)} for k, pattern in kinds.items()}
        named = [kind for kind in ('screening', 'regimen', 'monitoring') if 'yes' in stated[kind]]
        if len(named) == 1:
            f['purpose'] = named[0]
        elif named:
            f['purpose'] = 'ambiguous'                             # "để sàng lọc hoặc theo dõi": two purposes, ask which
            if 'screening' in named:
                f.pop('diabetes', None)                            # "sàng lọc … đái tháo đường" says nothing sure about the diagnosis
        if f.get('purpose') in stated and stated[f['purpose']] and 'yes' not in stated[f['purpose']]:
            f.pop('purpose')
        if has(q, r'\b(?:khong|chua) (?:ro|biet|xac dinh) muc dich\b'):
            f.pop('purpose', None)
        # Confirmed diabetes: suspected, pre-diabetes or "chưa có chẩn đoán" is not confirmed.
        found = []
        for state, word, c, m in mentions(clauses, r'(?:tien )?' + DIABETES, F_IS, SUSPECT):
            if c[m.end():].startswith(' thai ky') and state == 'no':
                continue                                           # "không phải đái tháo đường thai kỳ" negates the pregnancy form only
            found.append(False if m.group(0).startswith('tien ') or state == 'no' or word in SUSPICION else True if state == 'yes' else None)
        if has(q, r'\broi loan dung nap\b'):
            found.append(False)
        if found:
            if None in found or len(set(found)) > 1:
                f.pop('diabetes', None)
            else:
                f['diabetes'] = found[0]
        # Gestational diabetes decides which branch applies, so it is read like any other fact:
        # "chưa xác định có đái tháo đường thai kỳ" is not gestational diabetes.
        found = mentions(clauses, r'thai ky', F_GESTATIONAL)
        if found:
            state = verdict(found)
            f['gestational'] = True if state == 'yes' else False if state == 'no' and all(x[1] != 'chua' for x in found) else 'unknown'
        # Insulin: "không còn dùng", "đã dừng", "chưa có chỉ định dùng" are not "đang dùng";
        # "dự kiến dùng", "có thể sẽ dùng", "… không?" are asked back.
        insulin = verdict(mentions(clauses, r'insulin', F_USE, stoppable=True))
        if any(raw.isascii() and has(norm(raw), r'\bda dung (?:\w+ ){0,2}insulin\b') for raw in CLAUSE_SPLIT.split(message.lower())):
            insulin = 'unknown'                                    # typed without diacritics: "đã dùng" or "đã dừng"?
        if insulin == 'yes':
            f['insulin'] = True
        elif insulin == 'no':
            f['insulin'] = False
        elif insulin == 'unknown':
            f.pop('insulin', None)
        # First test: "không phải lần đầu" means there was an earlier test.
        # "Lần đầu" must be about this test: "lần đầu tại bệnh viện này" or "khám lần đầu" says
        # nothing about an earlier HbA1c elsewhere.
        test = r'(?:lam|xet nghiem|do|thuc hien|dinh luong|chi dinh)'
        sure = (r'chua tung ' + test + r'(?: hba1c| a1c)?|chua ' + test + r'(?: hba1c| a1c)? (?:lan nao|bao gio)|'
                + test + r'(?: hba1c| a1c)? lan dau(?: tien)?|(?:hba1c|a1c) lan dau(?: tien)?|lan dau(?: tien)? ' + test)
        found = mentions(clauses, sure, {'phai', 'la'})
        place = r'^ (?:tai|o|trong|cua) (?:benh vien|vien|co so|khoa|phong kham|day|noi|trung tam)'
        for i, x in enumerate(found):
            if has(x[2][x[3].end():], place):
                found[i] = ('unknown', 'place') + x[2:]
        covered = [(x[2], x[3].start(), x[3].end()) for x in found]
        for state, word, c, m in mentions(clauses, r'lan dau(?: tien)?', {'phai', 'la'}):
            if any(c == cc and a <= m.start() < b for cc, a, b in covered):
                continue
            bare = re.fullmatch(r'(?:(?:day|lan nay|hom nay|nay) )?(?:(?:khong|chua) phai )?(?:la )?lan dau(?: tien)?', c)
            found.append((state if bare else 'unknown', word, c, m))
        first = verdict(found)
        if first == 'yes':
            f['first_test'] = True
            f.pop('last_date', None); f.pop('last_range', None)
        elif first == 'no':
            f['first_test'] = False
        elif first == 'unknown':
            f.pop('first_test', None)
        if has(q, r'\b(?:lan thu (?:2|hai|3|ba)|tu lan thu 2|da lam|da xet nghiem)\b'):
            f['first_test'] = False
        self.extract_dates(message, q, f, prev, today, errors)

    @staticmethod
    def extract_dates(message, q, f, prev, today, errors):
        f.pop('date_error', None)
        if q in ('khong nho', 'khong biet', 'chua ro', 'khong ro') or has(q, r'\b(?:khong nho|khong biet|chua ro|khong ro).{0,35}(?:ngay|lan truoc)|\b(?:ngay|lan truoc).{0,20}(?:khong nho|chua ro|khong ro)\b'):
            f.pop('last_date', None); f.pop('last_range', None)
            f.pop('first_test', None)

        def spans(unit):
            found = re.findall(r'\b(?:cach(?: day)?\s+)?(\d{1,4})\s+' + unit + r'\s+(?:truoc|roi)\b|\bcach(?: day)?\s+(?:khoang\s+)?(\d{1,4})\s+' + unit + r'\b', q)
            return {int(a or b) for a, b in found}
        days, weeks, months = spans('ngay'), spans('tuan'), spans('thang')
        if has(q, r'\b(?:gan|hon|khoang|chua den|chua toi|khong qua|duoi|tren|it nhat|toi da|toi thieu|xap xi|tam)\s+\d+\s+(?:ngay|tuan|thang)\b'):
            # "gần 100 ngày", "chưa đến 3 tháng": an estimate cannot be compared with a day limit.
            errors.append('Khoảng cách mới là ước lượng (“gần”, “hơn”, “khoảng”, “chưa đến”…); hãy nêu ngày thực hiện lần trước.')
            days = weeks = months = set()
        exact = days | {7 * w for w in weeks}
        if len(exact) > 1 or (exact and months):
            errors.append('Có nhiều khoảng cách khác nhau; hãy nêu ngày thực hiện gần nhất.')
        elif exact:
            f['last_date'] = (today - dt.timedelta(days=exact.pop())).isoformat()
            f['first_test'] = False
            f.pop('last_range', None)
        elif len(months) > 1:
            errors.append('Có nhiều khoảng cách khác nhau; hãy nêu ngày thực hiện gần nhất.')
        elif months:
            # "2 tháng trước" is 56–62 days: usable only when the whole range falls on one side of the rule.
            n = months.pop()
            f['last_range'] = [28 * n, 31 * n, n]
            f['first_test'] = False
            f.pop('last_date', None)
        dates = list(re.finditer(r'(?<!\d)(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4})(?!\d)', message))
        assigned = {}
        filler = r'(?: (?:lam|thuc hien|xet nghiem|do|la|vao|luc|hom|ngay|hba1c|a1c))*$'
        for match in dates:
            value = match.group(0)
            try:
                parts = list(map(int, re.split(r'[/.-]', value)))
                date = dt.date(*parts) if len(value.split('-')[0]) == 4 else dt.date(parts[2], parts[1], parts[0])
            except ValueError:
                errors.append('Ngày không hợp lệ; hãy ghi đủ ngày/tháng/năm.')
                continue
            before = norm(message[max(0, match.start() - 70):match.start()])
            if has(before, r'(?:lan truoc|gan nhat|lan cu|truoc do|da (?:lam|thuc hien|xet nghiem))' + filler):
                role = 'last_date'
            elif has(before, r'(?:lan nay|du kien|chi dinh|hom nay|lam lai)' + filler):
                role = 'planned_date'
            elif len(dates) == 1 and prev.get('pending') == 'last_date':
                role = 'last_date'
            else:
                errors.append('Hãy ghi rõ ngày xét nghiệm lần trước và ngày dự kiến lần này để tránh nhầm hai mốc.')
                continue
            if role in assigned and assigned[role] != date.isoformat():
                errors.append('Có hai ngày cho cùng một lần xét nghiệm; cần xác nhận ngày đúng.')
            assigned[role] = date.isoformat()
        f.update(assigned)
        if 'last_date' in assigned:
            f['first_test'] = False
            f.pop('last_range', None)
        if has(q, r'\bngay mai\b') and 'planned_date' not in assigned:
            f['planned_date'] = (today + dt.timedelta(days=1)).isoformat()
        elif has(q, r'\bhom nay\b') and 'planned_date' not in assigned:
            f.pop('planned_date', None)
        if errors:
            f.pop('last_date', None); f.pop('last_range', None)
            f['date_error'] = ' '.join(errors)

    # ---- comparison with the source row --------------------------------------------
    def evaluate(self, sid, f, case, errors, today):
        row = self.services[sid]
        rule = row.get('rule')
        reasons = []

        def result(status, text, pending=None, highlight=()):
            return {'status': status, 'conclusion': text, 'reasons': reasons, 'pending': pending, 'highlight': list(highlight)}
        if sid == 'tumor_markers':
            if f.get('ca125'):
                return evaluate_ca125(f, result)
            if f.get('multiple_markers'):
                return result('conditions_only', 'CA 125 có nhánh riêng tại điểm a và b. Khi hỏi nhiều dấu ấn, '
                              'cần đối chiếu từng xét nghiệm với bệnh cảnh và mục đích tương ứng. Bác sĩ có thể hỏi riêng CA 125.')
        if rule == 'gene':
            return self.evaluate_gene(row, f, case, result, reasons)
        if rule == 'scope':
            return self.evaluate_scope(row, f, result, reasons)
        if rule != 'hba1c' and f.get('foreign_method'):
            return result('needs_review', 'Câu hỏi nêu kỹ thuật hoặc xét nghiệm khác với dòng này (xem tên dịch vụ và ghi chú). Chưa có căn cứ từ dòng này cho xét nghiệm đang hỏi; điều đó không có nghĩa là BHYT không chi trả.')
        if rule != 'hba1c':
            return result('conditions_only', 'Dịch vụ này có điều kiện thanh toán riêng trong nguồn; đọc nguyên văn dưới đây. Chatbot chưa tự đối chiếu ca bệnh cụ thể với dòng này.')
        if not case:
            if f.get('purpose') == 'screening' or f.get('diabetes') is False:
                return result('source_condition_not_met', 'Bối cảnh vừa nêu không khớp nhánh HbA1c đã tra; bộ dữ liệu này chưa có căn cứ khác để kết luận cho sàng lọc/chẩn đoán ban đầu.')
            return result('conditions_only', 'Có quy định thanh toán HbA1c theo mục đích xét nghiệm và khoảng cách giữa các lần. Xem đủ ba nhánh điều kiện dưới đây.')
        if errors or f.get('date_error'):
            return result('needs_info', f.get('date_error') or ' '.join(errors), 'last_date')
        if f.get('purpose') == 'ambiguous':
            return result('needs_info', 'Câu hỏi nêu hơn một mục đích. Lần này để xác định phác đồ điều trị, đánh giá kết quả điều trị, hay sàng lọc/chẩn đoán ban đầu?', 'purpose')
        planned = dt.date.fromisoformat(f.get('planned_date', today.isoformat()))
        if planned < dt.date.fromisoformat(self.source['effective_from']) or planned > today:
            return result('needs_review', 'Ngày xét nghiệm nằm trước ngày áp dụng bộ quy tắc hoặc trong tương lai. Cần kiểm tra văn bản áp dụng ở thời điểm đó; chưa đối chiếu tự động.')
        if f.get('purpose') == 'screening' or f.get('diabetes') is False:
            return result('source_condition_not_met', 'Thông tin vừa nêu không khớp nhánh HbA1c đã có trong nguồn (đái tháo đường đã xác định/phục vụ điều trị). Không suy ra kết luận từ chối BHYT cho mọi trường hợp.')
        if f.get('gestational') == 'unknown':
            return result('needs_info', 'Trường hợp đang hỏi đã xác định là đái tháo đường thai kỳ chưa? Thông tin này quyết định nhánh điều kiện được áp dụng.', 'gestational')
        gestational = f.get('gestational') is True
        if gestational and 'insulin' not in f:
            return result('needs_info', 'Đái tháo đường thai kỳ có điều trị bằng insulin không? Thông tin này quyết định có áp dụng nhánh 30 ngày hay không.', 'insulin')
        exception = gestational and f.get('insulin') is True
        if not exception:
            if not f.get('purpose'):
                return result('needs_info', 'Lần này để xác định phác đồ điều trị, đánh giá kết quả điều trị, hay sàng lọc/chẩn đoán ban đầu?', 'purpose')
            if f.get('diabetes') is not True:
                return result('needs_info', 'Trường hợp đang hỏi đã được chẩn đoán xác định đái tháo đường chưa?', 'diabetes')
        mark = [2] if exception else [0] if f['purpose'] == 'regimen' else [1]
        reasons.append('Áp dụng nhánh đái tháo đường thai kỳ có insulin: mỗi 30 ngày một lần.' if exception else 'Áp dụng nhánh ' + ('xác định phác đồ điều trị.' if f['purpose'] == 'regimen' else 'đánh giá kết quả điều trị từ lần thứ 2.'))
        if f.get('first_test') is True:
            if not exception and f.get('purpose') == 'regimen':
                reasons.append('Bạn cho biết chưa từng thực hiện HbA1c; không có lần trước trong khoảng thời gian nguồn yêu cầu.')
                return result('source_conditions_match', 'Thông tin đã nêu khớp điều kiện riêng của nhánh xác định phác đồ trong nguồn; chưa xác nhận thanh toán thực tế.', highlight=mark)
            return result('needs_review', 'Bạn cho biết đây là lần đầu. Không áp máy móc điều kiện lặp lại để kết luận cho lần đầu; cần đối chiếu thêm mục đích và căn cứ phù hợp.', highlight=mark)
        policy = row['timing_policy']
        need, too_short = (30, 'Khoảng cách chưa đạt 30 ngày theo nhánh thai kỳ dùng insulin trong nguồn.') if exception else \
            (policy['below_days'], 'Khoảng cách ngắn hơn mốc 90 ± 3 ngày trong nguồn. Chưa khớp điều kiện thời gian của nhánh đang đối chiếu.')
        clear = 30 if exception else policy['review_through_days'] + 1      # from here on the interval is met
        matched = 'Thông tin đã nêu khớp điều kiện riêng của nhánh HbA1c đang đối chiếu; chưa xác nhận thanh toán thực tế.'
        if not f.get('last_date'):
            if f.get('last_range'):
                low, high, months = f['last_range']
                reasons.append(f'Lần trước cách khoảng {months} tháng (ước {low}–{high} ngày, chưa có ngày chính xác).')
                if high < need:
                    return result('source_condition_not_met', too_short, highlight=mark)
                if low >= clear:
                    return result('source_conditions_match', matched, highlight=mark)
                return result('needs_info', f'Khoảng “{months} tháng” có thể rơi đúng vào mốc thời gian của nguồn; hãy nêu ngày thực hiện lần trước để tính chính xác.', 'last_date', mark)
            return result('needs_info', 'HbA1c gần nhất được thực hiện ngày nào? Có thể trả lời “Lần trước ngày …” hoặc “cách … ngày”; nếu chưa từng làm, hãy nói rõ.', 'last_date', mark)
        last = dt.date.fromisoformat(f['last_date'])
        days = (planned - last).days
        reasons.append(f"Lần trước {last.strftime('%d/%m/%Y')}, lần này {planned.strftime('%d/%m/%Y')}: cách {days} ngày.")
        if days < 0:
            return result('needs_info', 'Ngày lần trước đang sau ngày lần này. Hãy kiểm tra lại hai mốc.', 'last_date', mark)
        if days < need:
            return result('source_condition_not_met', too_short, highlight=mark)
        if not exception and policy['review_from_days'] <= days <= policy['review_through_days']:
            reasons.append(policy['note'])
            return result('needs_review', 'Khoảng cách nằm trong vùng 90 ± 3 ngày. Giữ nguyên quy định và cần đối chiếu cách áp dụng sai số; chatbot chưa tự chốt ở mốc này.', highlight=mark)
        return result('source_conditions_match', matched, highlight=mark)

    @staticmethod
    def evaluate_gene(row, f, case, result, reasons):
        name, scope, label = row['name'], row['scope'], row['scope_label']
        if f.get('non_mutation_method'):
            return result('needs_review', 'Dòng HER2 này quy định xét nghiệm đột biến gen. IHC đánh giá biểu hiện protein; ISH/FISH có thể đánh giá khuếch đại gen. Cần tên và mã kỹ thuật ghi trên phiếu để đối chiếu riêng.')
        if f.get('prognosis_only'):
            return result('needs_review', 'Mục đích đang hỏi là tiên lượng đơn thuần. Dòng nguồn quy định chẩn đoán đột biến gen trong điều trị; chưa đủ căn cứ xác nhận chi trả cho mục đích này.')
        special = (row.get('special_note') or 'Dòng này không quy định cụ thể phương pháp, bệnh phẩm, số lần lặp lại hay giá/tỷ lệ.') + ' Cần đối chiếu đúng dịch vụ và nguồn bổ sung; chưa kết luận cho chi tiết vừa hỏi.'
        if f.get('special_question'):
            return result('needs_review', special)
        disease = f.get('disease')
        outside = disease not in (None, 'unknown', 'lung_unspecified') and disease not in scope
        if disease == 'lung_unspecified' and 'nsclc' not in scope:
            outside = True
        if outside or f.get('purpose') in ('screening', 'not_mutation'):
            text = (f'Bối cảnh vừa nêu không khớp phạm vi của dòng “{name}” (nguồn chỉ nêu {label}, để chẩn đoán đột biến gen trong điều trị). Không dùng dòng này để kết luận chi trả cho bệnh hoặc mục đích khác.' if not case else
                    f'Bệnh hoặc mục đích vừa nêu không khớp điều kiện của dòng “{name}” trong nguồn (nguồn chỉ nêu {label}); chưa có căn cứ khác trong bộ dữ liệu này.')
            return result('source_condition_not_met', text, highlight=[0])
        if not case:
            return result('conditions_only', f'Có quy định thanh toán {name[0].lower() + name[1:]} trong điều trị {label}. Điều kiện này độc lập với điều kiện dùng thuốc.')
        if disease not in scope:
            ask = (f'Nguồn áp dụng cho {label}. Trường hợp đang hỏi đã xác định thể bệnh này chưa?' if len(scope) == 1 or disease == 'lung_unspecified'
                   else f'Nguồn áp dụng cho {label}. Trường hợp đang hỏi là bệnh nào trong số này?')
            return result('needs_info', ask, 'disease')
        reasons.append(f'Bệnh được nêu: {DISEASE_LABEL[disease]} — khớp phạm vi bệnh của dòng này.')
        if f.get('purpose') != 'mutation_in_treatment':
            return result('needs_info', 'Xét nghiệm có nhằm chẩn đoán đột biến gen trong quá trình điều trị không?', 'purpose')
        reasons.append('Mục đích được nêu: chẩn đoán đột biến gen trong điều trị — khớp điều kiện riêng của dịch vụ.')
        return result('source_conditions_match', f'Thông tin đã nêu khớp điều kiện riêng của dòng “{name}” trong nguồn. Đây chưa phải xác nhận thanh toán của bệnh viện.', highlight=[0])

    @staticmethod
    def evaluate_scope(row, f, result, reasons):
        disease, scope = f.get('disease'), row['scope']
        if f.get('purpose') == 'screening' or (disease not in (None, 'unknown') and disease not in scope):
            return result('source_condition_not_met', f'Bệnh hoặc mục đích vừa nêu không nằm trong phạm vi của dòng “{row["name"]}” (nguồn nêu: {row["scope_label"]}). Không dùng dòng này để kết luận chi trả cho trường hợp khác.')
        if disease in scope:
            reasons.append(f'Bệnh được nêu: {DISEASE_LABEL[disease]} — có trong danh sách của dòng này.')
            reasons.append(row['scope_note'])
        return result('conditions_only', 'Dịch vụ này có điều kiện thanh toán riêng trong nguồn; đọc nguyên văn dưới đây.' + (' Chatbot chỉ đối chiếu được bệnh, chưa đối chiếu các điều kiện còn lại.' if disease in scope else ''))

    # ---- source viewer ---------------------------------------------------------------
    def source_html(self, sid):
        if sid not in self.services:
            return None
        s = self.services[sid]
        d = self.doc(s)
        e = html.escape
        verified = self.integrity_ok(sid)
        scan = s.get('transcription') == 'scan_read'
        images = s.get('images') or [{'url': s['image_url'], 'page': s['page']}]
        if verified:
            body = ''.join(f'<img class="lab-source-image" src="{e(i["url"])}" alt="Ảnh {"trang " + str(i["page"]) + " của bản hợp nhất, có dòng" if scan else "nguyên văn dòng"} STT {s["original_row"] if scan else s["appendix_row"]}, {e(s["name"])}">' for i in images)
        else:
            body = '<p class="error">Tệp nguồn bị thiếu hoặc thay đổi. Không hiển thị ảnh trích dẫn chưa kiểm chứng.</p>'
        hint = (f'Ảnh toàn trang của bản scan; dòng STT {s["original_row"]} nằm trên trang này. Phần chữ bên dưới được chép từ ảnh (Đỗ Quốc An đọc). {e(self.scan_status)}' if scan
                else 'Ảnh cắt trọn dòng dịch vụ, gồm tất cả nhánh và ngoại lệ.')
        text = s['quote'] + ('\n\nTỷ lệ, mức giá thanh toán:\n' + '\n'.join(s['rate']) if s.get('rate') else '')
        page_link = (f'<a href="{e(d["local_url"])}#page={s["page"]}" target="_blank" rel="noopener noreferrer">Mở trang {s["page"]} của bản hợp nhất</a>' if scan
                     else f'<a href="{e(d["local_url"])}#page={s["page"]}" target="_blank" rel="noopener noreferrer">Mở toàn trang PDF {s["page"]}</a>')
        consolidated = '' if scan else f'<a href="/sources/labs/17-vbhn-2024.pdf#page={s["consolidated_pages"][0]}" target="_blank" rel="noopener noreferrer">Đối chiếu bản hợp nhất</a>'
        day = lambda iso: '/'.join(reversed(iso.split('-')))
        return f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(s['name'])} · Trích dẫn nguồn</title><link rel="stylesheet" href="/style.css"></head><body>
<main class="canvas lab-source-page"><a href="/">Về chatbot</a><h1>{e(s['name'])}</h1><p>{e(d['title'])} · {e(s['locator'])}</p>
<section id="source-row" class="panel"><h2>Vị trí trích dẫn trong bản gốc</h2>{body}<p class="hint">{hint}</p><details{" open" if scan else ""}><summary>Đọc nguyên văn dạng chữ</summary><p class="lab-verbatim">{e(text) if verified else 'Nguồn chưa kiểm chứng.'}</p></details></section>
<div class="source-links">{page_link}<a href="{e(d['official_url'])}" target="_blank" rel="noopener noreferrer">Bản công bố chính thức</a>{consolidated}</div>
<p>Áp dụng quy tắc từ {day(d['effective_from'])} · Kiểm tra nguồn {day(d['checked_as_of'])}.</p><p class="hint">{e(d['review_limitations'])}</p><p>{e(d['review_status'])}</p></main></body></html>'''.encode('utf-8')
