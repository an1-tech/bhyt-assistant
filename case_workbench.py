"""Case workbench: source-linked preliminary comparison, no payment adjudication."""
import hashlib
import json
import re

FIELD_LABELS={"diagnosis":"Chẩn đoán / chỉ định điều trị","stage":"Giai đoạn / mức độ bệnh",
    "biomarkers":"Xét nghiệm / dấu ấn liên quan","treatment":"Bối cảnh điều trị",
    "product_name":"Tên sản phẩm","registration":"Số đăng ký (nếu có)"}
LIMITS={"diagnosis":500,"stage":200,"biomarkers":400,"treatment":700,"product_name":160,"registration":100}
PRIVATE=re.compile(r"(?i)(?:họ tên|ho ten|mã bệnh án|ma benh an|số thẻ bhyt|so the bhyt|số điện thoại)\s*[:=]|\b(?:0[35789]\d{8}|\d{12})\b")

class CaseWorkbench:
    def __init__(self,corpus):
        self.c=corpus
        data=json.loads((corpus.data/"case_profiles.json").read_text(encoding="utf-8"))
        if data.get("version")!=1:raise ValueError("Unsupported case profiles")
        self.profiles=data["profiles"]
        for id,profile in self.profiles.items():
            row=corpus.by_id.get(id)
            if not row or row["ingredient"]!=profile["ingredient"] or hashlib.sha256(row.get("conditions_verbatim","").encode()).hexdigest()!=profile["note_sha256"]:
                raise ValueError("Case profile is stale: "+id)

    def drugs(self,query):
        from engine import normalize
        q=normalize(query)
        choices=[]
        for name,rows in self.c.names.items():
            if q and q not in name and not any(q==str(r["stt"]) for r in rows):continue
            choices.append({"id":rows[0]["record_id"],"ingredient":rows[0]["ingredient"],
                "stt":rows[0]["stt"],"appendix":rows[0].get("appendix","I"),
                "variants":[{"id":r["record_id"],"route":r["route"]} for r in rows]})
        choices.sort(key=lambda x:(not normalize(x["ingredient"]).startswith(q),x["ingredient"]))
        return choices[:15]

    def schema(self,id):
        if not isinstance(id,str) or id not in self.c.by_id:raise ValueError("Chọn đúng dòng thuốc trong danh mục.")
        row=self.c.by_id[id]
        profile=self.profiles.get(id)
        fields=list(profile["fields"]) if profile else []
        topics=self.c.supplemental.topics(row["ingredient"])
        if topics and not any(f["key"]=="indication" for f in fields):
            fields.append({"key":"clinical_topic","label":"Hướng dẫn cần tham khảo (chưa xác nhận chỉ định)","choices":topics})
        return {"drug":{"id":id,"ingredient":row["ingredient"],"route":row["route"],
                    "stt":row["stt"],"appendix":row.get("appendix","I")},
            "fields":fields,
            "source_coverage":self.c.supplemental.coverage(row,{}),
            "has_preliminary_profile":bool(profile),
            "conditions_verbatim":row.get("conditions_verbatim",""),
            "profile_status":"Chưa được Dược/BHYT thẩm định",
            "product_registry_available":False}

    def evaluate(self,payload):
        if not isinstance(payload,dict):raise ValueError("Dữ liệu ca đối chiếu không hợp lệ.")
        if set(payload)-{"drug_id","facts","answers","department"}:raise ValueError("Trường dữ liệu ca không hợp lệ.")
        schema=self.schema(payload.get("drug_id"))
        id=schema["drug"]["id"];row=self.c.by_id[id]
        facts=payload.get("facts",{});answers=payload.get("answers",{})
        if not isinstance(facts,dict) or not isinstance(answers,dict):raise ValueError("Thông tin đối chiếu không hợp lệ.")
        if set(facts)-set(LIMITS):raise ValueError("Trường thông tin chưa được hỗ trợ.")
        for key,value in facts.items():
            if not isinstance(value,str) or len(value)>LIMITS[key]:raise ValueError("Thông tin "+FIELD_LABELS[key]+" quá dài hoặc không hợp lệ.")
            if PRIVATE.search(value):raise ValueError("Chỉ nhập bối cảnh không định danh; bỏ tên, mã bệnh án, số thẻ và số điện thoại.")
        allowed={f["key"]:{x["value"] for x in f["choices"]}|{""} for f in schema["fields"]}
        if set(answers)-set(allowed):raise ValueError("Câu trả lời không thuộc thuốc đang đối chiếu.")
        for key,value in answers.items():
            if not isinstance(value,str) or value not in allowed[key]:raise ValueError("Giá trị đối chiếu không hợp lệ.")
        # Hidden answers cannot survive a branch change or be used to choose a rate.
        for f in schema["fields"]:
            if f.get("show_when") and any(answers.get(k)!=v for k,v in f["show_when"].items()):
                answers={k:v for k,v in answers.items() if k!=f["key"]}
        criteria=[]
        def add(key,label,status,value,reason,source_ids=None):
            criteria.append({"key":key,"label":label,"status":status,"value":value or "Chưa cung cấp",
                "reason":reason,"source_ids":source_ids or []})
        add("product","Đúng sản phẩm và nhãn đăng ký","needs_review",
            facts.get("product_name",""),"Tên sản phẩm do người dùng nhập; chưa có nhãn/đăng ký đã xác minh để đối chiếu.")
        add("diagnosis","Bối cảnh ca bệnh","recorded" if facts.get("diagnosis","").strip() else "missing",
            facts.get("diagnosis",""),"Chỉ ghi nhận nội dung nhập, chưa suy ra chẩn đoán hoặc điều kiện từ văn bản tự do.")
        source_ids=[id]
        checks=[]
        def check(key,label,good):
            value=answers.get(key,"")
            f=next(x for x in schema["fields"] if x["key"]==key)
            display=next((x["label"] for x in f["choices"] if x["value"]==value),"")
            status="missing" if not value else "matched" if value in good else "not_matched"
            checks.append(status)
            add(key,label,status,display,
                "Đối chiếu sơ bộ với ghi chú danh mục; cần đọc đầy đủ nguyên văn và quy định chung.",source_ids)
        candidate=None
        if schema["has_preliminary_profile"]:
            stt=row["stt"]
            if stt==402:
                check("indication","Chỉ định trong ghi chú",{"breast","gastric"})
                check("her2","Điều kiện HER2",{"positive"})
                if answers.get("indication")=="gastric":check("extent","Mức độ ung thư dạ dày",{"advanced"})
                if all(s=="matched" for s in checks):
                    candidate={"percentage":60 if answers["indication"]=="breast" else 50,
                        "scope":"Ung thư vú có HER2 dương tính" if answers["indication"]=="breast" else "Ung thư dạ dày tiến xa hoặc di căn có HER2 dương tính","source_id":id}
                add("facility","Phạm vi áp dụng tại cơ sở","needs_review","Chưa xác minh",
                    "Ghi chú có điều kiện cơ sở. Phải đọc cùng TT37 và hướng dẫn áp dụng, không dùng riêng cột hạng cũ.",source_ids)
            elif stt in (394,395):
                check("indication","Chỉ định trong ghi chú",{"nsclc"});check("egfr","Điều kiện EGFR",{"positive"})
                if all(s=="matched" for s in checks):candidate={"percentage":50,"scope":"Ung thư phổi không phải tế bào nhỏ có EGFR dương tính","source_id":id}
            else:
                check("formulation","Dạng thuốc trong ghi chú",set(allowed["formulation"])-{""})
                value=answers.get("formulation")
                if value:candidate={"percentage":100 if value=="other" else 50,"scope":next(x["label"] for x in schema["fields"][0]["choices"] if x["value"]==value),"source_id":id}
        else:
            add("source_note","Điều kiện riêng trong danh mục","needs_review","Có ghi chú" if row.get("conditions_verbatim") else "Ô ghi chú trống",
                "Điều kiện của dòng này cần đối chiếu trực tiếp theo nguyên văn cùng quy định chung. Ô trống không suy ra thanh toán 100%.",source_ids)
        clinical=self.c.supplemental.for_case(row,answers)
        coverage=self.c.supplemental.coverage(row,answers)
        add("clinical_sources","Hướng dẫn Bộ Y tế / nhãn / Dược thư","needs_review","Chưa đủ bộ nguồn",
            coverage[1]["detail"]+" Nhãn sản phẩm và Dược thư còn cần bổ sung.",[x["id"] for x in clinical])
        add("local_scope","Điều kiện BHYT tại bệnh viện","needs_review","Chưa xác minh",
            "Cần kiểm tra danh mục, hợp đồng và phạm vi thực hiện tại cơ sở.")
        citations=[self.c.by_chunk[id]]
        citations+=self.c.policy_context(row["ingredient"],row.get("group","").startswith("8."))
        transition=id in self.c.transition_rules["mapping"]
        if transition:
            citations+=self.c.transition_chunks
            add("transition","Điều kiện chuyển tiếp","needs_review",facts.get("treatment",""),
                "Cần đối chiếu đầy đủ Điều 8 TT20/2022 và hồ sơ điều trị; nhánh dẫn chiếu tỷ lệ lịch sử vẫn cần xác minh.",self.c.transition_rules["chunk_ids"])
        citations=self.c.complete_context(list({c["id"]:c for c in citations}.values()))
        counts={s:sum(x["status"]==s for x in criteria) for s in ("matched","not_matched","missing","needs_review","recorded")}
        headline="Có thông tin chưa khớp ghi chú danh mục" if counts["not_matched"] else "Cần bổ sung thông tin để đối chiếu" if counts["missing"] else "Đã đối chiếu sơ bộ; còn căn cứ cần xác minh"
        return {"status":"requires_review","headline":headline,"drug":schema["drug"],"facts":facts,"answers":answers,
            "criteria":criteria,"counts":counts,"candidate_source_rate":candidate,
            "conditions_verbatim":row.get("conditions_verbatim",""),"citations":[self.c.citation(c) for c in citations]+clinical,
            "source_checked_as_of":self.c.supplemental.registry["checked_as_of"],
            "source_coverage":coverage,
            "next_steps":[x["label"]+": "+x["reason"] for x in criteria if x["status"] in ("missing","not_matched","needs_review")],
            "notice":"Kết quả là đối chiếu sơ bộ dữ kiện đã nhập với bộ nguồn; bảng điều kiện chưa được Dược/BHYT thẩm định. Chưa xác nhận quyền lợi hay số tiền thanh toán.",
            "snapshot":"2026-11-06","profile_review":"prototype_extraction_not_hospital_validated","payment_eligibility":None,"ai_used":False}
