"""General drug + indication chat. No patient form and no individual entitlement decision."""
import hashlib
import json
import re

TOPICS = {
    "breast":("Ung thư vú",r"(?:ung thu|ut) vu"),
    "gastric":("Ung thư dạ dày",r"(?:ung thu|ut) da day"),
    "nsclc":("Ung thư phổi không phải tế bào nhỏ",r"(?:ung thu|ut) phoi (?:the )?khong (?:phai )?te bao nho|nsclc"),
    "sclc":("Ung thư phổi tế bào nhỏ",r"(?:ung thu|ut) phoi (?:the )?te bao nho|sclc"),
    "lung":("Ung thư phổi (chưa nêu thể)",r"(?:ung thu|ut) phoi"),
    "colorectal":("Ung thư đại trực tràng",r"(?:ung thu|ut) (?:dai truc trang|dai trang|truc trang)"),
    "liver":("Ung thư gan",r"(?:ung thu|ut) gan"),
    "t2d":("Đái tháo đường típ 2",r"(?:dai thao duong|tieu duong) (?:tip|type|typ|loai) 2"),
}

def topics_in(text):
    from engine import normalize
    q=normalize(text);hits=[]
    for key,(_,pattern) in TOPICS.items():
        for m in re.finditer(r"\b(?:"+pattern+r")\b",q):
            if re.search(r"(?:khong phai|khong bi|loai tru)\s*$",q[max(0,m.start()-24):m.start()]):continue
            hits.append(key);break
    if "nsclc" in hits or "sclc" in hits:hits=[x for x in hits if x!="lung"]
    return hits

def explicit_negative(text, marker):
    from engine import normalize
    q=normalize(text).replace("her 2","her2")
    if re.search(r"(?:chua biet|khong ro|chua xac dinh|chua xet nghiem).{0,24}"+marker,q):return False
    # A mixed/uncertain question is described conditionally, never resolved to negative.
    if re.search(marker+r".{0,25}(?:hay|hoac)",q):return False
    return bool(re.search(r"\b"+marker+r"\s*(?:la |co )?(?:am tinh|negative|khong duong tinh)\b",q)
        or re.search(marker+r"\s*\(\s*-\s*\)|"+marker+r"\s*-",text,re.I))

