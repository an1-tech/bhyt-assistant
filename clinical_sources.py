"""Clinical references stay separate from the BHYT answer/AI index and payment rules."""
import hashlib
import json
import re
from pathlib import PurePosixPath

STATUS_LABELS = {"reference_only":"Có trích đoạn tham khảo", "pdf_only":"Chỉ đối chiếu PDF", "pending_identity":"Chờ xác minh bản ký"}

class ClinicalSources:
    def __init__(self, data):
        self.data = data
        self.registry = json.loads((data / "supplemental_sources.json").read_text(encoding="utf-8"))
        if self.registry.get("version") != 1:
            raise ValueError("Unsupported clinical source registry")
        self.documents = self.registry["documents"]
        self.by_id = {d["id"]:d for d in self.documents}
        if len(self.by_id) != len(self.documents):
            raise ValueError("Duplicate clinical source ID")
        self.local_files = {}
        for d in self.documents:
            if d["status"] not in STATUS_LABELS or d.get("payment_authority") is not False:
                raise ValueError("Clinical source must have explicit non-payment scope")
            rel = PurePosixPath(d["local_file"])
            if len(rel.parts) != 3 or rel.parts[:2] != ("sources", "clinical") or not re.fullmatch(r"[a-z0-9-]+[.]pdf", rel.name):
                raise ValueError("Invalid clinical source path")
            if d["local_url"] != "/" + rel.as_posix():
                raise ValueError("Invalid clinical source URL")
            file = data / rel.as_posix()
            if not file.resolve().is_relative_to((data/"sources/clinical").resolve()) or hashlib.sha256(file.read_bytes()).hexdigest() != d["pdf_sha256"]:
                raise ValueError("Clinical source PDF checksum mismatch: " + d["id"])
            self.local_files[d["local_url"]] = file
            if not set(d["related_documents"]) <= self.by_id.keys():
                raise ValueError("Missing clinical amendment")
            for pages in d["anchors"].values():
                if not pages or any(type(p) is not int or not 1 <= p <= d["pages"] for p in pages):
                    raise ValueError("Invalid clinical page anchor")
        if self.registry["chunks_file"] != "clinical_pages.jsonl":
            raise ValueError("Invalid clinical chunk path")
        file = data / self.registry["chunks_file"]
        if hashlib.sha256(file.read_bytes()).hexdigest() != self.registry["chunks_sha256"]:
            raise ValueError("Clinical chunks checksum mismatch")
        self.pages = {}
        for line in file.read_text(encoding="utf-8").splitlines():
            c = json.loads(line);d = self.by_id[c["document_id"]]
            if type(c["page"]) is not int or not 1 <= c["page"] <= d["pages"] or c["id"] in self.pages:
                raise ValueError("Invalid or duplicate clinical chunk")
            if c["eligible_reference"] != (d["status"] == "reference_only"):
                raise ValueError("Unreviewed clinical text cannot be activated")
            self.pages[c["id"]] = c
        for d in self.documents:
            if {p["page"] for p in self.pages.values() if p["document_id"] == d["id"]} != set(range(1,d["pages"]+1)):
                raise ValueError("Incomplete clinical page bundle")

    def metadata(self):
        docs = [{k:v for k,v in d.items() if k not in ("local_file", "anchors")} | {
            "status_label":STATUS_LABELS[d["status"]],
            "chunks":sum(c["document_id"] == d["id"] and c["eligible_reference"] for c in self.pages.values())} for d in self.documents]
        return {"checked_as_of":self.registry["checked_as_of"], "documents":docs,
            "archived_pages":len(self.pages), "reference_pages":sum(p["eligible_reference"] for p in self.pages.values()),
            "scope":self.registry["scope"], "limitations":self.registry["limitations"]}

    def topics(self, ingredient):
        return [{"value":key,"label":label} for key,label in self.registry["topics"].items()
            if any(d["topic"] == key and ingredient in d["anchors"] for d in self.documents)]

    def selected(self, row, answers):
        topic = answers.get("indication") or answers.get("clinical_topic")
        return [d for d in self.documents if d["topic"] == topic and row["ingredient"] in d["anchors"]]

    def coverage(self, row, answers):
        available = self.topics(row["ingredient"]);docs = self.selected(row,answers)
        status = "missing";detail = "Chưa có hướng dẫn gắn với thuốc và chỉ định này trong đợt bổ sung."
        if available and not (answers.get("indication") or answers.get("clinical_topic")):
            status = "needs_selection";detail = "Có tài liệu theo chủ đề; chọn chỉ định / hướng dẫn cần tham khảo để dẫn đúng nguồn."
        elif docs:
            if all(d["status"] == "reference_only" for d in docs):
                status = "reference";detail = "Có trích đoạn kèm số trang; dùng tham khảo lâm sàng. Chưa xác nhận phù hợp ca bệnh, phiên bản mới nhất hay quyền lợi BHYT."
            elif any(d["status"] == "pending_identity" for d in docs):
                status = "pending";detail = "Đã lưu hướng dẫn và văn bản sửa đổi; PDF còn trống số/ngày ký. Chưa sử dụng nội dung để đối chiếu."
            else:
                status = "pdf_only";detail = "Có bản scan và văn bản sửa đổi đi kèm. Đọc trực tiếp PDF; chưa sử dụng lớp chữ/sơ đồ để đối chiếu tự động."
        return [{"title":"Danh mục và quy định BHYT", "status":"available", "detail":"Có nguyên văn trong bộ nguồn BHYT chốt 06/11/2026."},
            {"title":"Hướng dẫn chẩn đoán và điều trị", "status":status, "detail":detail},
            {"title":"Nhãn sản phẩm đã đăng ký", "status":"missing", "detail":"Chưa xác minh đúng sản phẩm, hàm lượng, dạng bào chế và bản nhãn Việt Nam; hướng dẫn điều trị không thay thế nhãn."},
            {"title":"Dược thư Quốc gia", "status":"missing", "detail":"Chưa có toàn văn chuyên luận chính thức tương ứng để nhập; không dùng bản sao thương mại làm nguồn đã xác minh."}]

    def citation(self, d, page, pointer=False):
        c = self.pages[d["id"] + "-PDF-" + str(page).zfill(3)]
        # Unsigned files and poor OCR are pointers only, never clinical excerpts.
        text = "Chỉ dẫn tài liệu: " + d["title"] + ". " + d["limitations"] if pointer else c["text"]
        return {"id":c["id"], "document_id":d["id"], "document_title":d["title"],
            "locator":d["decision"] + " · Trang PDF " + str(page), "page":page,
            "source_url":d["source_url"], "official_url":d["official_url"],
            "local_url":d["local_url"] + "#page=" + str(page), "excerpt":text,
            "kind":"clinical_document_pointer" if pointer else "clinical_reference", "checked_as_of":d["checked_as_of"],
            "review_status":d["status"], "scope":"Tham khảo lâm sàng; không xác nhận thanh toán BHYT",
            "source_review_flags":[{"note":d["limitations"]}]}

    def for_case(self, row, answers):
        result = []
        for d in self.selected(row, answers):
            pointer = d["status"] != "reference_only"
            for page in d["anchors"][row["ingredient"]]:
                result.append(self.citation(d,page,pointer))
            # Always keep amendments with the base guideline, including scanned diagrams.
            for id in d["related_documents"]:
                amendment = self.by_id[id]
                for page in range(1,amendment["pages"]+1):
                    result.append(self.citation(amendment,page,amendment["status"] != "reference_only"))
        return list({c["id"]:c for c in result}.values())
