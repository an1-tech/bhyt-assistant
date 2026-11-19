"""Source-linked clinical context for tests outside the special-condition table."""
import json
import re


def contains(q, terms):
    return any(re.search(r'\b' + re.escape(term) + r'\b', q) for term in terms)


GENERAL = re.compile(
    r'(?:(?:xin |cho biet |cho hoi )?(?:dieu kien|quy dinh|pham vi|truong hop nao)'
    r'.{0,65}(?:cho |cua |voi |ve )?(?:cac )?(?:xet nghiem|xn)'
    r'|(?:cac )?(?:xet nghiem|xn) (?:co duoc |duoc )?(?:bhyt|bao hiem y te).{0,35})'
    r'(?: cau tra loi yes or no va trong nhung truong hop nao| nay| do)?'
)
CONDITIONS = ('Đối chiếu kỹ thuật được phê duyệt tại cơ sở, quy trình chuyên môn áp dụng và giá BHYT '
              'được phê duyệt. Nếu dịch vụ có điều kiện riêng, kiểm tra thêm đúng dòng và phương pháp. '
              'Mức hưởng còn phụ thuộc hồ sơ và quyền lợi của lượt khám.')
LAB_WORDS = ('xet nghiem', 'xn', 'dinh luong', 'do hoat do', 'dich vu', 'men gan')
SCREEN = ('tam soat', 'sang loc', 'kham suc khoe', 'kham dinh ky', 'goi kham')
MATRIX = ('nuoc tieu', 'mao mach', 'dich nao tuy', 'dich mang', 'nieu', 'tai giuong', 'dung nap')


