"""Grounded drug lookup and retrieval. Python 3.10+, standard library only."""
from __future__ import annotations
import collections, datetime as dt, difflib, hashlib, json, math, os, re, unicodedata
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
                for part in re.findall(r'\(([^)]+)\)',name):
                    if re.fullmatch(r'[A-Za-z][A-Za-z -]{3,}',part):
                        self.source_names.setdefault(normalize(part),set()).add(key)
        self.aliases={};self.alias_sources={}
        alias_file=self.data/'aliases.json'
        if alias_file.exists():
            for a in json.loads(alias_file.read_text(encoding='utf-8')):
                # Only verified, sourced brand mappings are usable; never guess from similar names.
                if a.get('verified') is True and str(a.get('source_url','')).startswith('https://') and normalize(a.get('ingredient','')) in self.names:
                    self.aliases[normalize(a['brand'])]=normalize(a['ingredient'])
                    self.alias_sources[normalize(a['brand'])]=a
        self.source_fingerprint=hashlib.sha256((self.data/'rag_current.jsonl').read_bytes()).hexdigest()
        self.fingerprint=effective_fingerprint(self.chunks)
        # TF-IDF sparse vectors support local ranked evidence retrieval without an external API.
        self.counts=[collections.Counter(normalize(c['text']).split()) for c in self.chunks]
        df=collections.Counter(t for counts in self.counts for t in counts)
        self.idf={t:math.log((len(self.chunks)+1)/(n+1))+1 for t,n in df.items()}
        self.vectors=[self.vector(x) for x in self.counts]
        self.semantic_path=self.data/'embeddings.sqlite'

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

    def resolve(self, message):
        q=' '+normalize(message)+' '
        direct=[k for k in self.names if ' '+k+' ' in q]
        hits=list(direct)
        hits.extend(self.aliases[k] for k in self.aliases if ' '+k+' ' in q)
        for short,keys in self.source_names.items():
            if ' '+short+' ' in q and len(keys)==1 and not any(' '+short+' ' in ' '+k+' ' for k in direct):hits.extend(keys)
        hits=list(dict.fromkeys(hits))
        # A listed combination takes priority over the separately listed ingredients.
        def spans(key):
            return [key]+[short for short,keys in self.source_names.items() if key in keys]
        hits=[k for k in hits if not any(k!=other and ' '+k+' ' in ' '+other+' ' for other in hits)]
        return [self.names[k] for k in sorted(hits,key=lambda k:min([q.find(' '+x+' ') for x in spans(k) if ' '+x+' ' in q] or [len(q)]))]

    def detect_route(self,message):
        q=' '+normalize(message)+' '
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
        keys=difflib.get_close_matches(q,self.names.keys(),n=4,cutoff=.66)
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
        selected.extend(self.search(query,3,True,distinct_parents=True))
        if transition_intent(normalize(query)):
            selected=self.transition_chunks+selected
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
        if re.search(r'\b(?:0[35789]\d{8}|\d{12})\b',message) or re.search(r'(?i)(họ tên bệnh nhân|mã bệnh án|số thẻ bhyt)\s*[:=]',message):
            return base|dict(status='private_input',answer='Bạn chỉ cần nhập tên thuốc, hoạt chất và bối cảnh không định danh. Vui lòng bỏ số điện thoại, mã bệnh án hoặc số thẻ BHYT trước khi tra cứu.')
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

    def converse(self,message,state=None,as_of=None):
        from indication_chat import IndicationChat, topics_in
        # Short conversational follow-ups can retain a single medicine, even with
        # prefixes such as "còn", "vậy" or "nếu". A newly named medicine resets it.
        lookup_message=message
        if isinstance(message,str) and isinstance(state,dict) and not self.resolve(message):
            previous=[self.by_id[x] for x in state.get("selected_ids",[])[:20] if isinstance(x,str) and x in self.by_id] if isinstance(state.get("selected_ids"),list) else []
            if len({r["ingredient"] for r in previous})==1 and (topics_in(message) or re.search(r"\b(?:her[ -]?2|egfr)\b",message,re.I) or re.search(r"\b(?:ung thu|benh|dai thao duong|tang huyet ap|viem|nhiem khuan|suy tim|hen|copd|dieu tri)\b",normalize(message))):
                lookup_message=previous[0]["ingredient"]+" "+message
        # General coverage answers use source-bound templates; no external AI call.
        result=self.chat(lookup_message,state,as_of,allow_ai=False)
        answerer=getattr(self,"_indication_chat",None)
        if answerer is None:
            answerer=self._indication_chat=IndicationChat(self)
        result=answerer.enrich(result,message,state)
        notes=self.brand_notes(message)
        if notes and result.get("results"):result["brand_notes"]=notes
        return self.finalize_status(result)

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
