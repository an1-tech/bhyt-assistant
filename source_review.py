"""Apply traceable, image-checked OCR corrections without changing imported sources."""
import copy
import hashlib
import json

def apply_source_review(chunks, manifest_path):
    out=copy.deepcopy(chunks)
    if not manifest_path.exists():
        return out
    review=json.loads(manifest_path.read_text(encoding="utf-8"))
    if review.get("version") != 1:
        raise ValueError("Unsupported source review version")
    by={c["id"]:c for c in out}
    seen=set()
    for patch in review["patches"]:
        id=patch["id"]
        if id in seen or id not in by:
            raise ValueError("Invalid source review chunk: "+id)
        seen.add(id)
        c=by[id]
        if c["kind"] in ("drug_row","radiopharmaceutical_row"):
            raise ValueError("Drug rows require a separate structured review")
        if hashlib.sha256(c["text"].encode()).hexdigest()!=patch["expected_text_sha256"]:
            raise ValueError("Source review is stale: "+id)
        text=c["text"]
        for edit in patch["edits"]:
            if not edit["old"] or edit["count"]<1 or text.count(edit["old"])!=edit["count"]:
                raise ValueError("Source review edit mismatch: "+id)
            text=text.replace(edit["old"],edit["new"])
        c["text"]=text
        c["source_review"]={"status":"listed_ocr_corrections_checked",
            "date":review["review_date"],"original_text_sha256":patch["expected_text_sha256"],
            "evidence":patch["evidence"],"scope":patch["scope"],"hospital_validation":"pending"}
    for c in out:
        flags=[]
        docflag=review.get("document_flags",{}).get(c.get("document_id"))
        chunkflag=review.get("chunk_flags",{}).get(c["id"])
        if docflag: flags.append(copy.deepcopy(docflag))
        if chunkflag: flags.append(copy.deepcopy(chunkflag))
        if flags: c["source_review_flags"]=flags
    return out

def effective_fingerprint(chunks):
    payload=[{"id":c["id"],"text":c["text"]} for c in chunks]
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
