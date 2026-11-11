"""Build-time source extraction for laboratory services. Runtime needs only the standard library.

Scope: every laboratory-test row with its own payment condition in
  - TT39/2024 appendix (rows amended from 01/01/2025; PDF with a text layer), and
  - 17/VBHN-BYT (TT35/2016 consolidated; a scan) for the rows TT39 did not amend.

TT39 rows are read from the PDF text layer: the service name must equal the name typed
here and the condition text is taken from the table cell itself (only line wraps are
joined). Each row is cropped to an image. One complete service row is one chunk.

17/VBHN-BYT rows are transcribed from the page images by reading them (the OCR layer of
that scan is unusable). They are marked `scan_read` and shown with the page image so the
reader can compare; they are never used for an automatic case conclusion.

    python tools/build_lab_sources.py        (needs pdfplumber)
"""
import hashlib
import json
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data/sources/labs'
CHECKED = '2026-11-11'
MARK = re.compile(r'^(?:[a-zđ]\)|\d+\.|[-+•])\s')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def squeeze(text):
    return re.sub(r'\s+', '', text or '')


def paragraphs(text):
    """Join PDF line wraps; keep the list items of the source as separate paragraphs."""
    out = []
    for line in (text or '').split('\n'):
        line = ' '.join(line.split())
        if not line:
            continue
        prev = out[-1] if out else ''
        ended = prev.endswith(('.', ';', ':'))
        marker = bool(MARK.match(line))
        # "thanh quản\n- hạ họng": a dash inside a sentence, not a list item.
        if marker and line[0] == '-' and line[2:3].islower() and prev and not ended:
            marker = False
        if not out or marker or (ended and not prev.endswith(':')):
            out.append(line)
        elif re.search(r'\S-$', prev) and not prev.endswith(' -'):
            out[-1] = prev + line            # "CA 15-" + "3", "Pro-" + "calcitonin"
        else:
            out[-1] = prev + ' ' + line
    return out