class LabGuidance:
    def __init__(self, directory):
        path = directory / 'lab_guidance.json'
        self.data = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
        self.tests = self.data.get('tests', {})

    def match(self, q, state, existing, drug_hits, named, list_items):
        if not self.data:
            return None
        prev = state.get('lab_guide', {})
        ids = [sid for sid, test in self.tests.items() if contains(q, test['aliases'])
               or (test.get('code') and contains(q, [test['code'].replace('.', ' ')]))]
        explicit = contains(q, LAB_WORDS)
        if ids and re.search(r'\b(?:khong phai|thay vi|khong lam) (?:xet nghiem )?(?:ana|ast|alt|got|gpt|ggt|glucose|creatinin)\b', q):
            return {'topic': 'clarify_test'}
        # Glucose is also an infusion. A laboratory value in a medicine question
        # is context, not another ordered service.
        drugs = {group[0]['ingredient'].casefold() for group in drug_hits}
        if 'glucose' in ids and not (explicit or contains(q, ('duong huyet', 'duong mau', 'glucose mau', 'glucose huyet tuong'))):
            ids.remove('glucose')
        lab_drugs = drugs - ({'glucose'} if 'glucose' in ids else set())
        if contains(q, ('chat gpt', 'chatgpt', 'mo hinh gpt', 'openai', 'phim alt', 'got chan',
                        'truyen glucose', 'dung dich glucose')):
            return None
        oncology_purpose = prev.get('topic') == 'oncology' and contains(q, ('chon thuoc',))
        toxicity = contains(q, ('doc tinh thuoc', 'ton thuong gan do thuoc', 'doc tinh gan'))
        if lab_drugs or (contains(q, ('thuoc',)) and not oncology_purpose and not toxicity):
            if not (explicit and (not lab_drugs or contains(q, ('ca thuoc', 'va thuoc', 'va xet nghiem')))):
                return None
        if existing and existing['kind'] in ('renal', 'ambiguous_egfr') and 'egfr' in q:
            return None
        listed = any(piece in self.tests[sid]['aliases'] for piece in list_items for sid in ids)
        if named and (not ids or not (listed or re.search(r'\b(?:va|kem|cung)\b', q))):
            return None
        if ids:
            return {'topic': 'tests', 'tests': ids}
        if contains(q, ('men gan',)) and not named:
            return {'topic': 'liver_panel'}
        group_question = re.search(r'\b(?:cac|nhung|nhom) (?:chi dinh )?(?:xet nghiem|xn)\b|\b(?:xet nghiem|xn) (?:gi|nao|can|chi dinh|trong|khi)\b|\bchi dinh xet nghiem (?:cho|trong|ung thu)\b', q)
        if contains(q, ('ung thu', 'ung buou')) and group_question:
            return {'topic': 'oncology'}
        if group_question:
            matches = [item for item in self.data['indications'] if contains(q, item['terms'])]
            if len(matches) == 1:
                return {'topic': 'indication', 'indication': matches[0]}
            groups = [item for item in self.data['payment_topics'] if contains(q, item['terms'])]
            if len(groups) == 1:
                return {'topic': 'payment_topic', 'group': groups[0]}
        general = GENERAL.fullmatch(q) or q in ('dieu kien bhyt cho xet nghiem', 'chi dinh xet nghiem')
        if prev.get('topic') == 'oncology' and (general or contains(q, ('ung thu',)) or any(
                contains(q, item['terms']) for key in ('cancer_sites', 'cancer_purposes') for item in self.data[key])):
            if not explicit or general:
                return {'topic': 'oncology'}
        if prev.get('topic') == 'tests' and (general or re.fullmatch(
                r'(?:(?:de |dang |chi de |cho )?(?:theo doi |danh gia |chan doan )?(?:viem gan b(?: cap)?|ton thuong gan|benh than man|dai thao duong)|'
                r'(?:chi |de )?(?:tam soat|sang loc|kham suc khoe)(?: dinh ky)?|(?:de )?(?:theo doi |nghi )?doc tinh thuoc|tai vinmec|co hay khong|yes or no|can gi them)', q)):
            return {'topic': 'tests', 'tests': prev['tests'], 'scope': prev.get('scope')}
        if general:
            if state.get('lab', {}).get('id'):
                return None
            return {'topic': 'general'}
        return None

    def answer(self, q, route, prev, labs):
        sections = []
        def add(title, text, sources=()):
            sections.append({'title': title, 'text': text, 'links': [self.data['sources'][key] for key in sources]})

        topic = route['topic']
        memory = {'topic': topic}
        followups = []
        if topic == 'clarify_test':
            lead = 'Bác sĩ muốn tra kỹ thuật nào trên phiếu chỉ định?'
            add('Xác nhận tên', 'Hãy gửi riêng tên kỹ thuật cần đối chiếu. Điều kiện của một kỹ thuật có thể khác với kỹ thuật vừa được loại trừ.')
        elif topic == 'liver_panel':
            lead = 'Bác sĩ muốn tra enzym nào trên phiếu xét nghiệm men gan?'
            add('Chọn kỹ thuật', 'Có thể tra AST (GOT) và ALT (GPT) cùng nhau hoặc tra riêng GGT. Với kỹ thuật khác, gửi tên trên phiếu để đối chiếu đúng nguồn.')
            followups = ['AST và ALT', 'GGT máu']
        elif topic == 'payment_topic':
            group = route['group']
            lead = group['title'] + '. Có các dòng xét nghiệm liên quan trong danh mục BHYT.'
            add('Điểm cần phân biệt', group['question'])
            add('Phạm vi', 'Các dòng dưới đây giúp tra điều kiện và tỷ lệ thanh toán theo kỹ thuật. Việc chọn xét nghiệm cho người bệnh còn phụ thuộc đánh giá lâm sàng.')
        elif topic == 'indication':
            item = route['indication']
            lead = item['title'] + '. Bác sĩ muốn tra điều kiện BHYT cho kỹ thuật nào?'
            add('Các xét nghiệm theo mục đích', item['summary'], item['sources'])
            add('Khi đối chiếu thanh toán', CONDITIONS, ['law'])
            followups = item['followups']
        elif topic == 'general':
            lead = 'Có thể được BHYT chi trả. Cần tên xét nghiệm và mục đích chỉ định để xác định điều kiện cụ thể.'
            add('Điều kiện chung', CONDITIONS, ['law'])
            add('Để tra một trường hợp', 'Bác sĩ cho biết tên kỹ thuật trên phiếu, mục đích làm và cơ sở thực hiện. Với xét nghiệm lặp lại, bổ sung lần làm trước nếu dòng nguồn quy định khoảng cách.')
            followups = ['AST, ALT được BHYT chi trả khi nào?', 'Các xét nghiệm chỉ định trong ung thư', 'HbA1c có điều kiện BHYT gì?']
        elif topic == 'tests':
            ids = route['tests']
            memory['tests'] = ids
            tests = [self.tests[sid] for sid in ids]
            profiles = list(dict.fromkeys(t['profile'] for t in tests))
            labels = ', '.join(t['name'] for t in tests)
            lead = 'Có thể được BHYT chi trả có điều kiện: ' + labels + '. Chưa đủ căn cứ xác nhận thanh toán cho ca cụ thể tại Vinmec.'
            if 'excluded' in profiles:
                lead = ('Theo Danh mục 3 của 17/VBHN-BYT, quỹ tạm thời chưa thanh toán ANA 17 profile test.'
                        if len(profiles) == 1 else 'Các kỹ thuật được hỏi có quy định khác nhau. Cần đối chiếu riêng từng mục.')
            different_method = contains(q, MATRIX) or route.get('scope') == 'other_method'
            screening = (contains(q, SCREEN) or route.get('scope') == 'screening') and not contains(q, ('khong tam soat', 'khong sang loc', 'khong kham suc khoe'))
            if screening and 'excluded' not in profiles:
                memory['scope'] = 'screening'
                lead = 'Chưa đủ căn cứ xác nhận BHYT cho lượt khám hoặc gói sàng lọc đang hỏi.'
            if different_method:
                memory['scope'] = 'other_method'
                lead = 'Chưa đủ căn cứ cho loại mẫu hoặc phương pháp đang hỏi. Cần xác nhận tên kỹ thuật trên phiếu.'
            for profile in profiles:
                group = [t for t in tests if t['profile'] == profile]
                if profile == 'excluded':
                    add('ANA 17 profile test', 'Điều 4 khoản 6 và Danh mục 3, STT 6 nêu đúng kỹ thuật này. Không mở rộng sang xét nghiệm ANA đơn lẻ.', ['excluded','law'])
                    continue
                if different_method:
                    add('Xác nhận kỹ thuật', 'Các mã đã đối chiếu thuộc xét nghiệm máu. Bác sĩ cho biết loại mẫu, phương pháp và tên dịch vụ tại cơ sở để tra đúng mã.')
                    continue
                codes = ', '.join(t['name'] + ' · ' + t['code'] for t in group)
                add('Căn cứ nhận diện dịch vụ', codes + '. Danh mục BHYT công khai của một cơ sở tại Thái Nguyên có các mã này. Mã và phạm vi thanh toán tại Vinmec cần xác nhận riêng.', ['catalog'])
                item = self.data['profiles'][profile]
                if profile == 'liver' and contains(q, ('doc tinh thuoc', 'ton thuong gan do thuoc', 'doc tinh gan')):
                    add('Khi nghi tổn thương gan do thuốc', 'AST và ALT giúp mô tả kiểu tổn thương cùng các chỉ số khác. Cần đối chiếu tên thuốc, thời điểm dùng và hướng dẫn theo dõi của thuốc cụ thể trước khi xác định lịch xét nghiệm.', ['toxicity'])
                else:
                    add('Ví dụ chỉ định chuyên môn', item['summary'], item['sources'])
                if profile == 'liver':
                    add('Đối chiếu với Vinmec', 'Bảng giá dịch vụ Vinmec Nha Trang ghi ALT (GPT) mã 23.19 và AST (GOT) mã 23.20. Để xác nhận quyền lợi, cần danh mục kỹ thuật và giá BHYT được duyệt tại đúng cơ sở, vào ngày thực hiện.', ['vinmec'])
                if screening:
                    add('Trường hợp khám hoặc sàng lọc', 'Cần xác định chương trình, đối tượng và nguồn kinh phí. Bảng dịch vụ của lượt khám chữa bệnh chưa đủ để xác nhận chi trả cho gói sàng lọc.')
                elif not different_method and not contains(q, ('viem gan b', 'benh than man', 'dai thao duong')):
                    add('Thông tin cần làm rõ', item['question'])
            if any(t.get('code') for t in tests):
                add('Điều kiện BHYT cần kiểm tra', CONDITIONS, ['law'])
                if contains(q, ('viem gan b', 'benh than man', 'dai thao duong')):
                    add('Đối chiếu tại cơ sở', 'Bước tiếp theo là kiểm tra tên/mã trên phiếu chỉ định và phạm vi kỹ thuật, giá BHYT tại cơ sở cho lượt khám này.')
        else:
            anatomy = re.sub(r'\bdich vu\b|\btuy xuong\b|\bbach cau tuy\b', ' ', q)
            sites = [s for s in self.data['cancer_sites'] if contains(anatomy, s['terms'])]
            purposes = [s for s in self.data['cancer_purposes'] if contains(q, s['terms'])]
            site = sites[0] if len(sites) == 1 else None
            purpose = purposes[0] if len(purposes) == 1 else None
            ambiguous = len(sites) > 1 or len(purposes) > 1 or bool(re.search(r'\b(?:loai tru|khong phai|khong de|khong nham)\b', q))
            if ambiguous:
                site = purpose = None
            if prev.get('topic') == topic and not ambiguous:
                if not site and not contains(q, ('ung thu', 'ung buou')):
                    site = next((s for s in self.data['cancer_sites'] if s['label'] == prev.get('site')), None)
                if not purpose and (not site or site['label'] == prev.get('site')):
                    purpose = next((s for s in self.data['cancer_purposes'] if s['label'] == prev.get('purpose')), None)
            if site:
                memory['site'] = site['label']
            if purpose:
                memory['purpose'] = purpose['label']
            lead = 'Chọn xét nghiệm theo loại ung thư và mục đích: sàng lọc, xác định chẩn đoán, chọn điều trị hoặc theo dõi. Mỗi kỹ thuật có căn cứ BHYT riêng.'
            if site:
                goal = ' để ' + purpose['label'] if purpose else ''
                lead = f"Với ung thư {site['label']}{goal}, cần đối chiếu từng kỹ thuật theo mục đích chỉ định."
            if purpose:
                add('Mục đích · ' + purpose['label'], purpose['note'], ['diagnosis','oncology'])
            else:
                add('Chọn theo câu hỏi lâm sàng', 'Giải phẫu bệnh giúp xác định bản chất tổn thương; xét nghiệm phân tử có thể hỗ trợ chọn thuốc; một số dấu ấn dùng để theo dõi. Một dấu ấn tăng đơn độc chưa xác định ung thư.', ['diagnosis','oncology'])
            candidates = site['rows'] if site else []
            if purpose:
                candidates = [sid for sid in candidates if sid in purpose['rows']]
            missing_source = False
            for sid in candidates:
                row = labs.services.get(sid)
                if not row or not labs.integrity_ok(sid):
                    missing_source = True
                    continue
                desc = ' '.join(row['conditions'])
                if sid == 'tumor_markers' and site.get('marker_terms'):
                    matching = [t for t in row['conditions'] if any(term in t.casefold() for term in site['marker_terms'])]
                    desc = 'Đọc theo nhánh chẩn đoán hoặc theo dõi tương ứng trong nguồn. ' + ' '.join(matching)
                sections.append({'title':row['name'], 'text':desc,
                    'links':[{'label':row['locator'], 'url':row['viewer_url']}]})
            if missing_source:
                add('Nguồn cần kiểm tra lại', 'Một hoặc nhiều dòng của nhóm này đang thiếu bản nguồn đã kiểm tra. Chỉ các dòng có nguồn đối chiếu được mới hiển thị.')
            if site and not candidates and not (purpose and purpose['label'] == 'sàng lọc'):
                add('Phạm vi bộ tra cứu','Chưa có mục đã ánh xạ cho tổ hợp loại ung thư và mục đích này. Cần tên kỹ thuật để tra riêng.')
            if not site and not purpose and not ambiguous and q.endswith(('ung thu', 'ung buou')):
                example = labs.services.get('egfr')
                if example and labs.integrity_ok('egfr'):
                    sections.append({'title': 'Ví dụ về một dòng thanh toán', 'text': example['conditions'][0],
                                     'links': [{'label': example['locator'], 'url': example['viewer_url']}]})
            if not site:
                add('Cần biết thêm', 'Bác sĩ cho biết một vị trí u và mục đích cần tra, hoặc gửi tên kỹ thuật trên phiếu. Các nhóm dưới đây là ví dụ đã có nguồn.')
            else:
                add('Tra theo nhóm ' + site['label'], 'Đây là các dòng nguồn để đối chiếu. Cần kiểm tra mô bệnh học, mục đích và phương pháp của từng kỹ thuật trước khi áp dụng cho ca cụ thể.')
            followups = (['Ung thư phổi', 'Ung thư vú', 'Ung thư đại trực tràng'] if not site else
                         ['Để chọn điều trị', 'Để theo dõi', 'Để sàng lọc'] if not purpose else [])
        return {'domain':'lab', 'mode':'local', 'status':'lab_guidance', 'answer':lead,
                'lab_guidance':sections, 'state':{'lab_guide':memory}, 'results':[], 'lab_results':[],
                'citations':[], 'source_checked_as_of':self.data['checked_on'], 'suggested_followups':followups,
                'review_label':'Tổng hợp theo các nguồn dẫn từng mục; phần mới chưa được Dược/BHYT Vinmec thẩm định.'}
