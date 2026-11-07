"""General drug + indication chat. No patient form and no individual entitlement decision.

Drug-specific branches (indication, rate, required marker) live in
data/indication_rules.json and are validated against the verbatim source note.
"""
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

DISEASE_SIGNAL = r"\b(?:ung thu|benh|dai thao duong|tang huyet ap|viem|nhiem khuan|suy tim|hen|copd|dieu tri)\b"
CONTEXT_DISEASE = r"\b(?:ung thu|benh|dai thao duong|tang huyet ap|dau|sot|viem|nhiem khuan|suy tim|hen|copd)\b"
SCOPE_NOTE = ("Thông tin chung theo bộ nguồn BHYT chốt 06/11/2026; chưa được bệnh viện thẩm định. "
              "Tỷ lệ của thuốc không đồng nghĩa mức hưởng cá nhân hoặc số tiền quỹ chi trả.")


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


def marker_mentioned(text, marker):
    from engine import normalize
    return bool(re.search(r"\b"+marker+r"\b",normalize(text).replace("her 2","her2")))


def _capital(text):
    return text[:1].upper()+text[1:]


class IndicationChat:
    def __init__(self,corpus):
        from indication_rules import load_indication_rules
        self.c=corpus
        self.profiles=json.loads((corpus.data/"case_profiles.json").read_text(encoding="utf-8"))["profiles"]
        for id,p in self.profiles.items():
            row=corpus.by_id.get(id)
            if not row or row["ingredient"]!=p["ingredient"] or hashlib.sha256(row.get("conditions_verbatim","").encode()).hexdigest()!=p["note_sha256"]:
                raise ValueError("Stale source-linked chat profile: "+id)
        self.rules_meta,self.rules=load_indication_rules(corpus.data,corpus.by_id,TOPICS)

    def enrich(self,result,message,previous=None):
        from engine import normalize
        result["response_type"]="general_indication_chat"
        result["requires_patient_details"]=False
        result["payment_eligibility"]=None
        result["suggested_followups"]=[]
        if not result.get("results"):return result
        previous=previous or {};current_topics=topics_in(message)
        previous_ids=previous.get("selected_ids",[])
        now_ids=result.get("state",{}).get("selected_ids",[])
        same=bool(set(previous_ids)&set(now_ids))
        prior=previous.get("context","") if same else ""
        # Explicitly named medicine or disease starts a new general question.
        # Unknown diseases must not silently inherit a previous, covered cancer.
        disease_signal=bool(re.search(DISEASE_SIGNAL,normalize(message)))
        reset_topic=bool(current_topics or self.c.resolve(message) or disease_signal)
        context=message if reset_topic or not prior else (prior+"; "+message)[-1000:]
        topics=current_topics if reset_topic else topics_in(prior)
        has_disease=bool(topics or re.search(CONTEXT_DISEASE,normalize(context)))
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
        suggested=[r["question_answer"].pop("_suggested",[]) for r in result["results"]]
        # Suggested next questions are optional chips, never a required form.
        if len(result["results"])==1:
            result["suggested_followups"]=list(dict.fromkeys(suggested[0]))[:3]
        result["answer"]="\n\n".join(r["ingredient"]+": "+r["question_answer"]["conclusion"] for r in result["results"])
        result["answer_status"]="conditional_coverage" if all(r["question_answer"]["status"]=="conditional_coverage" for r in result["results"]) else "source_answer"
        result["state"]["context"]=context[-1000:]
        return result

    def answer(self,row,topics,context,has_disease):
        from engine import normalize
        name=row["ingredient"];ids=row.get("record_ids",[])
        answer={"status":"insufficient_evidence","conclusion":"","conditions":[],"source_rate":None,
            "indications":[TOPICS[t][0] for t in topics],"scope":SCOPE_NOTE,"_suggested":[]}
        if row.get("status")=="route_unmatched":
            answer["conclusion"]="Chưa có căn cứ cho đường dùng nêu trong câu hỏi. Các đường dùng được ghi trong danh mục: "+", ".join(row.get("routes",[]))+"."
            return answer
        rule=self.rules.get(ids[0]) if len(ids)==1 else None
        if rule:
            answer["rule_review"]=rule.get("reviewed_by") or self.rules_meta["review_status"]
        if rule and rule["kind"]=="indication_branches":
            self.branch_answer(answer,rule,name,ids[0],topics,context,has_disease)
        elif rule and rule["kind"]=="formulation_note":
            answer["status"]="source_conditions"
            answer["conclusion"]=name+" có trong danh mục BHYT; ghi chú phân biệt tỷ lệ theo dạng bào chế. Ghi chú này chưa đủ để xác nhận chi trả cho một bệnh/chỉ định cụ thể."
            answer["conditions"]=list(row.get("conditions",[]))
        elif row.get("conditions"):
            answer["status"]="source_conditions"
            answer["conclusion"]=(name+" có trong danh mục BHYT và có điều kiện thanh toán riêng dưới đây. Bộ nguồn hiện chưa có đối chiếu đủ để xác nhận riêng cho bệnh/chỉ định trong câu hỏi." if has_disease
                else name+" có trong danh mục BHYT, kèm các điều kiện thanh toán ghi trong nguồn dưới đây.")
            answer["conditions"]=list(row["conditions"])
        else:
            answer["conclusion"]=(name+" có trong danh mục BHYT. Ô ghi chú không nêu điều kiện riêng, nhưng bộ nguồn hiện chưa đủ căn cứ xác nhận chi trả cho bệnh/chỉ định trong câu hỏi." if has_disease
                else name+" có trong danh mục BHYT. Ô ghi chú không nêu điều kiện riêng; thông tin này chưa đủ để xác nhận chi trả cho mọi chỉ định.")
            answer["conditions"]=["Không suy ra mức thanh toán 100% từ ô ghi chú trống.","Cần căn cứ về chỉ định trong nhãn/hướng dẫn điều trị/Dược thư và quy định thanh toán chung."]
        if len(row.get("routes",[]))>1:
            answer["conditions"].append("Danh mục có các đường dùng: "+" / ".join(row["routes"])+". Thông tin trên giữ phạm vi của từng dòng nguồn.")
        if re.search(r"\b(?:2014|2015|truoc nam|chuyen tiep)\b",normalize(context)) and any(id in self.c.transition_rules["mapping"] for id in ids):
            answer["status"]="transition_requires_review";answer["source_rate"]=None;answer["_suggested"]=[]
            answer.pop("matched_branch",None)
            answer["conclusion"]="Câu hỏi liên quan điều kiện chuyển tiếp. Bộ nguồn có Điều 8 TT20/2022 để đối chiếu, nhưng chưa đủ tỷ lệ lịch sử và chuỗi căn cứ để kết luận riêng trường hợp này. Không áp tỷ lệ của nhánh hiện tại cho thời kỳ khác."
        return answer

    def branch_answer(self,answer,rule,name,source_id,topics,context,has_disease):
        branches=rule["branches"];known={b["topic"] for b in branches}
        listing="; ".join(f"{b['scope']} ({b['rate']}%)" for b in branches)
        relevant=[t for t in topics if t in known]
        parents=[t for t in topics if t in rule.get("parent_topics",{})]
        if len(topics)==1 and relevant:
            b=next(x for x in branches if x["topic"]==relevant[0])
            answer["status"]="conditional_coverage"
            answer["conclusion"]=f"Có quy định BHYT thanh toán {name} trong {b['scope']}, với tỷ lệ {b['rate']}% ghi trong nguồn; áp dụng khi đáp ứng đủ điều kiện dưới đây."
            answer["conditions"]=(list(b["conditions"])
                +[f"Tỷ lệ ghi trong nhánh nguồn: {b['rate']}%; áp dụng khi đáp ứng các điều kiện của nguồn."]
                +list(rule.get("common_conditions",[])))
            answer["source_rate"]={"percentage":b["rate"],"source_id":source_id,"conditional":True}
            answer["matched_branch"]=b["topic"]
            for req in b.get("requirements",[]):
                if explicit_negative(context,req["marker"]):
                    answer["status"]="source_condition_not_met";answer["source_rate"]=None
                    answer["conclusion"]=(f"Nhánh thanh toán {name} cho {b['disease']} trong nguồn yêu cầu {req['label']} dương tính. "
                        f"Câu hỏi nêu {req['label']} âm tính/không dương tính nên không khớp điều kiện của nhánh này; chưa có căn cứ xác nhận chi trả cho tình huống được hỏi.")
                    break
                if not marker_mentioned(context,req["marker"]):
                    answer["_suggested"].append(f"Nếu {req['label']} âm tính thì sao?")
            answer["_suggested"]+=["Còn "+x["disease"]+" thì sao?" for x in branches if x is not b]
        elif (topics and not relevant and not parents) or (not topics and has_disease):
            answer["conclusion"]=(f"Chưa có căn cứ xác nhận BHYT chi trả {name} cho chỉ định được hỏi trong ghi chú hiện có. "
                f"Ghi chú chỉ nêu: {listing}. Không suy ra việc chi trả cho một bệnh khác từ các nhánh này.")
            answer["_suggested"]=[f"{name} điều trị {x['disease']} thì sao?" for x in branches]
        else:
            answer["status"]="source_conditions"
            answer["conclusion"]=f"{name} có quy định thanh toán theo từng chỉ định: {listing}. Đây là các tỷ lệ có điều kiện ghi trong nguồn, không phải xác nhận chi trả cho mọi bệnh/chỉ định."
            for t in parents:answer["conclusion"]+=" "+rule["parent_topics"][t]
            answer["conditions"]=[f"{_capital(b['scope'])}: tỷ lệ {b['rate']}% ghi trong nguồn." for b in branches]+list(rule.get("common_conditions",[]))
            answer["_suggested"]=[f"{name} điều trị {x['disease']} thì sao?" for x in branches]
