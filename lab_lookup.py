"""Source-bound laboratory lookup; no model calls, no patient records.

Routes service coverage separately from drug-marker conditions. Clinical facts
are per-turn/per-service and carried only in the engine's signed browser state.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import unicodedata
from pathlib import Path


def norm(value):
    text = unicodedata.normalize('NFD', str(value).lower().replace('đ', 'd'))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in text if not unicodedata.combining(c))).split())


def has(q, pattern):
    return bool(re.search(pattern, q))


def local_today():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).date()


class LabLookup:
    def __init__(self, data_dir):
        self.data = Path(data_dir)
        path = self.data / 'lab_services.json'
        self.bundle = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'services':[], 'source':{}}
        self.services = {s['id']:s for s in self.bundle['services']}
        self.source = self.bundle['source']

    def integrity_ok(self, service=None):
        if not self.source:
            return False
        files = [(self.source['local_url'], self.source['sha256'])]
        files += [(s['image_url'], s['image_sha256']) for s in self.services.values() if service in (None, s['id'])]
        for url, expected in files:
            path = self.data / url.removeprefix('/')
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                return False
        return True

    def metadata(self):
        return {**self.source, 'service_count':len(self.services), 'integrity_ok':self.integrity_ok(),
                'services':[{'id':s['id'], 'name':s['name'], 'viewer_url':s['viewer_url']} for s in self.services.values()]}

    def route(self, message, state, drug_hits):
        """None means leave the established drug chat path entirely unchanged."""
        q = norm(message)
        ids = [s['id'] for s in self.services.values() if any(has(q, r'\b'+re.escape(norm(a))+r'\b') for a in s['aliases'])]
        lab_state = state.get('lab', {})
        renal = has(q, r'\b(?:do loc cau than|muc loc cau than|creatinin|ckd epi|ml phut|ml min)\b')
        explicit_test = has(q, r'\b(?:xet nghiem|dinh luong|dich vu|xn)\b')
        drug_question = has(q, r'\b(?:thuoc nay|thuoc do|bhyt (?:cua|cho) thuoc|thuoc (?:nay |do )?(?:co duoc|duoc|co bhyt))\b')
        marker = has(q, r'\b(?:ket qua|duong tinh|am tinh|chua co|chua xet nghiem|chua lam|cho xet nghiem|cho ket qua|can xet nghiem|de nghi xet nghiem|chi dinh xet nghiem)\b')
        test_focus = has(q, r'\b(?:bhyt (?:cua|cho) (?:xet nghiem|xn)|(?:xet nghiem|dich vu|xn).{0,80}(?:co duoc|co bhyt|thanh toan|chi tra|dieu kien)|chi phi xet nghiem)\b')
        both = bool(drug_hits or state.get('selected_ids') or has(q,r'\bthuoc\b')) and has(q, r'\b(?:ca hai|ca thuoc va|ca xet nghiem va|va (?:thuoc|erlotinib|gefitinib|afatinib|osimertinib)|va (?:ca )?xet nghiem)\b')
        if renal and 'egfr' in ids:
            return {'ids':[], 'kind':'renal'}
        if 'egfr' in ids and re.search(r'\beGFR\b',message) and not has(q,r'\b(?:dot bien|gen|ung thu|nsclc)\b') and not drug_hits:
            return {'ids':[], 'kind':'ambiguous_egfr'}
        # Insulin used to describe the HbA1c exception is not a second coverage question.
        only_insulin_context = 'hba1c' in ids and has(q, r'\bthai ky\b') and not both
        if 'egfr' in ids and not both:
            if (drug_question or (drug_hits and marker and not test_focus)):
                return None
            if state.get('selected_ids') and not test_focus and (not explicit_test or marker):
                return None
            if drug_hits and not test_focus and not explicit_test:
                return None
        if ids:
            return {'ids':ids, 'kind':'mixed' if both and not only_insulin_context else 'lab'}
        if state.get('selected_ids') and not test_focus and has(q,r'\b(?:fish|ihc|her2|her 2|egfr|kras|nras|ras|co can xet nghiem|ket qua xet nghiem)\b'):
            return None
        if drug_hits or drug_question or has(q, r'\bthuoc\b'):
            return None
        if explicit_test:
            # A newly named unsupported test must never reuse HbA1c/EGFR rules.
            unknown = has(q, r'\b(?:her2|her 2|kras|nras|braf|hbv|hcv|troponin|creatinin|crp|cong thuc mau|scc|pcr|ngs)\b')
            referring = has(q, r'\b(?:xet nghiem (?:nay|do|lai|lan)|lan truoc|lan dau|lan thu|dinh luong lai)\b')
            if unknown or not (lab_state and referring):
                return {'ids':[], 'kind':'unsupported'}
        followup = has(q, r'\b(?:dieu kien|quy dinh|nguon|ngay|thang|lan truoc|lan dau|lan thu|dai thao duong|dtd|thai ky|insulin|phac do|theo doi|danh gia|dieu tri|chan doan|ung thu|nsclc|te bao nho|tam soat|sang loc|khong ro|chua ro|khong nho|khong biet|khong dung|chua dung)\b') or has(message, r'\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}')
        if lab_state.get('id') in self.services and followup:
            return {'ids':[lab_state['id']], 'kind':'lab'}
        if lab_state.get('pending') in ('insulin','diabetes','disease','purpose') and q in ('co','dung','dung roi','khong','chua','chua ro','khong ro'):
            return {'ids':[lab_state['id']], 'kind':'lab'}
        return None

    def citation(self, row):
        return {'id':'LAB-'+row['id'], 'document_id':self.source['document_id'],
                'document_title':self.source['title'], 'locator':row['locator'],
                'page':row['page'], 'page_checked':True, 'excerpt':row['quote'],
                'source_url':self.source['source_url'], 'official_url':self.source['official_url'],
                'local_url':self.source['local_url'], 'viewer_url':row['viewer_url'],
                'effective_from':self.source['effective_from'], 'checked_as_of':self.source['checked_as_of']}

    def answer(self, message, state, route, today=None):
        today = today or local_today()
        base = dict(snapshot=self.source.get('checked_as_of'), mode='local', domain='lab',
                    answer='', results=[], lab_results=[], citations=[], suggestions=[], followups=[], state={})
        if route['kind']=='ambiguous_egfr':
            return base | {'status':'needs_info', 'answer':'Bạn đang hỏi xét nghiệm đột biến gen EGFR trong ung thư, hay eGFR là mức lọc cầu thận? Hãy nêu rõ để tra đúng dịch vụ.'}
        if route['kind'] in ('unsupported','renal'):
            text = ('eGFR về mức lọc cầu thận không phải xét nghiệm đột biến gen EGFR. Bộ dữ liệu này chưa có quy tắc BHYT cho dịch vụ thận đang hỏi.'
                    if route['kind']=='renal' else 'Bộ dữ liệu xét nghiệm hiện mới có HbA1c và xét nghiệm đột biến gen EGFR. Chưa có căn cứ đã kiểm tra cho xét nghiệm đang hỏi; điều này không có nghĩa là BHYT không chi trả.')
            return base | {'status':'unknown', 'answer':text}
        if not self.integrity_ok():
            return base | {'status':'source_unavailable', 'answer':'Nguồn xét nghiệm bị thiếu hoặc đã thay đổi. Cần đối chiếu lại tài liệu trước khi trả lời điều kiện BHYT.'}
        for sid in route['ids']:
            row = self.services[sid]
            prev = state.get('lab', {}) if len(route['ids'])==1 else {}
            facts, case, errors = self.extract(message, sid, prev, today)
            if len(route['ids'])>1:
                # Dates/purposes in a multi-service question cannot be attributed safely.
                facts, case, errors = {}, False, []
            a = self.evaluate(sid, facts, case, errors, today)
            base['lab_results'].append({'id':sid, 'name':row['name'], **a, 'conditions':row['conditions'],
                                        'citation':self.citation(row), 'facts':facts,
                                        'scope':'Đối chiếu điều kiện riêng của dịch vụ theo nguồn; chưa xác nhận mức hưởng cá nhân, giá hay phạm vi hợp đồng của bệnh viện.'})
            base['citations'].append(self.citation(row))
            if len(route['ids'])==1:
                base['state']={'lab':{'id':sid,'facts':facts,'case':case, 'pending':a.get('pending'), 'date':today.isoformat()}}
        statuses = [r['status'] for r in base['lab_results']]
        base['status']='needs_info' if 'needs_info' in statuses else 'answered'
        base['answer']='\n\n'.join(r['name']+': '+r['conclusion'] for r in base['lab_results'])
        base['source_checked_as_of']=self.source['checked_as_of']
        return base

    def extract(self, message, sid, prev, today):
        q = norm(message)
        named = any(has(q, r'\b'+re.escape(norm(a))+r'\b') for a in self.services[sid]['aliases'])
        continuation = not named or has(q, r'^(?:con|vay|neu|the|lan truoc|lan nay)\b')
        same = prev.get('id')==sid and continuation and not has(q,r'\b(?:ca moi|truong hop khac|benh nhan khac)\b')
        f = dict(prev.get('facts', {})) if same else {}
        errors = []
        case = bool(prev.get('case')) if same else False
        if same and q in ('co','dung','dung roi','khong','chua','chua ro','khong ro'):
            key=prev.get('pending')
            value=True if q in ('co','dung','dung roi') else False if q in ('khong','chua') else None
            if key in ('insulin','diabetes'):
                if value is None:f.pop(key,None)
                else:f[key]=value
            if key=='disease':f['disease']='nsclc' if value is True else 'unknown'
            if key=='purpose' and sid=='egfr':
                if value is True:f['purpose']='mutation_in_treatment'
                else:f.pop('purpose',None)
        generic = has(q, r'\b(?:dieu kien (?:bhyt|thanh toan|chung)|quy dinh|noi chung|can dieu kien|dieu kien gi)\b')
        case_requested=has(q, r'\b(?:hom nay|chi dinh lai|lam lai|lan truoc|cach day|truoc do|benh nhan|nguoi benh|truong hop nay|ca nay|da duoc chan doan|da chan doan|lan dau|lan thu|chua tung)\b')
        if case_requested:
            case=True
        if generic and not case_requested and not has(q,r'\b(?:tam soat|sang loc|ngs|pcr|panel|gia|ty le|phan tram)\b'):
            return {},False,[]
        if has(q, r'\b(?:tam soat|sang loc|chan doan ban dau|chan doan dai thao duong)\b'):
            f['purpose']='screening'
        if has(q,r'\b(?:xac dinh|chon|lap|dieu chinh) phac do\b'):
            f['purpose']='regimen'
        if has(q,r'\b(?:theo doi|danh gia (?:ket qua |dap ung )?dieu tri|kiem soat duong huyet)\b'):
            f['purpose']='monitoring'
        if has(q,r'\b(?:khong|chua) (?:ro|biet|xac dinh) muc dich\b'):
            f.pop('purpose',None)
        if has(q,r'\b(?:khong|chua) (?:duoc )?chan doan (?:xac dinh )?(?:dai thao duong|dtd)\b|\bkhong (?:bi |mac )?(?:dai thao duong|dtd)\b'):
            f['diabetes']=False
        elif has(q,r'\b(?:dai thao duong|dtd|tieu duong)\b'):
            f['diabetes']=True
        if has(q,r'\b(?:thai ky)\b'):
            f['gestational']=not has(q,r'\b(?:khong (?:phai |co )?|loai tru )(?:dai thao duong )?thai ky\b')
        if has(q,r'\b(?:khong|chua|ngung|da ngung) (?:co |dieu tri |dung |su dung |bang )*insulin\b'):
            f['insulin']=False
        elif has(q,r'\binsulin\b'):
            f['insulin']=True
        if has(q,r'\b(?:chua ro|khong ro|chua biet|khong biet).{0,25}insulin\b'):
            f.pop('insulin',None)
        if has(q,r'\binsulin (?:hay )?khong\b'):
            f.pop('insulin',None)
        if has(q,r'\b(?:chua ro|khong ro|chua biet|khong biet).{0,30}(?:dai thao duong|dtd)\b'):
            f.pop('diabetes',None)
        if has(q,r'\b(?:dai thao duong|dtd) (?:hay )?(?:chua|khong)\b'):
            f.pop('diabetes',None)
        if has(q,r'\b(?:khong|chua) (?:de )?(?:theo doi|danh gia|xac dinh phac do)\b'):
            f.pop('purpose',None)
        if has(q,r'\b(?:chua tung (?:lam|thuc hien|xet nghiem)|lan dau|lan dau tien)\b'):
            f['first_test']=True
            f.pop('last_date',None)
        if has(q,r'\b(?:lan thu (?:2|hai|3|ba)|tu lan thu 2|da lam|da xet nghiem)\b'):
            f['first_test']=False
        # Explicit subtype precedes generic lung detection. Negative / unknown must not count as NSCLC.
        if has(q,r'\b(?:khong phai|khong bi|khong mac|loai tru|chua (?:ro|xac dinh|chan doan)).{0,25}(?:nsclc|ung thu phoi khong (?:phai )?te bao nho)\b'):
            f['disease']='unknown'
        elif has(q,r'\b(?:nsclc|ung thu phoi khong (?:phai )?te bao nho|utp khong te bao nho)\b'):
            f['disease']='nsclc'
        elif has(q,r'\b(?:sclc|ung thu phoi te bao nho|ung thu (?:vu|da day|dai truc trang|gan|tuyen giap))\b'):
            f['disease']='other'
        elif has(q,r'\bung thu phoi\b'):
            f['disease']='lung_unspecified'
        if has(q,r'\b(?:chua ro|khong ro).{0,20}(?:the benh|mo benh hoc|loai ung thu)\b'):
            f['disease']='unknown'
        if has(q,r'\b(?:nsclc|te bao nho) (?:hay )?(?:chua|khong)\b'):
            f['disease']='unknown'
        if sid=='egfr' and has(q,r'\b(?:dieu tri|chan doan dot bien)\b') and f.get('purpose')!='screening':
            f['purpose']='mutation_in_treatment'
        if sid=='hba1c':
            self.extract_dates(message, q, f, prev if same else {}, today, errors)
        # Unsupported timing/method questions are retained as an explicit limitation.
        f.pop('special_question',None)
        if sid=='egfr' and has(q,r'\b(?:ngs|pcr|panel|sinh thiet long|mau|huyet tuong|lan thu|lam lai|bao nhieu lan|gia|phan tram|ty le)\b'):
            f['special_question']=True
        return f,case,errors

    @staticmethod
    def extract_dates(message, q, f, prev, today, errors):
        f.pop('date_error',None)
        if q in ('khong nho','khong biet','chua ro','khong ro') or has(q,r'\b(?:khong nho|khong biet|chua ro|khong ro).{0,35}(?:ngay|lan truoc)|\b(?:ngay|lan truoc).{0,20}(?:khong nho|chua ro|khong ro)\b'):
            f.pop('last_date',None)
            f.pop('first_test',None)
        intervals = re.findall(r'\b(?:cach(?: day)?\s+)?(\d{1,4})\s+ngay\s+(?:truoc|roi)\b|\bcach(?: day)?\s+(\d{1,4})\s+ngay\b',q)
        if intervals:
            days={int(a or b) for a,b in intervals}
            if len(days)!=1:
                errors.append('Có nhiều khoảng cách ngày khác nhau; hãy nêu ngày thực hiện gần nhất.')
            else:
                f['last_date']=(today-dt.timedelta(days=days.pop())).isoformat()
                f['first_test']=False
        dates=list(re.finditer(r'(?<!\d)(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4})(?!\d)',message))
        assigned={}
        for match in dates:
            value=match.group(0)
            try:
                parts=list(map(int,re.split(r'[/.-]',value)))
                date=dt.date(*parts) if len(value.split('-')[0])==4 else dt.date(parts[2],parts[1],parts[0])
            except ValueError:
                errors.append('Ngày không hợp lệ; hãy ghi đủ ngày/tháng/năm.')
                continue
            before=norm(message[max(0,match.start()-55):match.start()])
            if has(before,r'(?:lan truoc|gan nhat|da (?:lam|thuc hien)|lan cu)(?: vao)?(?: ngay)?$'):
                role='last_date'
            elif has(before,r'(?:lan nay|du kien|chi dinh|hom nay)(?: vao)?(?: ngay)?$'):
                role='planned_date'
            elif len(dates)==1 and prev.get('pending')=='last_date':
                role='last_date'
            else:
                errors.append('Hãy ghi rõ ngày xét nghiệm lần trước và ngày dự kiến lần này để tránh nhầm hai mốc.')
                continue
            if role in assigned and assigned[role]!=date.isoformat():
                errors.append('Có hai ngày cho cùng một lần xét nghiệm; cần xác nhận ngày đúng.')
            assigned[role]=date.isoformat()
        f.update(assigned)
        if 'last_date' in assigned:
            f['first_test']=False
        if has(q,r'\bhom nay\b') and 'planned_date' not in assigned:
            f.pop('planned_date',None)
        if has(q,r'\b\d+ thang (?:truoc|roi)\b|\bcach(?: day)? \d+ thang\b'):
            f.pop('last_date',None)
            errors.append('Khoảng cách theo tháng chưa đủ chính xác ở mốc ngày; hãy nêu ngày thực hiện lần trước.')
        if errors:
            f.pop('last_date',None)
            f['date_error']=' '.join(errors)

    def evaluate(self, sid, f, case, errors, today):
        row=self.services[sid]
        reasons=[]
        def result(status, text, pending=None):
            return {'status':status, 'conclusion':text, 'reasons':reasons, 'pending':pending}
        if sid=='egfr' and f.get('special_question'):
            return result('needs_review','Dòng EGFR này không quy định cụ thể phương pháp, bệnh phẩm, số lần lặp lại hay giá/tỷ lệ. Cần đối chiếu đúng dịch vụ và nguồn bổ sung; chưa kết luận cho chi tiết vừa hỏi.')
        if not case:
            if sid=='hba1c':
                if f.get('purpose')=='screening' or f.get('diabetes') is False:
                    return result('source_condition_not_met','Bối cảnh vừa nêu không khớp nhánh HbA1c đã tra; bộ dữ liệu này chưa có căn cứ khác để kết luận cho sàng lọc/chẩn đoán ban đầu.')
                return result('conditions_only','Có quy định thanh toán HbA1c theo mục đích xét nghiệm và khoảng cách giữa các lần. Xem đủ ba nhánh điều kiện dưới đây.')
            if f.get('disease')=='other' or f.get('purpose')=='screening':
                return result('source_condition_not_met','Bối cảnh vừa nêu không khớp phạm vi của dòng EGFR đã tra. Không dùng dòng này để kết luận chi trả cho bệnh hoặc mục đích khác.')
            return result('conditions_only','Có quy định thanh toán xét nghiệm đột biến gen EGFR trong điều trị ung thư phổi không tế bào nhỏ. Điều kiện này độc lập với điều kiện dùng thuốc.')
        if sid=='egfr':
            if f.get('special_question'):
                return result('needs_review','Dòng EGFR này không quy định cụ thể phương pháp, bệnh phẩm, số lần lặp lại hay giá/tỷ lệ. Cần đối chiếu đúng dịch vụ và nguồn bổ sung; chưa kết luận cho chi tiết vừa hỏi.')
            if f.get('disease')=='other' or f.get('purpose')=='screening':
                return result('source_condition_not_met','Bệnh hoặc mục đích vừa nêu không khớp điều kiện của dòng xét nghiệm EGFR trong nguồn; chưa có căn cứ khác trong bộ dữ liệu này.')
            if f.get('disease')!='nsclc':
                return result('needs_info','Nguồn áp dụng cho ung thư phổi không tế bào nhỏ. Trường hợp đang hỏi đã xác định thể bệnh này chưa?', 'disease')
            reasons.append('Bệnh được nêu: ung thư phổi không tế bào nhỏ — khớp phạm vi bệnh của dòng EGFR.')
            if f.get('purpose')!='mutation_in_treatment':
                return result('needs_info','Xét nghiệm có nhằm chẩn đoán đột biến gen EGFR trong quá trình điều trị không?', 'purpose')
            reasons.append('Mục đích được nêu: chẩn đoán đột biến gen trong điều trị — khớp điều kiện riêng của dịch vụ.')
            return result('source_conditions_match','Thông tin đã nêu khớp điều kiện riêng của xét nghiệm EGFR trong nguồn. Đây chưa phải xác nhận thanh toán của bệnh viện.')
        if errors or f.get('date_error'):
            return result('needs_info',f.get('date_error') or ' '.join(errors), 'last_date')
        planned=dt.date.fromisoformat(f.get('planned_date',today.isoformat()))
        if planned<dt.date.fromisoformat(self.source['effective_from']) or planned>today:
            return result('needs_review','Ngày xét nghiệm nằm trước ngày áp dụng bộ quy tắc hoặc trong tương lai. Cần kiểm tra văn bản áp dụng ở thời điểm đó; chưa đối chiếu tự động.')
        if f.get('purpose')=='screening' or f.get('diabetes') is False:
            return result('source_condition_not_met','Thông tin vừa nêu không khớp nhánh HbA1c đã có trong nguồn (đái tháo đường đã xác định/phục vụ điều trị). Không suy ra kết luận từ chối BHYT cho mọi trường hợp.')
        gestational=f.get('gestational') is True
        if gestational and 'insulin' not in f:
            return result('needs_info','Đái tháo đường thai kỳ có điều trị bằng insulin không? Thông tin này quyết định có áp dụng nhánh 30 ngày hay không.', 'insulin')
        exception=gestational and f.get('insulin') is True
        if not exception:
            if not f.get('purpose'):
                return result('needs_info','Lần này để xác định phác đồ điều trị, đánh giá kết quả điều trị, hay sàng lọc/chẩn đoán ban đầu?', 'purpose')
            if f.get('diabetes') is not True:
                return result('needs_info','Trường hợp đang hỏi đã được chẩn đoán xác định đái tháo đường chưa?', 'diabetes')
        reasons.append('Áp dụng nhánh đái tháo đường thai kỳ có insulin: mỗi 30 ngày một lần.' if exception else 'Áp dụng nhánh '+('xác định phác đồ điều trị.' if f['purpose']=='regimen' else 'đánh giá kết quả điều trị từ lần thứ 2.'))
        if f.get('first_test') is True:
            if not exception and f.get('purpose')=='regimen':
                reasons.append('Bạn cho biết chưa từng thực hiện HbA1c; không có lần trước trong khoảng thời gian nguồn yêu cầu.')
                return result('source_conditions_match','Thông tin đã nêu khớp điều kiện riêng của nhánh xác định phác đồ trong nguồn; chưa xác nhận thanh toán thực tế.')
            return result('needs_review','Bạn cho biết đây là lần đầu. Không áp máy móc điều kiện lặp lại để kết luận cho lần đầu; cần đối chiếu thêm mục đích và căn cứ phù hợp.')
        if not f.get('last_date'):
            return result('needs_info','HbA1c gần nhất được thực hiện ngày nào? Có thể trả lời “Lần trước ngày …” hoặc “cách … ngày”; nếu chưa từng làm, hãy nói rõ.', 'last_date')
        last=dt.date.fromisoformat(f['last_date'])
        days=(planned-last).days
        reasons.append(f"Lần trước {last.strftime('%d/%m/%Y')}, lần này {planned.strftime('%d/%m/%Y')}: cách {days} ngày.")
        if days<0:
            return result('needs_info','Ngày lần trước đang sau ngày lần này. Hãy kiểm tra lại hai mốc.', 'last_date')
        if exception:
            if days<30:
                return result('source_condition_not_met','Khoảng cách chưa đạt 30 ngày theo nhánh thai kỳ dùng insulin trong nguồn.')
        else:
            policy=row['timing_policy']
            if days<policy['below_days']:
                return result('source_condition_not_met','Khoảng cách ngắn hơn mốc 90 ± 3 ngày trong nguồn. Chưa khớp điều kiện thời gian của nhánh đang đối chiếu.')
            if policy['review_from_days']<=days<=policy['review_through_days']:
                reasons.append(policy['note'])
                return result('needs_review','Khoảng cách nằm trong vùng 90 ± 3 ngày. Giữ nguyên quy định và cần đối chiếu cách áp dụng sai số; chatbot chưa tự chốt ở mốc này.')
        return result('source_conditions_match','Thông tin đã nêu khớp điều kiện riêng của nhánh HbA1c đang đối chiếu; chưa xác nhận thanh toán thực tế.')

    def source_html(self, sid):
        if sid not in self.services:
            return None
        s=self.services[sid]
        e=html.escape
        verified=self.integrity_ok(sid)
        body=(f'<img class="lab-source-image" src="{e(s["image_url"])}" alt="Ảnh nguyên văn dòng {s["appendix_row"]}, {e(s["name"])} trong phụ lục">' if verified
              else '<p class="error">Tệp nguồn bị thiếu hoặc thay đổi. Không hiển thị ảnh trích dẫn chưa kiểm chứng.</p>')
        return f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(s['name'])} · Trích dẫn nguồn</title><link rel="stylesheet" href="/style.css"></head><body>
<main class="canvas lab-source-page"><a href="/">Về chatbot</a><h1>{e(s['name'])}</h1><p>{e(self.source['title'])} · {e(s['locator'])}</p>
<section id="source-row" class="panel"><h2>Vị trí trích dẫn trong bản gốc</h2>{body}<p class="hint">Ảnh cắt trọn dòng dịch vụ, gồm tất cả nhánh và ngoại lệ.</p><details><summary>Đọc nguyên văn dạng chữ</summary><p class="lab-verbatim">{e(s['quote']) if verified else 'Nguồn chưa kiểm chứng.'}</p></details></section>
<div class="source-links"><a href="{e(self.source['local_url'])}#page={s['page']}" target="_blank" rel="noopener noreferrer">Mở toàn trang PDF {s['page']}</a><a href="{e(self.source['official_url'])}" target="_blank" rel="noopener noreferrer">Bản công bố chính thức</a><a href="/sources/labs/17-vbhn-2024.pdf#page={s['consolidated_pages'][0]}" target="_blank" rel="noopener noreferrer">Đối chiếu bản hợp nhất</a></div>
<p>Áp dụng quy tắc từ 01/01/2025 · Kiểm tra nguồn 10/11/2026.</p><p class="hint">{e(self.source['review_limitations'])}</p><p>{e(self.source['review_status'])}</p></main></body></html>'''.encode('utf-8')
