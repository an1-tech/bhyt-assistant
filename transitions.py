"""Verified source supplement and non-adjudicating transition lookup."""
import hashlib
import json
import re

def load_transition_bundle(data, rows):
    rules=json.loads((data/"transition_rules.json").read_text(encoding="utf-8"))
    if rules.get("version")!=1:
        raise ValueError("Unsupported transition rules")
    # Fixed, local filenames only; the manifest is not an arbitrary file loader.
    file=data/"rag_transition.jsonl"
    pdf=data/"sources/15-vbhn-byt-2024.pdf"
    if hashlib.sha256(file.read_bytes()).hexdigest()!=rules["chunks_sha256"]:
        raise ValueError("Transition text checksum mismatch")
    if hashlib.sha256(pdf.read_bytes()).hexdigest()!=rules["source_pdf_sha256"]:
        raise ValueError("Transition PDF checksum mismatch")
    chunks=[json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if [c["id"] for c in chunks]!=rules["chunk_ids"] or len(set(rules["chunk_ids"]))!=len(chunks):
        raise ValueError("Transition chunk set mismatch")
    article8=[c for c in chunks if c.get("article")==8]
    if [c["id"] for c in article8]!=rules["article8_ids"] or [c["page"] for c in article8]!=[4,5]:
        raise ValueError("Incomplete transition article")
    if not all(c.get("document_id")=="TT20_2022" and c.get("scope")=="transition_supplement" and c.get("default_retrieve") is True for c in chunks):
        raise ValueError("Invalid transition scope")
    by_id={r["record_id"]:r for r in rows}
    for id,rule in rules["mapping"].items():
        row=by_id.get(id)
        if not row or any(row[k]!=rule[k] for k in ("ingredient","route")):
            raise ValueError("Transition drug mapping mismatch: "+id)
        if rule["source_ids"]!=rules["chunk_ids"]:
            raise ValueError("Incomplete transition drug references")
    return chunks,rules

def transition_intent(normalized_query):
    q=normalized_query
    tt20=bool(re.search(r"(?:tt\s*20|thong tu 20|20 2022)",q))
    other=bool(re.search(r"(?:tt\s*37|thong tu 37|37 2024|06 2026)",q))
    return (("chuyen tiep" in q and (not other or tt20))
            or ("dieu 8" in q and tt20)
            or ("noi tru" in q and "2023" in q))

def transition_followup(normalized_query):
    return (normalized_query.startswith(("tu nam ","tu ngay ","bat dau ","tai phat","gian doan",
        "chuyen co so","chuyen vien","het thuoc","dung thuoc","su dung","co su dung","truoc ","sau ",
        "liposome","polymeric","dang liposome","dang erwinia"))
        or bool(re.match(r"^(?:nam )?(?:19|20)\d{2}\b",normalized_query)))

def transition_notice(rules, result):
    mapped=[]
    for row in result.get("results",[]):
        for id in row.get("record_ids",[]):
            rule=rules["mapping"].get(id)
            if rule and rule not in mapped:mapped.append(rule)
    text="Đã bổ sung đầy đủ Điều 8 Thông tư 20/2022 (trang 4–5) và ngày hiệu lực 01/03/2023; xem các đoạn căn cứ đi kèm."
    if mapped:
        text+=" "+" ".join(rule["ingredient"]+": "+rule["note"] for rule in mapped)
    text+=" Không tự suy ra đủ điều kiện chuyển tiếp từ tên thuốc hoặc năm điều trị. Cần đối chiếu hồ sơ và các trường hợp tại điểm a–đ."
    if not mapped or any(b["rate_reference"]=="TT40_2014_external_reference" for rule in mapped for b in rule["branches"]):
        text+=" Nhánh dẫn chiếu TT40/2014 chưa có bảng tỷ lệ lịch sử trong bộ nguồn, nên chưa tự tính tỷ lệ nhánh này."
    return text