# ---- TT39/2024 appendix rows (text layer). Key: (list, STT theo TT35). -----------------
GENE_SPECIAL = r'\b(?:ngs|pcr|panel|sinh thiet long|mau|huyet tuong|lan thu|lan 2|lan hai|lan 3|lam lai|lap lai|nhac lai|bao nhieu lan|gia|phan tram|ty le)\b'
# A question that names one of these asks about another HLA test or method than the two rows.
HLA_OTHER = r'\b(?:ngs|giai trinh tu|the he moi|sanger|flow|luminex|b27|b 27|b5801|b 5801|b1502|b 1502|hla b|hla a|hla c|hla dr|hla dq)\b'
TT39_ROWS = [
    dict(key=(1, 10), id='tumor_markers', name='Các xét nghiệm chỉ điểm khối u (CA 125, CA 15-3, CA 19-9, CA 72-4, CEA)',
         official_name='Các xét nghiệm chỉ điểm khối u bằng kỹ thuật miễn dịch phóng xạ hoặc hóa sinh.',
         aliases=['chỉ điểm khối u', 'dấu ấn ung thư', 'tumor marker', 'ca 125', 'ca125', 'ca 15 3', 'ca15 3', 'ca153', 'ca 19 9', 'ca19 9', 'ca199',
                  'ca 72 4', 'ca72 4', 'ca724', 'cea'], consolidated_pages=[26, 27]),
    dict(key=(1, 11), id='crp', name='Định lượng CRP/CRP hs [Máu]', official_name='Định lượng CRP/CRP hs [Máu]',
         aliases=['crp', 'crp hs', 'hs crp', 'protein phản ứng c'], consolidated_pages=[27]),
    dict(key=(1, 12), id='procalcitonin', name='Định lượng Procalcitonin [Máu]', official_name='Định lượng Pro-calcitonin [Máu]',
         aliases=['procalcitonin', 'pro calcitonin', 'pct'], consolidated_pages=[27, 28]),
    dict(key=(2, 69), id='cd25', name='Định lượng CD25 (IL-2R) hòa tan trong huyết thanh bằng kỹ thuật ELISA',
         official_name='Định lượng CD25 (IL-2R) hòa tan trong huyết thanh bằng kỹ thuật ELISA', aliases=['cd25', 'il 2r', 'il2r'], consolidated_pages=[44]),
    dict(key=(2, 72), id='hla_ssp', name='Định type HLA cho 1 locus bằng kỹ thuật PCR-SSP',
         official_name='Định type HLA cho 1 locus (Locus A, hoặc Locus B, hoặc Locus C, hoặc Locus DR, hoặc Locus DQ) bằng kỹ thuật PCR-SSP',
         aliases=['pcr ssp', 'hla pcr ssp'], loose_aliases=['hla', 'định type hla'], consolidated_pages=[44, 45],
         name_note='Dòng này chỉ quy định định type HLA cho 1 locus (A, B, C, DR hoặc DQ) bằng kỹ thuật PCR-SSP; xét nghiệm HLA bằng kỹ thuật khác không thuộc dòng này.',
         foreign=HLA_OTHER),
    dict(key=(2, 76), id='colony_culture', name='Nuôi cấy cụm tế bào gốc (colony forming culture)',
         official_name='Nuôi cấy cụm tế bào gốc (colony forming culture)', aliases=['nuôi cấy cụm tế bào gốc', 'colony forming'], consolidated_pages=[46]),
    dict(key=(2, 79), id='platelet_ab_flow', name='Phát hiện kháng thể kháng tiểu cầu bằng kỹ thuật Flow-cytometry',
         official_name='Phát hiện kháng thể kháng tiểu cầu bằng kỹ thuật Flow-cytometry', aliases=['kháng thể kháng tiểu cầu'], consolidated_pages=[46]),
    dict(key=(2, 80), id='platelet_ab_direct', name='Xét nghiệm xác định kháng thể kháng tiểu cầu trực tiếp',
         official_name='Xét nghiệm xác định kháng thể kháng tiểu cầu trực tiếp', aliases=['kháng thể kháng tiểu cầu', 'kháng thể kháng tiểu cầu trực tiếp'], consolidated_pages=[47]),
    dict(key=(2, 84), id='hba1c', name='Định lượng HbA1c [Máu]',
         official_name='Định lượng HbA1c [Máu] để xác định phác đồ điều trị hoặc để đánh giá kết quả điều trị bệnh đái tháo đường',
         aliases=['hba1c', 'hb a1c', 'a1c', 'hemoglobin a1c'], consolidated_pages=[47, 48], rule='hba1c',
         expected_conditions=[
             'a) Thanh toán cho xét nghiệm định lượng HbA1c trong máu đối với trường hợp đã được chẩn đoán xác định đái tháo đường để xác định phác đồ điều trị nếu chưa thực hiện xét nghiệm HbA1c trong vòng 90 ± 3 (chín mươi cộng trừ 3) ngày.',
             'b) Thanh toán cho xét nghiệm từ lần thứ 2 trở đi để đánh giá kết quả điều trị bệnh đái tháo đường tối thiểu sau mỗi 90 ± 3 (chín mươi cộng trừ 3) ngày.',
             'c) Trường hợp đái tháo đường thai kỳ có điều trị bằng insulin, thực hiện xét nghiệm HbA1C mỗi 30 ngày 01 lần.'],
         branches=[
             {'id': 'regimen', 'purpose': 'Xác định phác đồ điều trị', 'requires_confirmed_diabetes': True, 'timing': '90 ± 3 ngày'},
             {'id': 'monitoring', 'purpose': 'Đánh giá kết quả điều trị từ lần thứ 2', 'timing': '90 ± 3 ngày'},
             {'id': 'gestational_insulin', 'purpose': 'Đái tháo đường thai kỳ điều trị bằng insulin', 'interval_days': 30}],
         timing_policy={'below_days': 87, 'review_from_days': 87, 'review_through_days': 93, 'above_days': 93,
                        'note': '87–93 ngày: cần đối chiếu cách áp dụng sai số với bộ phận BHYT; đây là giới hạn tự động hóa của prototype, không phải điều kiện pháp luật bổ sung.'}),
    dict(key=(2, 87), id='hbv_load', name='HBV đo tải lượng (Real-time PCR hoặc hệ thống tự động)',
         official_name='HBV đo tải lượng Real-time PCR; HBV đo tải lượng hệ thống tự động',
         aliases=['hbv đo tải lượng', 'đo tải lượng hbv', 'tải lượng hbv', 'hbv dna', 'định lượng hbv', 'tải lượng virus viêm gan b', 'tải lượng vi rút viêm gan b',
                  'tải lượng viêm gan b'], consolidated_pages=[48]),
    dict(key=(2, 88), id='hcv_load', name='HCV đo tải lượng (Real-time PCR hoặc hệ thống tự động)',
         official_name='HCV đo tải lượng Real-time PCR; HCV đo tải lượng hệ thống tự động',
         aliases=['hcv đo tải lượng', 'đo tải lượng hcv', 'tải lượng hcv', 'hcv rna', 'định lượng hcv', 'tải lượng virus viêm gan c', 'tải lượng vi rút viêm gan c',
                  'tải lượng viêm gan c'], consolidated_pages=[48, 49],
         source_note='Nguồn in “viêm ban vi rút C” (cả TT39 và bản hợp nhất); giữ nguyên văn.'),
    dict(key=(2, 96), id='her2', name='Xét nghiệm đột biến gen Her 2', official_name='Xét nghiệm đột biến gen Her 2',
         aliases=['her2', 'her 2', 'đột biến gen her2', 'đột biến gen her 2'], consolidated_pages=[49], rule='gene', marker=True,
         scope=['breast', 'gastric', 'nsclc'], scope_label='ung thư vú, ung thư dạ dày hoặc ung thư phổi không tế bào nhỏ',
         special=GENE_SPECIAL[:-3] + r'|ihc|fish|hoa mo mien dich|nhuom|khuech dai|bieu hien)\b',
         special_note='Dòng này ghi “xét nghiệm đột biến gen Her 2” và không nêu phương pháp (hóa mô miễn dịch, FISH, giải trình tự…), bệnh phẩm, số lần lặp lại hay giá/tỷ lệ.'),
    dict(key=(2, 97), id='braf', name='Xét nghiệm đột biến gen BRAF', official_name='Xét nghiệm đột biến gen BRAF',
         aliases=['braf', 'đột biến gen braf'], consolidated_pages=[49], rule='gene', marker=True,
         scope=['colorectal', 'thyroid'], scope_label='ung thư đại trực tràng hoặc ung thư tuyến giáp', special=GENE_SPECIAL),
    dict(key=(2, 98), id='egfr', name='Xét nghiệm đột biến gen EGFR', official_name='Xét nghiệm đột biến gen EGFR',
         aliases=['egfr', 'e gfr', 'đột biến gen egfr'], consolidated_pages=[50], rule='gene', marker=True,
         scope=['nsclc'], scope_label='ung thư phổi không tế bào nhỏ', special=GENE_SPECIAL,
         expected_conditions=['Chẩn đoán đột biến gen EGFR trong điều trị ung thư phổi không tế bào nhỏ.'],
         branches=[{'id': 'nsclc', 'disease': 'Ung thư phổi không tế bào nhỏ', 'purpose': 'Chẩn đoán đột biến gen EGFR trong điều trị'}]),
    dict(key=(2, 99), id='kras', name='Xét nghiệm đột biến gen KRAS', official_name='Xét nghiệm đột biến gen KRAS',
         aliases=['kras', 'đột biến gen kras'], consolidated_pages=[50], rule='gene', marker=True,
         scope=['colorectal'], scope_label='ung thư đại trực tràng', special=GENE_SPECIAL),
    dict(key=(2, 100), id='scc', name='Định lượng SCC (Squamous cell carcinoma antigen) [Máu]',
         official_name='Định lượng SCC (Squamous cell carcinoma antigen)[Máu]',
         aliases=['định lượng scc', 'squamous cell carcinoma antigen'], explicit_aliases=['scc'], consolidated_pages=[50], rule='scope',
         scope=['nsclc', 'sclc', 'lung_unspecified', 'cervical', 'nasopharynx', 'larynx', 'oral', 'sinus', 'esophagus', 'vulva', 'penis', 'skin'],
         scope_label='ung thư biểu mô tế bào vảy của phổi, cổ tử cung, vòm mũi họng, thanh quản - hạ họng, khoang miệng, xoang mặt, thực quản, âm hộ, dương vật, da',
         scope_note='Dòng này yêu cầu ung thư biểu mô tế bào vảy và mục đích theo dõi đáp ứng điều trị, phát hiện tái phát hoặc di căn xa; chatbot chưa tự xác nhận hai điểm này.'),
    dict(key=(2, 101), id='pathology', name='Các xét nghiệm giải phẫu bệnh', official_name='Các xét nghiệm giải phẫu bệnh',
         aliases=['giải phẫu bệnh', 'xét nghiệm giải phẫu bệnh'], explicit_aliases=['mô bệnh học'], consolidated_pages=[50]),
]

