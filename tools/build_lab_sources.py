"""Build-time source extraction. Runtime needs only the Python standard library.

One complete service row is one chunk: its exceptions are never split away.
PDF bounds were visually checked against TT39 appendix and 17/VBHN-BYT.
Run again after any source replacement, then visually review both rows again.
"""
import hashlib
import json
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data/sources/labs'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = {
        'document_id': 'TT39_2024_LABS', 'title': 'Thông tư 39/2024/TT-BYT',
        'published_at': '2024-11-17', 'effective_from': '2025-01-01',
        'checked_as_of': '2026-11-10',
        'official_url': 'https://vanban.chinhphu.vn/?docid=211771&pageid=27160',
        'source_url': 'https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/11/39-byt-kem.pdf',
        'local_url': '/sources/labs/39-2024-appendix.pdf',
        'sha256': digest(DEST / '39-2024-appendix.pdf'),
        'review_status': 'Đã đối chiếu ảnh PDF và văn bản hợp nhất; chờ bệnh viện thẩm định.',
        'review_limitations': 'Tra cứu nguồn ngày 10/11/2026 chưa phát hiện văn bản sửa hai dòng này sau TT39/2024. Trang lịch sử hiệu lực VBPL không truy cập được; không khẳng định đã rà soát đầy đủ mọi văn bản mới.',
        'related_documents': [
            {'title': 'Thông tư 35/2016/TT-BYT, sửa đổi bởi TT50/2017, TT13/2020 và TT39/2024',
             'url': 'https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/01/17-vbhn-byt.pdf',
             'local_url': '/sources/labs/17-vbhn-2024.pdf', 'sha256': digest(DEST / '17-vbhn-2024.pdf')},
            {'title': 'Thông tư 39/2024/TT-BYT · Nội dung sửa đổi',
             'url': 'https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/11/39-byt.pdf',
             'local_url': '/sources/labs/39-2024-main.pdf', 'sha256': digest(DEST / '39-2024-main.pdf')},
        ],
    }
    rows = [
        dict(id='hba1c', name='Định lượng HbA1c [Máu]',
             official_name='Định lượng HbA1c [Máu] để xác định phác đồ điều trị hoặc để đánh giá kết quả điều trị bệnh đái tháo đường',
             aliases=['hba1c', 'hb a1c', 'a1c', 'hemoglobin a1c'],
             method=None, service_code=None, appendix_row=38, original_row=84, page=20,
             bbox=[70, 243, 559, 459], consolidated_pages=[47, 48],
             conditions=[
                 'a) Thanh toán cho xét nghiệm định lượng HbA1c trong máu đối với trường hợp đã được chẩn đoán xác định đái tháo đường để xác định phác đồ điều trị nếu chưa thực hiện xét nghiệm HbA1c trong vòng 90 ± 3 (chín mươi cộng trừ 3) ngày.',
                 'b) Thanh toán cho xét nghiệm từ lần thứ 2 trở đi để đánh giá kết quả điều trị bệnh đái tháo đường tối thiểu sau mỗi 90 ± 3 (chín mươi cộng trừ 3) ngày.',
                 'c) Trường hợp đái tháo đường thai kỳ có điều trị bằng insulin, thực hiện xét nghiệm HbA1C mỗi 30 ngày 01 lần.'
             ],
             branches=[
                 {'id': 'regimen', 'purpose': 'Xác định phác đồ điều trị', 'requires_confirmed_diabetes': True, 'timing': '90 ± 3 ngày'},
                 {'id': 'monitoring', 'purpose': 'Đánh giá kết quả điều trị từ lần thứ 2', 'timing': '90 ± 3 ngày'},
                 {'id': 'gestational_insulin', 'purpose': 'Đái tháo đường thai kỳ điều trị bằng insulin', 'interval_days': 30}
             ],
             timing_policy={'below_days':87, 'review_from_days':87, 'review_through_days':93, 'above_days':93,
                            'note':'87–93 ngày: cần đối chiếu cách áp dụng sai số với bộ phận BHYT; đây là giới hạn tự động hóa của prototype, không phải điều kiện pháp luật bổ sung.'}),
        dict(id='egfr', name='Xét nghiệm đột biến gen EGFR',
             official_name='Xét nghiệm đột biến gen EGFR', aliases=['egfr', 'e gfr', 'đột biến gen egfr'],
             method=None, service_code=None, appendix_row=43, original_row=98, page=21,
             bbox=[70, 385, 559, 450], consolidated_pages=[50],
             conditions=['Chẩn đoán đột biến gen EGFR trong điều trị ung thư phổi không tế bào nhỏ.'],
             branches=[{'id':'nsclc', 'disease':'Ung thư phổi không tế bào nhỏ', 'purpose':'Chẩn đoán đột biến gen EGFR trong điều trị'}])
    ]
    with pdfplumber.open(DEST / '39-2024-appendix.pdf') as pdf:
        for row in rows:
            page = pdf.pages[row['page'] - 1]
            crop = page.crop(tuple(row['bbox']))
            extracted = crop.extract_text()
            assert str(row['appendix_row']) in extracted and str(row['original_row']) in extracted
            assert ('HbA1c' if row['id']=='hba1c' else 'EGFR') in extracted
            # Exact text of the condition cell, normalized only for PDF wrapping.
            cell = page.crop((238, row['bbox'][1], row['bbox'][2], row['bbox'][3])).extract_text()
            assert ' '.join(cell.split()) == ' '.join(' '.join(row['conditions']).split())
            row['quote'] = '\n'.join(row['conditions'])
            row['locator'] = f"Danh mục 2 · STT {row['appendix_row']} (STT {row['original_row']} theo TT35) · trang PDF {row['page']}"
            row['viewer_url'] = f"/sources/labs/{row['id']}.html#source-row"
            row['image_url'] = f"/sources/labs/{row['id']}-row.png"
            image = DEST / f"{row['id']}-row.png"
            crop.to_image(resolution=180).save(str(image))
            row['image_sha256'] = digest(image)
    bundle = {'schema_version':1, 'source':source, 'services':rows}
    (ROOT / 'data/lab_services.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('Built two verified service rows and source crops.')


if __name__ == '__main__':
    main()
