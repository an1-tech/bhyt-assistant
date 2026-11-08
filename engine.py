"""Grounded drug lookup and retrieval. Python 3.10+, standard library only."""
from __future__ import annotations
import collections, datetime as dt, difflib, hashlib, hmac, itertools, json, math, os, re, secrets, unicodedata
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from source_review import apply_source_review, effective_fingerprint
from transitions import load_transition_bundle, transition_intent, transition_followup, transition_notice
from retrieval import ContextIndex, prepare_chunks, DRUG_KINDS, RETRIEVAL_VERSION  # noqa: F401

ROOT = Path(__file__).resolve().parent
SNAPSHOT = '2026-11-06'

def normalize(s):
    s = unicodedata.normalize('NFD', str(s).lower().replace('đ', 'd'))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in s if not unicodedata.combining(c))).split())

FOLLOWUP_PREFIXES=("neu ","con ","vay ","the con ","truong hop ","thuoc nay ","thuoc do ")
# Words that make a short message a follow-up about the medicine already under discussion.
FOLLOWUP_WORDS=r"\b(?:ty le|thanh toan|chi tra|dieu kien|xet nghiem|hoi chan|her ?2|egfr|k?ras|nras|cd20|binet|iod|fish|ihc|dot bien|di can|giai doan|tien trien|tai phat|khang|dung nap|that bai|lieu|duong dung)\b"
CONDITION_CUE=r"(?:khang|dung nap|sau|that bai|phu hop|chua dung|da dung|tien trien|tai phat|dap ung|chong chi dinh)[a-z0-9 ]{0,25}\b"
INN_STEM=r"(?:mab|tinib|rafenib|ciclib|parib|lisib|zomib|cept|platin|taxel|rubicin|mycin|vir|pril|sartan|olol|dipine|azole|gliptin|gliflozin|statin|cillin|floxacin)$"
PRODUCT_MODIFIERS=r"emtansine?|deruxtecan|dxd|mcc|dm1|vedotin|ozogamicin|govitecan|mafodotin|tesirine|pegol|duocarmazine|sn-?38"
VIET_SYLLABLE=re.compile(r"^(?:ngh|ng|nh|ch|gh|gi|kh|ph|qu|th|tr|[bcdghklmnprstvx])?[aeiouy]{1,3}(?:ch|ng|nh|[cmnpt])?$")
SALT_WORDS={'acetat','acetate','dimaleat','dimaleate','maleat','maleate','mesylat','mesylate','mesilat','besylat','besylate',
            'tosylat','tosylate','tartrat','fumarat','citrat','succinat','lactat','gluconat','carbonat','nitrat','sulfat','sulphat',
            'hydroclorid','hydrochlorid','hydrobromid','bromid','clorid','phosphat','phosphate','natri','kali','calci','magnesi',
            'meglumin','hydrat','dihydrat','trihydrat','base','peptid'}
# English/clinical words that are never treated as an unrecognised medicine name.
NOT_DRUG_WORDS=set("""stage grade score status type wild mutation mutant positive negative luminal triple please patient case
dose first second third line therapy treatment adjuvant neoadjuvant metastatic advanced early late relapse relapsed refractory
resistant resistance failure failed after before with without what about does insurance covered coverage price cost test result
biopsy tumor tumour cancer breast lung gastric colon rectal liver kidney prostate thyroid lymphoma leukemia hormone receptor
estrogen progesterone exon deletion insertion amplification express expression overexpression brca pdl1 ki67 msi mmr ecog
alk ros1 braf ntrk ret met tnm node nodes lymph distant local regional squamous adeno adenocarcinoma small cell nonsmall
non chemo chemotherapy radiotherapy surgery hospital doctor pharmacy question answer thanks hello
patients mutations mutated testing tested required require philadelphia regimen protocol scheme
folfox folfiri folfirinox xelox capox rchop chop abvd beacop cmf docetaxel-based platinum-based
human analog recombinant""".split())
# Chemistry words inside catalogue names that are not medicines by themselves.
GENERIC_CHEM={'hydroxyd','oxyd','oxid','furoat','propionat','dipropionat','bicarbonat','valerat','methyl','ethyl','polymaltose',
              'complex','sucrose','sucrat','trisilicat','phosphat','hydrogen','dinatri','monohydrat'}

def condition_mention(name,q):
    """The drug name sits inside a condition: "kháng Imatinib" or "Imatinib đáp ứng kém"."""
    return bool(re.search(CONDITION_CUE+re.escape(name)+r"\b",q) or re.search(
        r"\b"+re.escape(name)+r"\b[a-z0-9 ]{0,15}\b(?:dap ung kem|kem dap ung|khong (?:con )?(?:hieu qua|dap ung|dung nap)|that bai|khang|tien trien)\b",q))

def normalize_keep_plus(s):
    s = unicodedata.normalize('NFD', str(s).lower().replace('đ', 'd'))
    return ' '.join(re.sub(r'[^a-z0-9+/&]+', ' ', ''.join(c for c in s if not unicodedata.combining(c))).split())

def has_diacritics(s):
    return any(unicodedata.combining(c) for c in unicodedata.normalize('NFD', str(s))) or 'đ' in str(s).lower()

PRIVATE_RE=(
    re.compile(r'(?<![\w])(?:\+?84|0)(?:[\s.-]?\d){9}(?![\d])'),                       # phone, any spacing
    re.compile(r'(?<![\w])\d{12}(?![\d])'),                                            # CCCD
    re.compile(r'(?<![\w])\d{3}(?:[\s.-]\d{3}){3}(?![\d])'),                           # CCCD written in groups
    re.compile(r'(?<![A-Za-z0-9])[A-Za-z]{2}\s?\d(?:\s?\d){12}(?![\d])'),              # BHYT card (2 letters + 13 digits)
    re.compile(r'(?i)(?:họ tên|họ và tên|tên bệnh nhân|tên người bệnh|ho ten)\s*(?:bệnh nhân\s*)?(?:là\s*)?[:=]?\s*\S'),
    re.compile(r'(?i)(?:mã bệnh án|mã bn|số bệnh án|mã người bệnh|mã hồ sơ|số thẻ bhyt|thẻ bhyt số|mã thẻ bhyt|ma benh an|so the bhyt)\s*(?:là\s*)?[:=]?\s*[A-Za-z0-9]'),
    re.compile(r'(?i)(?:sinh ngày|ngày sinh|sinh năm|sinh|dob)\s*[:=]?\s*\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}'),
)
NAME_LEAD=re.compile(r'(?:[Bb]ệnh nhân|[Nn]gười bệnh|\bBN|\b[Ôô]ng|\b[Bb]à|\b[Cc]hị|\b[Aa]nh)\s*[:\-–]?\s+((?:\w+\s+){1,3}\w+)')
# Capitalised disease names after "Bệnh nhân" are not personal names.
DISEASE_LEAD=re.compile(r'^(?:dai thao duong|ung thu|tang huyet ap|suy tim|viem|benh|hen|lao|nhiem|sot|u |dot quy|xo gan)')

