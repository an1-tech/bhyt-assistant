"""Read-only corpus browsing; department context never restricts drug access."""
from collections import defaultdict
from engine import normalize, SNAPSHOT

DEPARTMENTS = ['Tất cả các khoa', 'Cấp cứu', 'Hồi sức tích cực', 'Nội tổng hợp', 'Tim mạch',
 'Hô hấp', 'Tiêu hóa', 'Nội tiết', 'Thận - Tiết niệu', 'Cơ xương khớp', 'Thần kinh',
 'Truyền nhiễm', 'Ung bướu', 'Huyết học', 'Ngoại khoa', 'Sản phụ khoa', 'Nhi khoa',
 'Gây mê hồi sức', 'Mắt', 'Tai mũi họng', 'Răng hàm mặt', 'Da liễu', 'Y học hạt nhân', 'Khoa khác']

DOCUMENT_NAMES = {'TT20_2022':'Thông tư 20/2022/TT-BYT',
 'TT37_2024':'Thông tư 37/2024/TT-BYT', 'CV3293_2025':'Công văn 3293/BYT-BH năm 2025',
 'CV5079_2025':'Công văn 5079/BYT-BH năm 2025'}


def group_label(row):
    label=row.get('group') or 'Thuốc phóng xạ và chất đánh dấu'
    # Preserve source rows; correct the display hierarchy of a misread 2.3 subsection.
    if normalize(label).startswith('23 thuoc chong thoai hoa khop'):
        return '2. Thuốc giảm đau, hạ sốt; chống viêm; gút và xương khớp'
    if label.startswith('2. '):return '2. Thuốc giảm đau, hạ sốt; chống viêm; gút và xương khớp'
    import re
    match=re.match(r'(\d+\. )(.*)',label)
    return match.group(1)+match.group(2).lower().capitalize() if match else label


def metadata(corpus):
    sources=[]
    for key in dict.fromkeys(c.get('document_id') for c in corpus.chunks):
        docs=[c for c in corpus.chunks if c.get('document_id')==key]
        sources.append(dict(id=key,title=DOCUMENT_NAMES.get(key,key),chunks=len(docs),
            url=docs[0].get('source_url'),official_url=docs[0].get('official_url'),
            local_url='/sources/15-vbhn-byt-2024.pdf' if key=='TT20_2022' else '/sources/37-2024-tt-byt.pdf' if key=='TT37_2024' else None))
    groups=list(dict.fromkeys(group_label(r) for r in corpus.rows))
    return dict(snapshot=SNAPSHOT,version='1.9-toan-vien',transition_review_date='2026-11-07',departments=DEPARTMENTS,groups=groups,
        drug_entries=len({r['stt'] for r in corpus.drugs}),radio_entries=len({r['stt'] for r in corpus.radio}),
        variants=len(corpus.rows),chunks=len(corpus.chunks),sources=sources,
        source_update=corpus.supplemental.metadata(),
        review_status='Chưa được bệnh viện thẩm định',
        scope='Toàn bộ các khoa; thuốc hóa dược, sinh phẩm, thuốc phóng xạ và chất đánh dấu trong bộ nguồn.',
        missing=['Danh mục thuốc, biệt dược và phạm vi hợp đồng BHYT tại bệnh viện.',
                 'Danh mục thuốc y học cổ truyền, dược liệu và vị thuốc chưa có trong gói dữ liệu này.',
                 'Chưa xác minh mức hưởng, chuyển cơ sở, chỉ định lâm sàng của từng người bệnh.'])


def catalog(corpus,query='',group='',appendix='',page=1):
    q=normalize(query[:150]);records=defaultdict(list)
    for row in corpus.rows:
        if appendix and row.get('appendix','I')!=appendix:continue
        if group and group_label(row)!=group:continue
        haystack=normalize(row['ingredient'])
        if q and q not in haystack and q!=str(row['stt']):continue
        records[(row.get('appendix','I'),row['stt'])].append(row)
    all_rows=[]
    for (app,stt),rows in records.items():
        all_rows.append(dict(ingredient=rows[0]['ingredient'],stt=stt,appendix=app,
            group=group_label(rows[0]),routes=list(dict.fromkeys(r['route'] for r in rows)),
            has_conditions=any(r.get('conditions_verbatim') for r in rows)))
    page=max(1,min(int(page),10000));size=20;total=len(all_rows)
    return dict(items=all_rows[(page-1)*size:page*size],total=total,page=page,page_size=size,pages=max(1,(total+size-1)//size))