# ---- 17/VBHN-BYT rows not amended by TT39 (scan; transcribed by reading the page image). ----
PAIR = 'paired'   # Danh mục 1: each condition has its own "Tỷ lệ, mức giá thanh toán" cell.
VBHN_ROWS = [
    dict(list=1, row=8, id='cbc_auto', pages=[26], name='Tổng phân tích tế bào máu ngoại vi bằng hệ thống tự động hoàn toàn (có nhuộm tiêu bản tự động)',
         aliases=['tổng phân tích tế bào máu', 'tế bào máu ngoại vi'], loose_aliases=['công thức máu'],
         name_note='Dòng này chỉ quy định cho kỹ thuật “hệ thống tự động hoàn toàn (có nhuộm tiêu bản tự động)”, không phải mọi xét nghiệm công thức máu.',
         conditions=['Nghi ngờ bệnh lý về tế bào máu và có bất thường về số lượng tế bào máu, có kết quả đọc tiêu bản do máy tự động kéo nhuộm.', 'Trường hợp khác.'],
         rate=['Thanh toán 01 lần/một lượt khám bệnh, chữa bệnh theo giá dịch vụ Tổng phân tích tế bào máu bằng hệ thống tự động hoàn toàn.',
               'Thanh toán theo giá DVKT “Tổng phân tích tế bào máu ngoại vi bằng máy laser”.'], rate_mode=PAIR,
         source_note='Cụm “một lượt khám bệnh, chữa bệnh” là nội dung đã sửa theo khoản 3 Điều 1 TT39/2024 (chú thích 22 của bản hợp nhất).'),
    dict(list=1, row=9, id='bnp', pages=[26], name='Định lượng BNP', aliases=['bnp', 'định lượng bnp'],
         conditions=['Chẩn đoán, theo dõi suy tim trên người bệnh suy thận.', 'Chẩn đoán, theo dõi suy tim trên người bệnh không suy thận.'],
         rate=['Thanh toán bằng giá DVKT.', 'Thanh toán theo giá DVKT “Định lượng Pro-BNP”.'], rate_mode=PAIR),
    dict(list=1, row=13, id='liquiprep', pages=[28], name='Xét nghiệm tế bào học bằng phương pháp Liqui Prep',
         aliases=['liqui prep', 'liquiprep'], loose_aliases=['tế bào học cổ tử cung', 'tế bào cổ tử cung'],
         name_note='Dòng này chỉ quy định cho xét nghiệm tế bào học bằng phương pháp Liqui Prep, không phải mọi xét nghiệm tế bào học cổ tử cung.',
         foreign=r'\b(?:thinprep|thin prep|pap|papanicolaou|cell prep|cellprep|surepath)\b',
         conditions=['Sau điều trị đối với người bệnh đã được khoét chóp cổ tử cung một phần và chẩn đoán tế bào học cổ tử cung - HSIL (tổn thương nội biểu mô vảy độ cao), tương đương đã được chẩn đoán mô bệnh học CIN 2,3',
                     'Các chỉ định khác.'],
         rate=['Thanh toán bằng giá DVKT.', 'Thanh toán theo giá DVKT “Nhuộm phiến đồ tế bào theo Papanicolaou”.'], rate_mode=PAIR),
    dict(list=2, row=67, id='serum_ife', pages=[44], name='Điện di miễn dịch huyết thanh', aliases=['điện di miễn dịch huyết thanh', 'điện di miễn dịch'],
         conditions=['Thanh toán đối với các trường hợp sau:', 'a) Tăng Gama Globulin máu;', 'b) Bệnh lý đơn dòng globulin miễn dịch.']),
    dict(list=2, row=68, id='antibody_id', pages=[44], name='Định danh kháng thể bất thường', aliases=['định danh kháng thể bất thường', 'kháng thể bất thường'],
         conditions=['Kết quả xét nghiệm kháng thể bất thường dương tính.']),
    dict(list=2, row=70, id='heme_gene_quant', pages=[44], name='Định lượng gen bệnh máu ác tính bằng kỹ thuật Real - Time PCR',
         aliases=['định lượng gen bệnh máu ác tính', 'gen bệnh máu ác tính'],
         conditions=['Theo dõi điều trị bằng hóa chất hoặc ghép tế bào gốc tạo máu ở người bệnh máu ác tính đã xác định đột biến gen bằng phương pháp định tính.']),
    dict(list=2, row=71, id='factor_xiii', pages=[44], name='Định lượng yếu tố XIII (Tên khác: Định lượng yếu tố ổn định sợi huyết)',
         aliases=['yếu tố xiii', 'yếu tố 13', 'yếu tố ổn định sợi huyết'],
         conditions=['Chẩn đoán và theo dõi điều trị rối loạn đông máu do thiếu yếu tố XIII.']),
    dict(list=2, row=73, id='hla_sso', pages=[45],
         name='Định type HLA độ phân giải cao cho 1 locus (Locus A, hoặc Locus B, hoặc Locus C, hoặc Locus DR, hoặc Locus DQ, hoặc Locus DP) bằng kỹ thuật PCR-SSO',
         aliases=['hla độ phân giải cao', 'định type hla độ phân giải cao', 'pcr sso', 'hla pcr sso'], loose_aliases=['hla', 'định type hla'],
         name_note='Dòng này chỉ quy định định type HLA độ phân giải cao cho 1 locus bằng kỹ thuật PCR-SSO; xét nghiệm HLA bằng kỹ thuật khác không thuộc dòng này.',
         foreign=HLA_OTHER,
         conditions=['Thanh toán đối với các trường hợp sau:', 'a) Người bệnh có chỉ định ghép tạng hoặc ghép tế bào gốc đồng loài khi cần kết quả HLA ở độ phân giải cao.',
                     'b) Đơn vị tế bào gốc hoặc tạng ghép cho người bệnh.']),
    dict(list=2, row=74, id='pivka', pages=[45], name='Định lượng PIVKA', aliases=['pivka', 'pivka ii', 'pivka 2'],
         conditions=['Khi các phương pháp chẩn đoán hình ảnh phát hiện có khối u gan + AFP dưới 400ng/ml; đánh giá hiệu quả điều trị, theo dõi di căn, tái phát.']),
    dict(list=2, row=75, id='gene_sequencing', pages=[45, 46], name='Xét nghiệm giải trình tự gen',
         aliases=['giải trình tự gen', 'giải trình tự gene', 'chimerism'],
         conditions=['Thanh toán khi thực hiện đối với một trong các trường hợp sau:',
                     'a) Phân tích đột biến gen bệnh máu (gen có nhiều loại đột biến hoặc đột biến trên nhiều gen). Đột biến gen kháng thuốc với các thuốc điều trị đích ở người bệnh Lơ xê mi kinh dòng bạch cầu hạt: Đã xác định dương tính với gen BCR-ABL bằng xét nghiệm RT - PCR và được điều trị bằng thuốc ức chế Tyrosine kinase sau 03 tháng nhưng không đáp ứng hoặc mất đáp ứng trong quá trình điều trị.',
                     'b) Phân tích tồn dư tối thiểu ở bệnh máu ác tính đối với người bệnh đã được chẩn đoán bệnh máu ác tính bằng xét nghiệm huyết đồ, tủy đồ thuộc một trong các trường hợp sau:',
                     '- Xét nghiệm RT-PCR âm tính với các gen AML1-ETO, PML-RAR a, CBFB-MIH11, NPM1, FLT3 (đối với bệnh Lơ xê mi cấp dòng tủy AML) hoặc gen BCR-ABL, TEL- AML1, MLL-AF4, E2A-PBX1 (đối với bệnh Lơ xê mi cấp dòng lympho ALL);',
                     '- Xét nghiệm di truyền tế bào âm tính với del (5q), del (7q), trisomy 8, del (20q) hoặc âm tính với gen JAK2 V617F (đối với bệnh tăng sinh tủy mạn MPN).',
                     'c) Xét nghiệm Chimerism sau ghép tế bào gốc tạo máu: Thực hiện khi không tìm được marker dương tính với xét nghiệm RQ-PCR. Thanh toán tối đa 04 lần trong 06 tháng đầu sau ghép; những lần sau cách nhau tối thiểu 02 tháng khi có hiện tượng thải ghép hoặc nguy cơ tái phát cần phải điều chỉnh thuốc ức chế miễn dịch.']),
    dict(list=2, row=77, id='thalassemia_rflp', pages=[46], name='Phát hiện gen bệnh Thalassemia bằng kỹ thuật PCR-RFLP',
         aliases=['gen bệnh thalassemia', 'gen thalassemia', 'pcr rflp'], explicit_aliases=['thalassemia'],
         conditions=['Bệnh Thalassemia hoặc nghi ngờ bệnh Thalassemia.']),
    dict(list=2, row=78, id='thalassemia_pcr', pages=[46], name='Xét nghiệm phát hiện đột biến gen thalassemia bằng kỹ thuật PCR',
         aliases=['đột biến gen thalassemia', 'gen thalassemia'], explicit_aliases=['thalassemia'],
         conditions=['Bệnh Thalassemia hoặc nghi ngờ bệnh Thalassemia.']),
    dict(list=2, row=82, id='marrow_ihc', pages=[47], name='Xét nghiệm và chẩn đoán hóa mô miễn dịch tủy xương cho một dấu ấn (Marker) trên máy nhuộm tự động',
         aliases=['hóa mô miễn dịch tủy xương'],
         conditions=['Xác định loại tế bào trong tủy xương: u lympho xâm lấn tủy, u lympho thể tủy, đa u tủy xương, lơ xê mi cấp, lơ xê mi kinh dòng lympho, hội chứng tăng sinh lympho, rối loạn sinh tủy hoặc ung thư di căn tủy.']),
    dict(list=2, row=83, id='probnp', pages=[47], name='Định lượng Pro-BNP', aliases=['pro bnp', 'probnp', 'nt probnp', 'nt pro bnp', 'định lượng pro bnp'],
         conditions=['Chẩn đoán, theo dõi suy tim.']),
    dict(list=2, row=85, id='cdiff', pages=[48], name='Clostridium nuôi cấy, định danh/Clostridium difficile miễn dịch tự động',
         aliases=['clostridium difficile', 'clostridium', 'c difficile', 'c diff'],
         conditions=['Người bị tiêu chảy nghi ngờ nhiễm C.difficle sau điều trị kháng sinh.'], source_note='Nguồn in “C.difficle”; giữ nguyên văn.'),
    dict(list=2, row=86, id='cmv_pcr', pages=[48], name='CMV Real-time PCR', aliases=['cmv real time pcr', 'cmv pcr', 'pcr cmv'], explicit_aliases=['cmv', 'cytomegalovirus'],
         conditions=['Chẩn đoán để điều trị các bệnh lý não, gan, mắt, ghép tạng, ghép tế bào gốc, sốt kéo dài hoặc tình trạng suy giảm miễn dịch không rõ nguyên nhân nghi ngờ do Cytomegalovirus.']),
    dict(list=2, row=89, id='hp_culture', pages=[49], name='Helicobacter pylori nuôi cấy, định danh và kháng thuốc',
         aliases=['helicobacter pylori nuôi cấy', 'nuôi cấy helicobacter pylori', 'nuôi cấy h pylori', 'h pylori nuôi cấy', 'nuôi cấy hp', 'hp nuôi cấy'],
         conditions=['Sau điều trị kháng sinh trên 15 ngày Helicobacter pylori vẫn dương tính.']),
    dict(list=2, row=90, id='fungi_seq', pages=[49], name='Vi nấm giải trình tự gene', aliases=['vi nấm giải trình tự gene', 'vi nấm giải trình tự gen', 'giải trình tự gene vi nấm', 'giải trình tự gen vi nấm'],
         conditions=['Chỉ định định danh các vi nấm không nuôi cấy được, khó nuôi cấy, nuôi cấy trên 15 ngày hoặc chưa định hướng được căn nguyên vi nấm gây bệnh.']),
    dict(list=2, row=91, id='hiv_resistance', pages=[49], name='HIV kháng thuốc giải trình tự gene', aliases=['hiv kháng thuốc', 'kháng thuốc hiv'],
         conditions=['Người bệnh được điều trị theo phác đồ điều trị HIV/AIDS của Bộ Y tế nhưng nghi ngờ kháng thuốc.']),
    dict(list=2, row=92, id='hcv_genotype', pages=[49], name='HCV genotype giải trình tự gene', aliases=['hcv genotype', 'genotype hcv', 'kiểu gen hcv'],
         conditions=['Chỉ định khi cần khẳng định genotype cho điều trị, khi DVKT “HCV genotype Real- time PCR” không thể xác định được genotype.']),
    dict(list=2, row=93, id='hbv_resistance', pages=[49], name='HBV kháng thuốc giải trình tự gene', aliases=['hbv kháng thuốc', 'kháng thuốc hbv'],
         conditions=['Người bệnh được điều trị theo hướng dẫn điều trị của Bộ Y tế nhưng nghi ngờ kháng thuốc.']),
    dict(list=2, row=94, id='virus_seq', pages=[49], name='Virus giải trình tự gene', aliases=['virus giải trình tự gene', 'virus giải trình tự gen', 'vi rút giải trình tự gen', 'giải trình tự gene virus', 'giải trình tự gen virus'],
         conditions=['Để định danh virus khi chưa định hướng được căn nguyên gây bệnh bằng các kỹ thuật xét nghiệm vi sinh khác.']),
    dict(list=2, row=95, id='bacteria_seq', pages=[49], name='Vi khuẩn định danh giải trình tự gene',
         aliases=['vi khuẩn định danh giải trình tự gene', 'vi khuẩn định danh giải trình tự gen', 'vi khuẩn giải trình tự gene', 'vi khuẩn giải trình tự gen', 'giải trình tự gen vi khuẩn', 'giải trình tự gene vi khuẩn'],
         conditions=['Chỉ định để định danh các vi khuẩn không nuôi cấy được, khó nuôi cấy, nuôi cấy trên 15 ngày không có kết quả hoặc chưa định hướng được căn nguyên vi khuẩn gây bệnh.']),
    dict(list=2, row=102, id='pas_stain', pages=[50], name='Nhuộm PAS Periodic Acid Schiff', aliases=['nhuộm pas', 'periodic acid schiff'],
         conditions=['Không thanh toán đối với bệnh phẩm nạo hút buồng tử cung, ruột thừa (trừ trường hợp u ruột thừa).']),
]