def private_input(message):
    if any(p.search(message) for p in PRIVATE_RE):return True
    # "bệnh nhân Nguyễn Văn An", "BN: Nguyễn Văn An": two or more capitalised words after a person word.
    for m in NAME_LEAD.finditer(message):
        words=m.group(1).split()
        lead=[w for w in words[:3] if w[:1].isupper() and not w.isupper() and w.isalpha()]
        if DISEASE_LEAD.match(normalize(" ".join(words[:3]))):continue
        # Vietnamese personal names: accented or short syllables ("Nguyễn Văn An", "Tran Van An"),
        # not a capitalised drug name ("Trastuzumab Ung thư").
        if len(lead)>=2 and words[0] in lead and words[1] in lead and all(not w.isascii() or len(w)<=6 for w in lead[:2]):
            return True
    return False

def read_jsonl(p):
    return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()]

def load_env(path=None):
    p = path or ROOT/'.env'
    if p.exists():
        for line in p.read_text(encoding='utf-8-sig').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                k,v=line.split('=',1);os.environ.setdefault(k.strip(),v.strip().strip('"').strip("'"))

def api_post(endpoint, payload):
    key=os.environ.get('OPENAI_API_KEY','')
    if not key:raise ValueError('Chưa cấu hình OPENAI_API_KEY.')
    req=Request('https://api.openai.com/v1/'+endpoint,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(req,timeout=45) as r:return json.load(r)
    except HTTPError as e:
        # Never echo API keys, request context or provider response bodies into the UI.
        raise RuntimeError(f'Dịch vụ AI trả HTTP {e.code}.') from None
    except (URLError,TimeoutError):raise RuntimeError('Không kết nối được dịch vụ AI.') from None

class Corpus:
    def __init__(self, data_dir=None):
        self.data=Path(data_dir or ROOT/'data')
        from clinical_sources import ClinicalSources
        self.supplemental=ClinicalSources(self.data)
        self.drugs=read_jsonl(self.data/'drugs_appendix_I.jsonl')
        self.radio=read_jsonl(self.data/'radiopharmaceuticals_appendix_II.jsonl')
        self.rows=self.drugs+self.radio
        self.by_id={r['record_id']:r for r in self.rows}
        raw=read_jsonl(self.data/'rag_current.jsonl')
        self.transition_chunks,self.transition_rules=load_transition_bundle(self.data,self.rows)
        reviewed=apply_source_review(raw, self.data/"source_review.json")
        self.chunks=[c for c in prepare_chunks(reviewed+self.transition_chunks) if self.allowed(c)]
        self.context_index=ContextIndex(self.chunks)
        self.by_chunk={c['id']:c for c in self.chunks}
        self.names={}
        for row in self.rows:self.names.setdefault(normalize(row['ingredient']),[]).append(row)
        # Parenthetical synonyms printed in the source are usable without a brand registry.
        self.source_names={}
        for key, rows in self.names.items():
            name=rows[0]['ingredient']
            if '+' not in name:
                plain=normalize(re.sub(r'\([^)]*\)', '', name))
                if plain and plain != key:self.source_names.setdefault(plain,set()).add(key)
                for group in re.findall(r'\(([^)]+)\)',name):
                    # "(folinic acid, leucovorin)", "(5-FU)"; never a bare salt/ion word like "(sulfat)".
                    for part in group.split(','):
                        p=normalize(part)
                        if len(p)>=3 and re.search(r'[a-z]{2}',p) and not set(p.split())<=SALT_WORDS:
                            self.source_names.setdefault(p,set()).add(key)
                # Written without the space ("Methyl prednisolon" -> "methylprednisolon").
                compact=(plain or key).replace(' ','')
                if compact!=(plain or key) and compact not in self.names:
                    self.source_names.setdefault(compact,set()).add(key)
                # Base name without a trailing salt word ("Afatinib dimaleate" -> "afatinib");
                # never an element/ion on its own ("calci", "magnesi").
                base=re.sub(r'(?:\s+(?:'+'|'.join(sorted(SALT_WORDS))+r'))+$','',plain or key)
                if base and base!=key and len(base)>=5 and base not in self.names and base not in SALT_WORDS:
                    self.source_names.setdefault(base,set()).add(key)
        self.aliases={};self.alias_sources={}
        alias_file=self.data/'aliases.json'
        if alias_file.exists():
            for a in json.loads(alias_file.read_text(encoding='utf-8')):
                # Only verified, sourced brand mappings are usable; never guess from similar names.
                if a.get('verified') is True and str(a.get('source_url','')).startswith('https://') and normalize(a.get('ingredient','')) in self.names:
                    self.aliases[normalize(a['brand'])]=normalize(a['ingredient'])
                    self.alias_sources[normalize(a['brand'])]=a
        self.load_hospital_list()
        self.source_fingerprint=hashlib.sha256((self.data/'rag_current.jsonl').read_bytes()).hexdigest()
        self.fingerprint=effective_fingerprint(self.chunks)
        # TF-IDF sparse vectors support local ranked evidence retrieval without an external API.
        self.counts=[collections.Counter(normalize(c['text']).split()) for c in self.chunks]
        df=collections.Counter(t for counts in self.counts for t in counts)
        self.idf={t:math.log((len(self.chunks)+1)/(n+1))+1 for t,n in df.items()}
        self.vectors=[self.vector(x) for x in self.counts]
        self.semantic_path=self.data/'embeddings.sqlite'
        self._state_key=secrets.token_bytes(32)

    def load_hospital_list(self):
        """Hospital public drug list (website "Danh sách thuốc", data/hospital/). Every entry is
        kept. Only deterministic matches (exact / spelling / salt / combination, see
        tools/match_hospital_list.py) let the hospital spelling find a TT20 row, and the answer
        says which spelling was converted. Presence on the list is shown; absence means nothing."""
        self.hospital={};self.hospital_aliases={};self.hospital_combos=[];self.hospital_other={}
        f=self.data/'hospital'/'hospital_tt20_match.json'
        if not f.exists():return
        doc=json.loads(f.read_text(encoding='utf-8'));usable=set(doc.get('usable_levels',()))
        for r in doc.get('results',[]):
            if r.get('duplicate_of'):continue
            keys=[t['key'] for t in r.get('tt20',[]) if t.get('key') in self.names]
            if r.get('level') in usable and len(keys)==1:
                key=keys[0];self.hospital.setdefault(key,[]).append(r)
                if r['kind']=='combination':
                    parts=[normalize(p) for p in re.split(r'\s*/\s*',r['name']) if normalize(p)]
                    if len(parts)>=2:self.hospital_combos.append((parts,key,r))
                    continue
                alias=normalize(r['name'])
                # Only a spelling the catalogue cannot already resolve ("Paracetamol" already
                # finds "Paracetamol (acetaminophen)" through the printed synonym).
                if r['level']!='exact' and alias and alias!=key and alias not in self.names and alias not in self.aliases and alias not in self.source_names:
                    self.aliases[alias]=key;self.hospital_aliases[alias]=(key,r)
            else:
                self.hospital_other[normalize(r['name'])]=r

    def hospital_combo_matches(self,message):
        """"Amoxicillin/ Clavulanic Acid" as printed on the hospital list: parts joined by
        "+", "/", "&" or "phối hợp" (any order), the same guard as a listed combination."""
        plus=normalize_keep_plus(message);found=[]
        joiner=r'\s*(?:\+|/|&|phoi hop|ket hop)\s*'
        for parts,key,_ in self.hospital_combos:
            for order in itertools.permutations(parts):
                if re.search(r'(?<![a-z0-9])'+joiner.join(re.escape(p) for p in order)+r'(?![a-z0-9])',plus):
                    found.append(key);break
        return found

    def hospital_notes(self,message,result):
        """Notes about the hospital list for the recognised medicines, and for names the list
        has but TT20 does not (product names, other spellings, unlisted ingredients)."""
        q=' '+normalize(message)+' ';notes=[];seen=set()
        tail=' Danh sách này chỉ ghi tên hoạt chất (không có biệt dược, hàm lượng, số đăng ký) nên không xác nhận thuốc đang được cung ứng hay được BHYT thanh toán.'
        combo_hits=self.hospital_combo_matches(message)
        for res in result.get('results') or []:
            key=normalize(res.get('ingredient',''))
            entries=self.hospital.get(key)
            if not entries or key in seen:continue
            seen.add(key)
            text='Danh sách thuốc công khai trên website Vinmec có: '+', '.join('“'+e['text']+'”' for e in entries)+'.'
            for alias,(k,e) in self.hospital_aliases.items():
                if k==key and ' '+alias+' ' in q:
                    text+=f' Đã quy đổi cách viết “{e["name"]}” → “{res["ingredient"]}” (tên trong TT20) theo quy tắc chính tả cố định, không theo tên gần giống.'
            for parts,k,e in self.hospital_combos:
                if k==key and key in combo_hits:
                    text+=f' Đã đối chiếu “{e["name"]}” với dòng phối hợp “{res["ingredient"]}” trong TT20.';break
            for e in entries:
                if e.get('route_hint_in_tt20') is False:
                    routes=', '.join(r2 for t in e['tt20'] for r2 in t['routes'])
                    text+=f' Lưu ý: danh sách bệnh viện ghi đường “{e["route_hint"]}”, còn dòng TT20 chỉ có: {routes}.'
            notes.append(text+tail)
        names=sorted((k for k in self.hospital_other if ' '+k+' ' in q),key=len,reverse=True)
        for k in names:
            if any(' '+k+' ' in ' '+other+' ' for other in names if other!=k):continue   # "Neopeptin" inside "Neopeptin syrup"
            e=self.hospital_other[k];tt=[t['ingredient'] for t in e.get('tt20',[])]
            if e['kind']=='product_name':
                text=f'“{e["text"]}” có trong danh sách thuốc công khai trên website Vinmec nhưng là tên sản phẩm; bộ nguồn chưa có ánh xạ sản phẩm → hoạt chất đã kiểm chứng nên chưa tra được BHYT. Hãy nhập tên hoạt chất.'
                if tt:text+=' Dòng TT20 có in tên này (cần Dược xác nhận đúng sản phẩm): '+', '.join(tt)+'.'
            elif e['level']=='parts':
                found=[t for p in e.get('parts',[]) for t in p['tt20']]
                text=f'“{e["text"]}” có trong danh sách thuốc công khai trên website Vinmec; TT20 không có dòng phối hợp này.'+(' Thành phần thấy riêng trong TT20: '+', '.join(found)+'.' if found else '')
            elif e['level'] in ('review','ambiguous'):
                text=f'“{e["text"]}” có trong danh sách thuốc công khai trên website Vinmec nhưng không khớp chắc một tên trong TT20.'+(' Tên gần nhất (chỉ là gợi ý, cần Dược xác nhận): '+', '.join(tt)+'.' if tt else '')
            else:
                text=f'“{e["text"]}” có trong danh sách thuốc công khai trên website Vinmec, nhưng không tìm thấy tên hoạt chất này trong Phụ lục I/II TT20 của bộ nguồn (đã thử cách viết tiếng Việt).'
            notes.append(text+' Không tìm thấy trong TT20 ở đây chưa đủ để kết luận thuốc không được BHYT thanh toán; cần Dược/BHYT kiểm tra.')
        return notes

    def with_hospital(self,message,result):
        if isinstance(message,str) and not private_input(message):
            notes=self.hospital_notes(message,result)
            if notes:result["hospital_notes"]=notes
        return result

    @staticmethod
    def allowed(c):
        if c.get('default_retrieve') is False:return False
        if c.get('status') in ('draft','repealed','application_deferred_under_article_20_2'):return False
        if c.get('document_id')=='TT37_2024' and c.get('article')==7:return False
        if c.get('document_id','').startswith('TT20') and c.get('article') in (3,4,5,6):return False
        return True

    def vector(self, counts):
        v={t:(1+math.log(n))*self.idf.get(t,0) for t,n in counts.items() if self.idf.get(t,0)}
        mag=math.sqrt(sum(x*x for x in v.values())) or 1
        return {t:x/mag for t,x in v.items()}

    def name_present(self,key,message,q):
        """Exact catalogue name in the message, with two guards: a combination needs
        "+", "/" or "phối hợp" between its parts, and when the user types with
        diacritics an accented name must match with its accents ("còn" ≠ "Cồn")."""
        name=self.names[key][0]['ingredient']
        if '+' in name:return False      # combinations are matched in resolve(), by level
        if ' '+key+' ' not in q:return False
        if not name.isascii() and has_diacritics(message):
            core=' '.join(re.sub(r'[^\w]+',' ',unicodedata.normalize('NFC',name.lower())).split())
            text=' '+' '.join(re.sub(r'[^\w]+',' ',unicodedata.normalize('NFC',message.lower())).split())+' '
            return ' '+core+' ' in text
        return True

    def combo_parts(self):
        """Per combination: (printed name, parts as printed, parts without salt words)."""
        if getattr(self,"_combos",None) is None:
            self._combos={}
            for key,rows in self.names.items():
                name=rows[0]['ingredient']
                if '+' not in name:continue
                full=[normalize_keep_plus(p).strip() for p in re.sub(r'\([^)]*\)','',name).split('+')]
                bare=[' '.join(w for w in p.split() if w not in SALT_WORDS) for p in full]
                self._combos[key]=(normalize_keep_plus(name),[p for p in full if p],[p for p in bare if p])
        return self._combos

    def combo_matches(self,message):
        """Listed combinations named in the message, strictest level first: the printed
        name; its parts in printed order joined by "+", "/", "&" or "phối hợp"; the parts
        in any order; the parts without salt words. A looser level is only used when no
        combination matched at a stricter one, so "A + B + C" never also matches "C + A + B"
        and "Sắt fumarat + acid folic" never matches "Sắt sulfat + acid folic"."""
        plus=normalize_keep_plus(message);bare=' '.join(w for w in plus.split() if w not in SALT_WORDS)
        words=set(plus.replace('+',' ').replace('/',' ').replace('&',' ').split())
        joiner=r'\s*(?:\+|/|&|phoi hop|ket hop)\s*'
        def joined(parts,text,orders):
            return any(re.search(r'(?<![a-z0-9])'+joiner.join(re.escape(p) for p in o)+r'(?![a-z0-9])',text) for o in orders)
        combos=self.combo_parts()
        # Level 0: the printed name, whatever its shape (brackets, "/", many parts).
        found=[key for key,(printed,_,_) in combos.items() if ' '+printed+' ' in ' '+plus+' ']
        if found:return found
        for level in range(1,4):
            found=[]
            for key,(printed,full,bare_parts) in combos.items():
                parts=bare_parts if level==3 else full
                if not 2<=len(parts)<=4 or not all(set(re.split(r'[\s/]+',p))<=words for p in parts):continue
                if level==1:ok=joined(parts,plus,[parts])
                elif level==2:ok=joined(parts,plus,itertools.permutations(parts))
                else:ok=joined(parts,bare,itertools.permutations(parts))
                if ok:found.append(key)
            if found:return found
        return []

    def resolve(self, message):
        q=' '+normalize(message)+' '
        direct=[k for k in self.names if self.name_present(k,message,q)]+self.combo_matches(message)+self.hospital_combo_matches(message)
        hits=list(direct)
        hits.extend(self.aliases[k] for k in self.aliases if ' '+k+' ' in q)
        for short,keys in self.source_names.items():
            if ' '+short+' ' in q and len(keys)==1 and not any(' '+short+' ' in ' '+k+' ' for k in direct):hits.extend(keys)
        hits=list(dict.fromkeys(hits))
        if not hits:
            # "Tegafur gimeracil oteracil": every part of a listed combination, in order,
            # without the salt word, and no single ingredient matched.
            for key,rows in self.names.items():
                name=rows[0]['ingredient']
                if '+' not in name:continue
                parts=[' '.join(w for w in normalize(p).split() if w not in SALT_WORDS) for p in re.sub(r'\([^)]*\)','',name).split('+')]
                if all(parts) and len(parts)>=3 and re.search(r'\b'+r'\s+'.join(re.escape(p) for p in parts)+r'\b',q):hits.append(key)
        # A listed combination takes priority over the separately listed ingredients.
        def spans(key):
            return [key]+[short for short,keys in self.source_names.items() if key in keys]
        hits=[k for k in hits if not any(k!=other and ' '+k+' ' in ' '+other+' ' for other in hits)]
        return [self.names[k] for k in sorted(hits,key=lambda k:min([q.find(' '+x+' ') for x in spans(k) if ' '+x+' ' in q] or [len(q)]))]

    def detect_route(self,message):
        q=' '+normalize(message)+' '
        # "dùng ngoài ung thư" / "ngoài chỉ định" describe scope, not the external route.
        q=re.sub(r' (?:dung )?ngoai (?=(?:ung thu|chi dinh|benh|pham vi|nhung|cac|truong hop|muc dich|dieu tri|nhan|huong dan) )',' pham vi khac ',q)
        for phrase in ("tiem truyen","truyen tinh mach","tiem tinh mach","tiem bap","tiem duoi da"):
            q=q.replace(" "+phrase+" "," tiem ")
        # Keep specific routes ahead of their parent route (e.g. intravitreal vs injection).
        routes=['Đặt', 'Tiêm trong dịch kính','Bơm vào khoang màng phổi','Dung dịch thẩm phân',
                'Đặt dưới lưỡi','Đặt tử cung','Đặt âm đạo','Thụt hậu môn','Nhỏ mắt',
                'Nhỏ tai','Nhỏ mũi','Xịt mũi','Xịt họng','Dán ngoài da','Dùng ngoài',
                'Khí dung','Dạng hít','Đường hô hấp','Đường nội khí quản','Ngậm','Uống','Tiêm']
        # Include every literal route from the supplied source, split only at commas.
        candidates={normalize(x):x for x in routes}
        for row in self.rows:
            for part in row['route'].split(','):
                if part.strip():candidates.setdefault(normalize(part),part.strip())
        routes=sorted(candidates.values(),key=lambda x:len(normalize(x)),reverse=True)
        aliases={'tiem truyen':'Tiêm','truyen tinh mach':'Tiêm','truyen':'Tiêm',
                 'tra mat':'Nhỏ mắt','dat hau mon':'Thụt hậu môn','boi ngoai da':'Dùng ngoài',
                 'boi da':'Dùng ngoài','hit':'Dạng hít'}
        hits=[];remaining=q
        for phrase,route in [(normalize(x),x) for x in routes]+list(aliases.items()):
            if ' '+phrase+' ' in remaining:
                hits.append(route);remaining=remaining.replace(' '+phrase+' ',' ')
        return list(dict.fromkeys(hits))

    @staticmethod
    def route_matches(selected,stored):
        q=' '+normalize(stored)+' ';needle=' '+normalize(selected)+' '
        if needle in q:return True
        if normalize(selected) in {"tiem truyen","truyen tinh mach","tiem tinh mach","tiem bap","tiem duoi da"} and normalize(stored)=="tiem":return True
        synonyms={'Nhỏ mắt':['tra mat'],'Thụt hậu môn':['dat hau mon','truc trang'],
                  'Dạng hít':['duong ho hap'],'Đường hô hấp':['dang hit','khi dung'],
                  'Dùng ngoài':['boi am dao','dan ngoai da','xit ngoai da']}
        return any(' '+x+' ' in q for x in {normalize(k):v for k,v in synonyms.items()}.get(normalize(selected),[]))

    def suggestions(self, message):
        q=normalize(message)
        q=re.sub(r'\b(thuoc|co|duoc|huong|bao|hiem|y|te|bhyt|khong|tra|cuu|chi|thanh|toan|la|gi)\b',' ',q)
        q=' '.join(q.split())
        if len(q)<4:return []
        keys=difflib.get_close_matches(q,self.names.keys(),n=4,cutoff=.75)
        return [self.names[k][0]['ingredient'] for k in keys]

    def search(self, query, limit=5, policies_only=False, distinct_parents=False):
        if limit <= 0:return []
        q=self.vector(collections.Counter(normalize(query).split()))
        scored=[]
        for i,(c,v) in enumerate(zip(self.chunks,self.vectors)):
            if policies_only and c['kind'] in ('drug_row','radiopharmaceutical_row'):continue
            score=sum(w*v.get(t,0) for t,w in q.items())
            if score>.035:scored.append((score,c))
        scored.sort(key=lambda r:r[0],reverse=True)
        if not distinct_parents:return [c for _,c in scored[:limit]]
        selected=[];seen=set()
        for _,c in scored:
            key=self.context_index.parent[c['id']]
            if key in seen:continue
            selected.append(c);seen.add(key)
            if len(selected)>=limit:break
        return selected

    def policy_search(self, query, limit=4):
        seeds=self.search(query,limit,True,distinct_parents=True)
        if transition_intent(normalize(query)):
            seeds=self.transition_chunks+seeds
        return self.complete_context(seeds)

    def semantic_search(self, query, limit=4):
        from ai_explain import semantic_search
        return semantic_search(self, query, limit)

    def policy_context(self, query, oncology=False):
        # Mandatory context first; all continuations belong to the same article.
        selected=[]
        for a in ([8,10,12,20] if oncology else [8,10,20]):
            selected.extend(c for c in self.chunks if c.get('document_id')=='TT37_2024' and c.get('article')==a)
        if oncology:
            selected.extend(c for c in self.chunks if c.get('document_id')=='CV3293_2025')
        found=self.search(query,3,True,distinct_parents=True)
        if transition_intent(normalize(query)):
            selected=self.transition_chunks+selected+found
        else:
            # Lexical matches on common words ("nếu… thì") must not pull the transition
            # article into a drug answer; mapped drugs add it explicitly in chat().
            transition_ids={c["id"] for c in self.transition_chunks}
            selected+=[c for c in found if c["id"] not in transition_ids]
        return self.complete_context(selected)

    def complete_context(self, seeds):
        selected=list(seeds)
        if any(c.get("id") in self.transition_rules["article8_ids"] for c in selected):
            selected+=self.transition_chunks
        return self.context_index.expand(selected)

    def citation(self,c):
        return {k:c.get(k) for k in ['id','document_id','locator','source_url','official_url','page','checked_as_of','article','kind','review_status','source_review','source_review_flags','scope','legal_status_review']} | {'excerpt':c['text']}

    def chat(self,message,state=None,as_of=None,*,allow_ai=True):
        message=message.strip();state=state or {}
        if not message or len(message)>3000:raise ValueError('Nhập câu hỏi từ 1 đến 3.000 ký tự.')
        if not isinstance(state,dict):raise ValueError('Trạng thái hội thoại không hợp lệ.')
        day=as_of or SNAPSHOT
        try:dt.date.fromisoformat(day)
        except (ValueError,TypeError):raise ValueError('Ngày tra cứu không hợp lệ.')
        base=dict(snapshot=SNAPSHOT,mode='local',citations=[],results=[],suggestions=[],followups=[],state={})
        if day!=SNAPSHOT:
            return base|dict(status='unsupported_date',answer=f'Bộ nguồn này được chốt ngày 06/11/2026. Chưa đủ dữ liệu phiên bản để trả lời cho ngày {day}. Hãy dùng ngày của bộ nguồn hoặc cập nhật dữ liệu tương ứng.')
        if private_input(message):
            return base|dict(status='private_input',answer='Bạn chỉ cần nhập tên thuốc, hoạt chất và bối cảnh không định danh. Vui lòng bỏ họ tên, ngày sinh, số điện thoại, mã bệnh án hoặc số thẻ BHYT trước khi tra cứu.')
        groups=self.resolve(message)
        if len(groups)>8:
            return base|dict(status='needs_info',answer='Bạn đang tra hơn 8 hoạt chất. Hãy chia thành từng nhóm tối đa 8 để đối chiếu riêng từng thuốc.')
        if not isinstance(state.get("context",""),str) or len(state.get("context",""))>1000:raise ValueError("Bối cảnh hội thoại không hợp lệ.")
        if not isinstance(state.get("selected_ids",[]),list) or not all(isinstance(x,str) for x in state.get("selected_ids",[])):raise ValueError("Danh sách thuốc không hợp lệ.")
        if state.get("route") is not None and not isinstance(state["route"],str):raise ValueError("Đường dùng không hợp lệ.")
        previous=[self.by_id[x] for x in state.get('selected_ids',[])[:20] if x in self.by_id] if isinstance(state.get('selected_ids',[]),list) else []
        q=normalize(message)
        detected_routes=self.detect_route(message)
        if len(detected_routes)>1 and groups:
            if len(groups)==1:
                # One medicine, several routes: each button is a complete one-route question, so it cannot loop.
                return base|dict(status='needs_info',answer='Bạn đã nêu nhiều đường dùng. Hãy tra từng thuốc kèm một đường dùng để tránh áp nhầm điều kiện.',
                                 suggestions=[f"{groups[0][0]['ingredient']} {r.lower()}" for r in detected_routes[:4]],suggestion_mode='replace',state={})
            return base|dict(status='needs_info',answer='Bạn đã nêu nhiều đường dùng. Hãy tra từng thuốc kèm một đường dùng để tránh áp nhầm điều kiện.',suggestions=[g[0]['ingredient'] for g in groups],state={})
        route=detected_routes[0] if detected_routes else None
        related_followup=(len({r["ingredient"] for r in previous})==1
            and any(r["record_id"] in self.transition_rules["mapping"] for r in previous)
            and transition_followup(q))
        is_followup=bool(not groups and previous and (route or related_followup or q.startswith(('ung thu','dieu tri','chi dinh','her2','benh ','chan doan','tang huyet ap','dai thao duong','nhiem khuan','suy tim','hen ','copd','viem '))))
        same_drugs=bool(groups and previous and {r["ingredient"] for g in groups for r in g}=={r["ingredient"] for r in previous})
        is_followup=is_followup or same_drugs
        if is_followup:
            if not groups:
                by_name={}
                for row in previous:by_name.setdefault(row["ingredient"],[]).append(row)
                groups=list(by_name.values())
            route=route or state.get('route')
        if not groups:
            suggested=self.suggestions(message)
            if suggested:return base|dict(status='ambiguous',answer='Chưa xác định chắc tên thuốc. Bạn chọn đúng hoạt chất dưới đây để tiếp tục; mình chưa kết luận BHYT từ tên gần giống.',suggestions=suggested)
            terms=normalize(message).split()
            if not transition_intent(q) and not any(t in terms for t in ['bhyt','thuoc','bao','hiem','thanh','toan','ung','thu']):
                return base|dict(status='unknown',answer='Chưa nhận diện được thuốc trong bộ danh mục. Bạn nhập tên hoạt chất hoặc kiểm tra lại tên thuốc. Không tìm thấy ở đây chưa đủ để kết luận thuốc không được BHYT thanh toán.')
            evidence=self.policy_search(message,4)
            if not evidence:return base|dict(status='unknown',answer='Chưa đủ căn cứ kết luận. Hãy nhập tên hoạt chất hoặc nêu rõ câu hỏi về điều kiện BHYT.')
            result=base|dict(status='policy_lookup',answer='Mình tìm được các đoạn quy định liên quan bên dưới. Cần nêu tên hoạt chất nếu bạn muốn tra một thuốc cụ thể.',citations=[self.citation(c) for c in evidence])
            return self.add_ai(result,message,evidence) if allow_ai else self.with_transition_context(result,evidence)
        evidence=[];results=[];original_ids=[r['record_id'] for g in groups[:8] for r in g]
        # Multiple distinct medications retain separate results; never mix their conditions.
        for group in groups[:8]:
            if route:
                matching=[r for r in group if self.route_matches(route,r['route'])]
                if matching:group=matching
                else:
                    results.append(dict(ingredient=group[0]['ingredient'],status='route_unmatched',routes=sorted(set(r['route'] for r in group)),conditions=[],message='Đường dùng vừa nhập không khớp các dòng đã tìm thấy. Cần kiểm tra lại trước khi đối chiếu.'))
                    continue
            conditions=list(dict.fromkeys(r.get('conditions_verbatim','') for r in group if r.get('conditions_verbatim')))
            route_choices=sorted(set(r['route'] for r in group))
            for r in group:
                c=self.by_chunk.get(r['record_id'])
                if c:evidence.append(c)
            oncology=any(r.get('group','').startswith('8.') for r in group)
            if any(r["record_id"] in self.transition_rules["mapping"] for r in group):
                evidence.extend(self.transition_chunks)
            evidence.extend(self.policy_context(message,oncology))
            results.append(dict(ingredient=group[0]['ingredient'],status='listed_requires_context',routes=route_choices,conditions=conditions,
                message='Có bản ghi trong danh mục. Việc thanh toán còn phụ thuộc điều kiện sử dụng và phạm vi áp dụng.',
                stt=group[0]['stt'],appendix=group[0].get('appendix','I'),
                empty_note=not conditions,record_ids=[r['record_id'] for r in group],
                need_route=(len(route_choices)>1 or any(',' in x or '/' in x for x in route_choices)) and route is None))
        if not any(r.get('record_ids') for r in results):
            return base|dict(status='needs_info',answer='Cần kiểm tra đường dùng trước khi đối chiếu BHYT.',results=results,state={'selected_ids':original_ids,'context':'','route':None},followups=sorted(set(r for x in results for r in x.get('routes',[])))[:10])
        evidence=list({x['id']:x for x in evidence}.values())
        answer='Đã tìm thấy thuốc trong danh mục nguồn. Xem điều kiện cụ thể dưới đây; kết quả này chưa xác nhận quyền lợi thanh toán của một người bệnh cụ thể.'
        followups=[]
        if len(results)==1 and results[0].get('need_route'):
            answer+=' Bạn đang dùng đường nào?';followups=list(dict.fromkeys(x.strip() for route_text in results[0]['routes'] for x in route_text.split(',')))
        elif any(r['conditions'] for r in results):
            answer+=' Thuốc được dùng cho bệnh/chỉ định nào? Bạn có thể bổ sung bối cảnh không định danh để đối chiếu căn cứ.'
        else:
            answer+=' Ô ghi chú trống không có nghĩa quỹ thanh toán 100%; vẫn phải đối chiếu quy định chung và dữ liệu tại cơ sở.'
        ids=[id for r in results for id in r.get('record_ids',[])]
        context=state.get('context','') if is_followup else ''
        if is_followup:context=(str(context)+'; '+message)[-1000:]
        if is_followup and context:
            answer+=' Bối cảnh đã ghi nhận: '+context.strip('; ')+' . Bản tra cứu cục bộ chưa tự đánh giá đủ các điều kiện lâm sàng; hãy đối chiếu nguyên văn và hồ sơ tại cơ sở.'
        result=base|dict(status='needs_info',answer=answer,results=results,citations=[self.citation(c) for c in evidence],followups=followups,state={'selected_ids':ids,'context':context,'route':route})
        return self.add_ai(result,message,evidence) if allow_ai else self.with_transition_context(result,evidence)

    def with_transition_context(self,result,evidence):
        self.attach_transition_review(result,evidence)
        return result

    # ---- Signed conversation state -------------------------------------------------
    # The browser keeps the state, so it is signed with a per-process key. A state that
    # is unsigned, tampered with or from an earlier server run is dropped (new chat):
    # facts, turns and selected medicines can only come from this server's own answers.
    def _state_sig(self,state):
        payload=json.dumps(state,ensure_ascii=False,sort_keys=True,separators=(",",":"))
        return hmac.new(self._state_key,payload.encode(),hashlib.sha256).hexdigest()

    def verify_state(self,state):
        if not isinstance(state,dict) or not state:return {}
        body={k:v for k,v in state.items() if k!="sig"}
        sig=state.get("sig")
        if not isinstance(sig,str) or not hmac.compare_digest(sig,self._state_sig(body)):return {}
        return body

    def sign_state(self,state):
        body={k:v for k,v in (state or {}).items() if k!="sig"}
        return body|{"sig":self._state_sig(body)} if body else {}

    def converse(self,message,state=None,as_of=None,confirm=None):
        """One chat turn: verify the signed state, block identifiers on every path,
        answer, then sign the new state."""
        trusted=self.verify_state(state)
        if isinstance(message,str) and private_input(message):
            result=self.chat(message,{},as_of,allow_ai=False)          # private_input reply, nothing stored
        elif as_of is not None and as_of!=SNAPSHOT:
            result=self.chat(message,{},as_of,allow_ai=False)          # unsupported_date on every path
        else:
            result=self._converse(message,trusted,as_of,confirm)
        result["state"]=self.sign_state(result.get("state") or {})
        return result

    def _converse(self,message,state=None,as_of=None,confirm=None):
        from indication_chat import IndicationChat, topics_in
        # Short conversational follow-ups can retain a single medicine, even with
        # prefixes such as "còn", "vậy" or "nếu". A newly named medicine resets it.
        answerer=getattr(self,"_indication_chat",None)
        if answerer is None:
            answerer=self._indication_chat=IndicationChat(self)
        if confirm is not None:
            return self.confirm_fact(message,state,as_of,confirm,answerer)
        lookup_message=message;named_drug=None;unrecognized=[]
        valid=isinstance(message,str) and 0<len(message.strip())<=3000 and not private_input(message)
        if valid:
            hits=self.resolve(message)
            q=normalize(message)
            # "Paclitaxel gắn albumin" (nab-paclitaxel) is a paclitaxel formulation, not Albumin infusion.
            nab=bool(re.search(r"\b(?:gan|bound|nab)\s?albumin\b|\balbumin bound\b|\bnab paclitaxel\b",q))
            if nab:
                hits=[g for g in hits if normalize(g[0]["ingredient"])!="albumin"]
                lookup_message=re.sub(r"(?i)albumin","(gắn protein)",lookup_message)
            all_hits=list(hits)
            # "Trastuzumab emtansine" is another medicine, not Trastuzumab.
            variant=self.product_variant(message,hits)
            if variant:
                return self.finalize_status(answerer.enrich(self.unrecognized_result([variant[0]],variant[1]),message,state))
            related=self.condition_drugs(message,hits,answerer.rules)
            if related:
                # "Nilotinib ... kháng Imatinib": Imatinib is part of the condition, not a second medicine.
                for name in related:lookup_message=re.sub(re.escape(name),"thuốc trước",lookup_message,flags=re.I)
                hits=[g for g in hits if g[0]["ingredient"] not in related]
            previous=[self.by_id[x] for x in state.get("selected_ids",[])[:20] if isinstance(x,str) and x in self.by_id] if isinstance(state,dict) and isinstance(state.get("selected_ids"),list) else []
            prev_names=list(dict.fromkeys(r["ingredient"] for r in previous))[:8]
            single=previous[0] if len(prev_names)==1 else None
            related_followup=False
            if hits and single:
                # Asked about Nilotinib, then "Nếu kháng Imatinib?": still Nilotinib.
                # "Còn Imatinib thì sao?" (no condition word) switches to Imatinib.
                names={g[0]["ingredient"] for g in hits}
                rel=set(answerer.rules.get(single["record_id"],{}).get("related_drugs",[]))
                if single["ingredient"] not in names and names<=rel and all(condition_mention(normalize(n),q) for n in names):
                    for name in names:lookup_message=re.sub(re.escape(name),"thuốc trước",lookup_message,flags=re.I)
                    hits=[];related_followup=True
            unrecognized=[t for t in self.unrecognized_names(message,all_hits) if not (nab and normalize(t)=="albumin")]
            if unrecognized and not hits:
                # Never answer an unknown medicine with the previous medicine's rules.
                # Choices: catalogue names containing the word ("insulin" → insulin rows), then
                # near-identical spellings ("Paclitaxen"); "Pertuzumab" is not "Trastuzumab".
                suggested=[n for t in unrecognized for n in self.lexicon_matches(normalize(t))]
                suggested+=[self.names[k][0]["ingredient"] for t in unrecognized
                            for k in difflib.get_close_matches(normalize(t),self.names.keys(),n=3,cutoff=.85)]
                suggested=list(dict.fromkeys(suggested))[:6]
                return self.finalize_status(self.with_hospital(message,answerer.enrich(self.unrecognized_result(unrecognized,suggested=suggested),message,state)))
            if hits and prev_names and q.startswith(("thuoc nay ","thuoc do ")):
                # "Thuốc này dùng phối hợp với docetaxel được không": keep the medicine under discussion too.
                lookup_message=" ".join(n for n in prev_names if n not in {g[0]["ingredient"] for g in hits})+" "+lookup_message
            if prev_names and not hits and (related_followup or topics_in(message) or re.search(r"\b(?:her[ -]?2|egfr)\b",message,re.I)
                    or re.search(r"\b(?:ung thu|benh|dai thao duong|tang huyet ap|viem|nhiem khuan|suy tim|hen|copd|dieu tri)\b",q)
                    or q.startswith(FOLLOWUP_PREFIXES) or re.search(FOLLOWUP_WORDS,q)):
                # Applies to every medicine of the previous answer (one or several).
                lookup_message=" ".join(prev_names)+" "+lookup_message
            named_drug=bool(hits)
            # "Erlotinib NSCLC" → "Còn gefitinib?": keep the disease, change the medicine.
            carry_prior=bool(hits and previous and q.startswith(("con ","vay ","the con ","con thuoc ")) and not topics_in(message))
        # General coverage answers use source-bound templates; no external AI call.
        result=self.chat(lookup_message,state,as_of,allow_ai=False)
        result=answerer.enrich(result,message,state,named_drug=named_drug,carry_prior=valid and carry_prior)
        notes=self.brand_notes(message)
        if notes and result.get("results"):result["brand_notes"]=notes
        notices=[]
        if unrecognized and result.get("results"):
            result["unrecognized"]=unrecognized
            notices.append("Chưa nhận ra trong danh mục: "+", ".join(unrecognized)+"; câu trả lời chỉ áp dụng cho thuốc đã nhận diện.")
        if valid and result.get("results"):
            notices+=self.combination_notices(message,result)
        if notices:result["notice"]=" ".join([result.get("notice","")]+notices).strip()
        return self.finalize_status(self.with_hospital(message,result))

    def confirm_fact(self,message,state,as_of,confirm,answerer):
        """A confirmation button: record one fact for the medicine under discussion and answer again.
        The fact always wins over text reading; nothing is inferred from the button label."""
        if not isinstance(confirm,dict) or not isinstance(confirm.get("key"),str) or not isinstance(confirm.get("value"),str):
            raise ValueError("Xác nhận không hợp lệ.")
        parts=confirm["key"].split("|")
        if len(parts)!=3:raise ValueError("Xác nhận không hợp lệ.")
        rid,topic,marker=parts;rule=answerer.rules.get(rid)
        ids=state.get("selected_ids",[]) if isinstance(state,dict) else []
        if not rule or not isinstance(ids,list) or rid not in ids:
            raise ValueError("Xác nhận không thuộc thuốc đang trao đổi. Hãy hỏi lại.")
        if topic=="formulation":
            if rule["kind"]!="formulation_note" or marker!="value" or confirm["value"] not in {f["value"] for f in rule["formulations"]}:
                raise ValueError("Xác nhận không hợp lệ.")
        else:
            branch=next((b for b in rule.get("branches",[]) if b["topic"]==topic),None)
            if not branch or marker not in {r["marker"] for r in branch.get("requirements",[])} or confirm["value"] not in ("met","not_met","unknown"):
                raise ValueError("Xác nhận không hợp lệ.")
        name=self.by_id[rid]["ingredient"]
        result=self.chat(name,state,as_of,allow_ai=False)
        result=answerer.enrich(result,message if isinstance(message,str) else "",state,confirm={"key":confirm["key"],"value":confirm["value"]})
        return self.finalize_status(result)

    def combination_notices(self,message,result):
        """Separately named ingredients that also exist as a listed combination."""
        q=' '+normalize(message)+' ';answered={r["ingredient"] for r in result["results"]};out=[]
        for key,rows in self.names.items():
            name=rows[0]["ingredient"]
            if '+' not in name or name in answered:continue
            parts=[' '.join(w for w in normalize(p).split() if w not in SALT_WORDS) for p in re.sub(r'\([^)]*\)','',name).split('+')]
            if all(parts) and all(' '+p+' ' in q for p in parts):
                out.append(f"Danh mục còn có dạng phối hợp “{name}”; nếu ý bạn là thuốc phối hợp, hỏi lại với dấu “+” (ví dụ “{name}”).")
        return out[:2]

    @staticmethod
    def condition_drugs(message,hits,rules):
        """Drugs named only as part of another drug's payment condition in this message."""
        if len(hits)<2:return set()
        q=normalize(message)
        if re.search(r"\b(?:so sanh|khac nhau|khac gi|hay la|thay the|doi chieu|nen chon)\b",q):return set()
        names={g[0]["ingredient"] for g in hits};found=set()
        for g in hits:
            main=normalize(g[0]["ingredient"])
            for row in g:
                for name in rules.get(row["record_id"],{}).get("related_drugs",[]):
                    rel=normalize(name)
                    # "Imatinib hay/hoặc/và Nilotinib": two medicines being compared.
                    joined=re.search(r"\b"+re.escape(main)+r"\s+(?:hay|hoac|va|voi|hay la|so voi)\s+"+re.escape(rel)+r"\b|\b"+re.escape(rel)+r"\s+(?:hay|hoac|va|voi|hay la|so voi)\s+"+re.escape(main)+r"\b",q)
                    if name in names and name!=g[0]["ingredient"] and not joined and condition_mention(rel,q):found.add(name)
        return found if names-found else set()

    def vocabulary(self):
        """Words that are known not to be an unrecognised medicine name."""
        if getattr(self,"_vocab",None) is None:
            from indication_chat import TOPICS
            words=set()
            for r in self.rows:
                words.update(normalize(r["ingredient"]).split());words.update(normalize(r.get("conditions_verbatim","")).split())
            for k in list(self.aliases)+list(self.source_names):words.update(k.split())
            for label,_ in TOPICS.values():words.update(normalize(label).split())
            words.update("bhyt bhxh her2 egfr ras kras nras cd20 ihc fish cml cll gist nsclc sclc hcc rcc nhl icd type wild positive negative liposome micelle".split())
            self._vocab=words
        return self._vocab

    def drug_lexicon(self):
        """Words that occur in catalogue medicine names (e.g. "interferon", "insulin",
        "lopinavir", "codein"). Seeing one that is not part of a recognised name means
        the user is talking about another medicine — never answer with the previous one."""
        if getattr(self,"_lexicon",None) is None:
            words=set()
            for r in self.rows:
                for w in normalize(r["ingredient"]).split():
                    if len(w)>=5 and w.isalpha() and not VIET_SYLLABLE.match(w) and w not in SALT_WORDS and w not in NOT_DRUG_WORDS and w not in GENERIC_CHEM:
                        words.add(w)
            self._lexicon=words
        return self._lexicon

    def lexicon_matches(self,word):
        """Catalogue names that contain the word, as choices for the user."""
        return [rows[0]["ingredient"] for key,rows in self.names.items() if ' '+word+' ' in ' '+key+' '][:6]

    def unrecognized_names(self,message,hits=()):
        """Words that look like a medicine name but match nothing recognised in this message:
        catalogue name words not covered by a recognised name, INN stems, brand-like words
        (any case) that are not Vietnamese syllables or known clinical words, and codes such
        as "T-DM1" or "TS-1". Mutation codes, regimens and biomarkers are not medicines."""
        vocab=self.vocabulary();lexicon=self.drug_lexicon();found=[]
        covered=set()
        for g in hits:
            for r in g:
                covered.update(normalize(r["ingredient"]).split())
            # The hospital spelling of a recognised medicine ("Amoxicillin/ Clavulanic Acid").
            for e in self.hospital.get(normalize(g[0]["ingredient"]),[]):
                covered.update(normalize(e["name"]).split())
        for t in re.findall(r"[^\s,.;:!?()\[\]\"'“”‘’]+",message):
            t=t.strip("-+/")
            lw=t.lower();nt=normalize(t)
            if not t or not t.isascii() or lw in NOT_DRUG_WORDS or lw in SALT_WORDS:continue
            if nt and set(nt.split())<=covered:continue
            if nt in lexicon:found.append(t);continue
            if lw in vocab or nt in vocab:continue
            compact=nt.replace(' ','')
            if compact in vocab or compact in NOT_DRUG_WORDS:continue
            # Mutation codes (L858R, G12C, T790M), biomarkers and staging codes are not medicines.
            if re.fullmatch(r"[a-z]\d{2,4}[a-z]|del\d{1,2}|ex(?:on)?\d{1,2}",lw.replace('-','')):continue
            code=bool(re.fullmatch(r"[A-Za-z]{1,4}-?\d{1,3}[A-Za-z]?|[A-Za-z]-[A-Za-z]{1,3}\d|\d-[A-Za-z]{2,3}",t)) and not re.fullmatch(r"(?:her|cd|ki|ihc|egfr|pd|pdl|ca|cea|ecog|t|n|m|g|v|ps|brca|msi|ct|pt)\d+[a-z0-9]*",lw.replace('-',''))
            if code:found.append(t);continue
            if len(t)<5 or not t.isalpha():continue
            stem=re.search(INN_STEM,lw)
            wordlike=not VIET_SYLLABLE.match(lw)
            if stem or wordlike:found.append(t)
        return list(dict.fromkeys(found))

    @staticmethod
    def product_variant(message,hits):
        for g in hits:
            name=g[0]["ingredient"]
            # "Trastuzumab deruxtecan", "trastuzumab-deruxtecan", "Trastuzumab (deruxtecan)".
            m=re.search(re.escape(name)+r"[\s\-(\[]+("+PRODUCT_MODIFIERS+r")\b",message,re.I)
            if m:return (message[m.start():m.end()],name)
        return None

    def unrecognized_result(self,names,base=None,suggested=None):
        if suggested:
            # A probable misspelling ("Paclitaxen"): offer the catalogue names, conclude nothing.
            return dict(snapshot=SNAPSHOT,mode='local',citations=[],results=[],suggestions=list(suggested),followups=[],state={},
                        status='ambiguous',unrecognized=list(names),
                        answer="Chưa xác định chắc tên thuốc “"+", ".join(names)+"”. Bạn chọn đúng hoạt chất dưới đây để tiếp tục; mình chưa kết luận BHYT từ tên gần giống.")
        if base:
            answer=(f"“{names[0]}” là thuốc khác với “{base}” trong danh mục BHYT. Bộ nguồn chưa có dòng riêng cho thuốc này nên chưa kết luận, "
                    f"và không dùng điều kiện của {base} cho thuốc này. Không tìm thấy ở đây chưa đủ để kết luận thuốc không được BHYT thanh toán.")
        else:
            answer=("Chưa nhận ra thuốc “"+", ".join(names)+"” trong danh mục BHYT của bộ nguồn. Bot không dùng thuốc đang hỏi trước đó để trả lời. "
                    "Hãy nhập tên hoạt chất; không tìm thấy ở đây chưa đủ để kết luận thuốc không được BHYT thanh toán.")
        return dict(snapshot=SNAPSHOT,mode='local',citations=[],results=[],suggestions=[],followups=[],state={},
                    status='unknown_drug',answer=answer,unrecognized=list(names))

    def brand_notes(self,message):
        q=' '+normalize(message)+' ';notes=[]
        for key,a in self.alias_sources.items():
            if ' '+key+' ' in q:
                notes.append(f"Đã quy đổi biệt dược {a['brand']} → hoạt chất {a['ingredient']} theo {a.get('source_title') or a['source_url']} ({a['source_url']}). {a.get('verification_scope','')}".strip())
        return notes

    @staticmethod
    def finalize_status(result):
        # "status" describes the reply for chat clients; the raw lookup state stays in lookup_status.
        result["lookup_status"]=result.get("status")
        if result.get("results") and result.get("answer_status"):
            result["status"]="answered"
        return result

    def attach_transition_review(self,result,evidence):
        if not any(c["id"] in self.transition_rules["article8_ids"] for c in evidence):
            return False
        evidence=self.complete_context(evidence)
        result["citations"]=[self.citation(c) for c in evidence]
        result["notice"]=transition_notice(self.transition_rules,result)
        result["transition_review"]={"status":"source_available_requires_case_review",
            "review_date":self.transition_rules["review_date"],
            "article8_ids":self.transition_rules["article8_ids"],
            "effective_date_id":self.transition_rules["effective_date_id"],
            "eligibility_evaluated":False,"hospital_validation":"pending",
            "linked_drugs":[{"record_id":id,**self.transition_rules["mapping"][id]}
                for row in result.get("results",[]) for id in row.get("record_ids",[])
                if id in self.transition_rules["mapping"]]}
        # Free-form AI payment reasoning stays off until historical rates and
        # clinical-case handling have been validated. Local source lookup works.
        return True

    def add_ai(self,result,message,evidence):
        # Legacy optional AI explanation; converse() never reaches it.
        from ai_explain import add_ai
        return add_ai(self,result,message,evidence)