class IndicationChat:
    def __init__(self,corpus):
        self.c=corpus
        self.profiles=json.loads((corpus.data/"case_profiles.json").read_text(encoding="utf-8"))["profiles"]
        for id,p in self.profiles.items():
            row=corpus.by_id.get(id)
            if not row or row["ingredient"]!=p["ingredient"] or hashlib.sha256(row.get("conditions_verbatim","").encode()).hexdigest()!=p["note_sha256"]:
                raise ValueError("Stale source-linked chat profile: "+id)

    def enrich(self,result,message,previous=None):
        from engine import normalize
        result["response_type"]="general_indication_chat"
        result["requires_patient_details"]=False
        result["payment_eligibility"]=None
        if not result.get("results"):return result
        previous=previous or {};current_topics=topics_in(message)
        previous_ids=previous.get("selected_ids",[])
        now_ids=result.get("state",{}).get("selected_ids",[])
        same=bool(set(previous_ids)&set(now_ids))
        prior=previous.get("context","") if same else ""
        # Explicitly named medicine or disease starts a new general question.
        # Unknown diseases must not silently inherit a previous, covered cancer.
        disease_signal=bool(re.search(r"\b(?:ung thu|benh|dai thao duong|tang huyet ap|viem|nhiem khuan|suy tim|hen|copd|dieu tri)\b",normalize(message)))
        reset_topic=bool(current_topics or self.c.resolve(message) or disease_signal)
        context=message if reset_topic or not prior else (prior+"; "+message)[-1000:]
        topics=current_topics if reset_topic else topics_in(prior)
        has_disease=bool(topics or re.search(r"\b(?:ung thu|benh|dai thao duong|tang huyet ap|dau|sot|viem|nhiem khuan|suy tim|hen|copd)\b",normalize(context)))
        supplemental=[]
        for row in result["results"]:
            row["question_answer"]=self.answer(row,topics,context,has_disease)
            row["question_answer"]["source_ids"]=row.get("record_ids",[])
            for id in row.get("record_ids",[]):
                source=self.c.by_id[id]
                for topic in topics:
                    if topic in {x["value"] for x in self.c.supplemental.topics(source["ingredient"])}:
                        supplemental+=self.c.supplemental.for_case(source,{"indication":topic})
        result["clinical_references"]=list({c["id"]:c for c in supplemental}.values())
        result["source_checked_as_of"]=self.c.supplemental.registry["checked_as_of"]
        result["followups"]=[]
        result["answer"]="\n\n".join(r["ingredient"]+": "+r["question_answer"]["conclusion"] for r in result["results"])
        result["answer_status"]="conditional_coverage" if all(r["question_answer"]["status"]=="conditional_coverage" for r in result["results"]) else "source_answer"
        result["state"]["context"]=context[-1000:]
        return result

    def answer(self,row,topics,context,has_disease):
        from engine import normalize
        name=row["ingredient"];ids=row.get("record_ids",[])
        answer={"status":"insufficient_evidence","conclusion":"", "conditions":[],"source_rate":None,
            "indications":[TOPICS[t][0] for t in topics],
            "scope":"Thông tin chung theo bộ nguồn BHYT chốt 06/11/2026; chưa được bệnh viện thẩm định. Tỷ lệ của thuốc không đồng nghĩa mức hưởng cá nhân hoặc số tiền quỹ chi trả."}
        if row.get("status")=="route_unmatched":
            answer["conclusion"]="Chưa có căn cứ cho đường dùng nêu trong câu hỏi. Các đường dùng được ghi trong danh mục: "+", ".join(row.get("routes",[]))+"."
            return answer
        profile=self.profiles.get(ids[0]) if len(ids)==1 else None
        if profile and profile["ingredient"]=="Trastuzumab":
            relevant=[t for t in topics if t in ("breast","gastric")]
            if len(relevant)==1 and len(topics)==1:
                topic=relevant[0];disease=TOPICS[topic][0].lower();rate=60 if topic=="breast" else 50
                answer["status"]="conditional_coverage"
                answer["conclusion"]=f"Có quy định BHYT thanh toán Trastuzumab trong {disease}, kèm điều kiện trong ghi chú danh mục."
                answer["conditions"]=["HER2 dương tính."]
                if topic=="gastric":answer["conditions"].append("Ung thư dạ dày tiến xa hoặc di căn.")
                answer["conditions"].append(f"Tỷ lệ ghi trong nhánh nguồn: {rate}%; áp dụng khi đáp ứng các điều kiện của nguồn.")
                answer["conditions"].append("Phạm vi cơ sở và các quy định thanh toán chung phải đọc cùng TT37/2024 và hướng dẫn liên quan; không dùng riêng cột hạng bệnh viện cũ.")
                answer["source_rate"]={"percentage":rate,"source_id":ids[0],"conditional":True}
                if explicit_negative(context,"her2"):
                    answer["status"]="source_condition_not_met"
                    answer["conclusion"]="Câu hỏi nêu HER2 âm tính/không dương tính, trong khi nhánh thanh toán cho "+disease+" ở nguồn này yêu cầu HER2 dương tính. Vì vậy không khớp điều kiện của nhánh này; chưa có căn cứ xác nhận chi trả cho tình huống được hỏi."
                    answer["source_rate"]=None
            elif topics and not relevant:
                answer["conclusion"]="Chưa có căn cứ xác nhận BHYT chi trả Trastuzumab cho chỉ định được hỏi trong ghi chú hiện có. Ghi chú nêu các nhánh ung thư vú và ung thư dạ dày, có điều kiện riêng. Không suy ra việc chi trả cho một bệnh khác từ các nhánh này."
            else:
                answer["status"]="source_conditions"
                answer["conclusion"]="Trastuzumab có quy định thanh toán theo từng chỉ định: ung thư vú HER2 dương tính (60%); ung thư dạ dày tiến xa hoặc di căn, HER2 dương tính (50%). Đây là các tỷ lệ có điều kiện ghi trong nguồn, không phải xác nhận chi trả cho mọi bệnh ung thư."
        elif profile and profile["ingredient"] in ("Erlotinib","Gefitinib"):
            if topics==["nsclc"]:
                answer["status"]="conditional_coverage"
                answer["conclusion"]=f"Có quy định BHYT thanh toán {name} trong ung thư phổi không phải tế bào nhỏ có EGFR dương tính, với tỷ lệ 50% ghi trong nguồn."
                answer["conditions"]=["Đúng thể ung thư phổi không phải tế bào nhỏ; EGFR dương tính.","Đọc cùng các quy định thanh toán chung và điều kiện chuyển tiếp nếu có."]
                answer["source_rate"]={"percentage":50,"source_id":ids[0],"conditional":True}
                if explicit_negative(context,"egfr"):
                    answer["status"]="source_condition_not_met";answer["source_rate"]=None
                    answer["conclusion"]=f"Nhánh thanh toán {name} trong nguồn yêu cầu EGFR dương tính. Câu hỏi nêu EGFR âm tính/không dương tính nên không khớp điều kiện của nhánh này; chưa có căn cứ xác nhận chi trả cho tình huống được hỏi."
            elif topics==["lung"] or not has_disease:
                answer["status"]="source_conditions"
                answer["conclusion"]="Ghi chú thanh toán "+name+" nêu ung thư phổi không phải tế bào nhỏ có EGFR dương tính, tỷ lệ 50%. Quy định này có giới hạn về thể bệnh và EGFR; không áp dụng chung cho mọi ung thư phổi."
            else:
                answer["conclusion"]="Chưa có căn cứ xác nhận chi trả "+name+" cho chỉ định được hỏi trong ghi chú hiện có. Nhánh được ghi nhận là ung thư phổi không phải tế bào nhỏ có EGFR dương tính (50%)."
        elif profile and profile["ingredient"] in ("Doxorubicin","Paclitaxel"):
            answer["status"]="source_conditions"
            answer["conclusion"]=name+" có trong danh mục BHYT; ghi chú phân biệt tỷ lệ theo dạng bào chế. Ghi chú này chưa đủ để xác nhận chi trả cho một bệnh/chỉ định cụ thể."
            answer["conditions"]=list(row.get("conditions",[]))
        elif row.get("conditions"):
            answer["status"]="source_conditions"
            answer["conclusion"]=name+" có trong danh mục BHYT và có điều kiện thanh toán riêng dưới đây. Bộ nguồn hiện chưa có đối chiếu đủ để xác nhận riêng cho bệnh/chỉ định trong câu hỏi." if has_disease else name+" có trong danh mục BHYT, kèm các điều kiện thanh toán ghi trong nguồn dưới đây."
            answer["conditions"]=list(row["conditions"])
        else:
            answer["conclusion"]=name+" có trong danh mục BHYT. Ô ghi chú không nêu điều kiện riêng, nhưng bộ nguồn hiện chưa đủ căn cứ xác nhận chi trả cho bệnh/chỉ định trong câu hỏi." if has_disease else name+" có trong danh mục BHYT. Ô ghi chú không nêu điều kiện riêng; thông tin này chưa đủ để xác nhận chi trả cho mọi chỉ định."
            answer["conditions"]=["Không suy ra mức thanh toán 100% từ ô ghi chú trống.","Cần căn cứ về chỉ định trong nhãn/hướng dẫn điều trị/Dược thư và quy định thanh toán chung."]
        if len(row.get("routes",[]))>1:
            answer["conditions"].append("Danh mục có các đường dùng: "+" / ".join(row["routes"])+". Thông tin trên giữ phạm vi của từng dòng nguồn.")
        if re.search(r"\b(?:2014|2015|truoc nam|chuyen tiep)\b",normalize(context)) and any(id in self.c.transition_rules["mapping"] for id in ids):
            answer["status"]="transition_requires_review";answer["source_rate"]=None
            answer["conclusion"]="Câu hỏi liên quan điều kiện chuyển tiếp. Bộ nguồn có Điều 8 TT20/2022 để đối chiếu, nhưng chưa đủ tỷ lệ lịch sử và chuỗi căn cứ để kết luận riêng trường hợp này. Không áp tỷ lệ của nhánh hiện tại cho thời kỳ khác."
        return answer