def read_tt39(pdf):
    """Every table row of the appendix: {(list, tt35): {name, cond, rate, segments}}."""
    rows, current, listno = {}, None, 1
    for number, page in enumerate(pdf.pages, 1):
        if 'DANH MỤC 2' in (page.extract_text() or '')[:200]:
            listno = 2
        for table in page.find_tables():
            for geometry, cells in zip(table.rows, table.extract()):
                cells = [(c or '').strip() for c in cells]
                if len(cells) < 4:
                    continue
                first, second = cells[0].replace('.', '').strip(), cells[1].replace('.', '').strip()
                if first.isdigit() and second.isdigit():
                    current = {'appendix_row': int(first), 'name': [cells[2]], 'cond': [cells[3]], 'rate': [cells[4]] if len(cells) > 4 else [],
                               'segments': [(number, geometry.bbox)]}
                    rows[(listno, int(second))] = current
                elif current and not first and any(cells[2:]) and not cells[2].startswith('DVKT'):
                    current['name'].append(cells[2]); current['cond'].append(cells[3])   # row continued on the next page
                    if len(cells) > 4:
                        current['rate'].append(cells[4])
                    current['segments'].append((number, geometry.bbox))
    return rows


def main():
    appendix, vbhn_pdf = DEST / '39-2024-appendix.pdf', DEST / '17-vbhn-2024.pdf'
    limitations = ('Tra cứu nguồn ngày 10/11/2026 chưa phát hiện văn bản sửa các dòng này sau TT39/2024. Trang lịch sử hiệu lực VBPL không truy cập được; '
                   'không khẳng định đã rà soát đầy đủ mọi văn bản mới.')
    source = {
        'document_id': 'TT39_2024_LABS', 'title': 'Thông tư 39/2024/TT-BYT',
        'published_at': '2024-11-17', 'effective_from': '2025-01-01', 'checked_as_of': CHECKED,
        'official_url': 'https://vanban.chinhphu.vn/?docid=211771&pageid=27160',
        'source_url': 'https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/11/39-byt-kem.pdf',
        'local_url': '/sources/labs/39-2024-appendix.pdf', 'sha256': digest(appendix),
        'review_status': 'Đã đối chiếu ảnh PDF và văn bản hợp nhất; chờ bệnh viện thẩm định.',
        'review_limitations': limitations,
        'related_documents': [
            {'title': 'Thông tư 35/2016/TT-BYT, sửa đổi bởi TT50/2017, TT13/2020 và TT39/2024',
             'url': 'https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/01/17-vbhn-byt.pdf',
             'local_url': '/sources/labs/17-vbhn-2024.pdf', 'sha256': digest(vbhn_pdf)},
            {'title': 'Thông tư 39/2024/TT-BYT · Nội dung sửa đổi',
             'url': 'https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/11/39-byt.pdf',
             'local_url': '/sources/labs/39-2024-main.pdf', 'sha256': digest(DEST / '39-2024-main.pdf')},
        ],
    }
    vbhn = {
        'document_id': 'TT35_VBHN17_LABS', 'title': 'Văn bản hợp nhất 17/VBHN-BYT (Thông tư 35/2016/TT-BYT và các lần sửa đổi)',
        'effective_from': '2025-01-01', 'checked_as_of': CHECKED,
        'official_url': 'https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/01/17-vbhn-byt.pdf',
        'source_url': 'https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/01/17-vbhn-byt.pdf',
        'local_url': '/sources/labs/17-vbhn-2024.pdf', 'sha256': digest(vbhn_pdf),
        'review_status': 'Chép từ ảnh trang của bản scan (AI đọc, không dùng lớp OCR); chờ bệnh viện thẩm định.',
        'review_limitations': 'Các dòng này không bị TT39/2024 sửa nên chỉ có trong bản hợp nhất dạng scan. ' + limitations,
    }
    services = []
    with pdfplumber.open(appendix) as pdf:
        table = read_tt39(pdf)
        for spec in TT39_ROWS:
            listno, tt35 = spec.pop('key')
            found = table[(listno, tt35)]
            printed = ' '.join(' '.join(found['name']).split())
            assert squeeze(printed) == squeeze(spec['official_name']), (spec['id'], printed)
            conditions = paragraphs('\n'.join(found['cond']))
            expected = spec.pop('expected_conditions', None)
            if expected:   # the two pilot rows keep their hand-checked wording
                assert conditions == expected, (spec['id'], conditions)
            assert squeeze(''.join(conditions)) == squeeze(''.join(found['cond'])), spec['id']
            rate = paragraphs('\n'.join(found['rate']))
            images = []
            for n, (number, bbox) in enumerate(found['segments'], 1):
                name = f"{spec['id']}-row.png" if n == 1 else f"{spec['id']}-row-{n}.png"
                pdf.pages[number - 1].crop(bbox).to_image(resolution=180).save(str(DEST / name))
                images.append({'url': '/sources/labs/' + name, 'sha256': digest(DEST / name), 'page': number})
            pages = sorted({number for number, _ in found['segments']})
            row = dict(spec, doc='tt39', transcription='text_layer', list=listno, appendix_row=found['appendix_row'], original_row=tt35,
                       page=pages[0], pages=pages, method=None, service_code=None, conditions=conditions, rate=rate,
                       rate_mode='row' if rate else None, quote='\n'.join(conditions), images=images,
                       locator=f"Danh mục {listno} · STT {found['appendix_row']} (STT {tt35} theo TT35) · trang PDF {'–'.join(map(str, pages))}")
            services.append(row)
    with pdfplumber.open(vbhn_pdf) as pdf:
        rendered = {}
        for spec in VBHN_ROWS:
            images = []
            for number in spec['pages']:
                if number not in rendered:
                    name = f'vbhn-p{number}.png'
                    pdf.pages[number - 1].to_image(resolution=100).original.convert('L').save(str(DEST / name), optimize=True)
                    rendered[number] = {'url': '/sources/labs/' + name, 'sha256': digest(DEST / name), 'page': number}
                images.append(rendered[number])
            row = dict(spec, doc='vbhn', transcription='scan_read', official_name=spec['name'], appendix_row=None, original_row=spec.pop('row'),
                       page=spec['pages'][0], consolidated_pages=spec['pages'], method=None, service_code=None,
                       rate=spec.get('rate', []), rate_mode=spec.get('rate_mode'), quote='\n'.join(spec['conditions']), images=images)
            row['locator'] = f"Danh mục {row['list']} · STT {row['original_row']} · trang {'–'.join(map(str, row['pages']))} của bản hợp nhất"
            services.append(row)
    for row in services:
        row['viewer_url'] = f"/sources/labs/{row['id']}.html#source-row"
        row['image_url'] = row['images'][0]['url']
        row['image_sha256'] = row['images'][0]['sha256']
    services.sort(key=lambda r: (r['list'], r['original_row']))
    ids = [r['id'] for r in services]
    assert len(ids) == len(set(ids))
    bundle = {'schema_version': 2, 'source': source, 'documents': {'tt39': source, 'vbhn': vbhn}, 'services': services}
    (ROOT / 'data/lab_services.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Built {len(services)} service rows: {sum(r['doc'] == 'tt39' for r in services)} from the TT39 text layer, "
          f"{sum(r['doc'] == 'vbhn' for r in services)} read from the 17/VBHN-BYT scan.")


if __name__ == '__main__':
    main()
