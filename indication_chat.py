"""General drug + indication chat. No patient form and no individual entitlement decision.

Drug-specific branches (indication, rate, required marker) live in
data/indication_rules.json and are validated against the verbatim source note.
"""
import hashlib
import json
import re
from condition_reader import choose_formulation, requirement_status

TOPICS = {
    "breast":("Ung thư vú",r"(?:ung thu|ut) vu"),
    "gastric":("Ung thư dạ dày",r"(?:ung thu|ut) da day"),
    "nsclc":("Ung thư phổi không phải tế bào nhỏ",r"(?:ung thu|ut) phoi (?:the )?khong (?:phai )?te bao nho|nsclc"),
    "sclc":("Ung thư phổi tế bào nhỏ",r"(?:ung thu|ut) phoi (?:the )?te bao nho|sclc"),
    "lung":("Ung thư phổi (chưa nêu thể)",r"(?:ung thu|ut) phoi"),
    "colorectal":("Ung thư đại trực tràng",r"(?:ung thu|ut) (?:dai truc trang|dai trang|truc trang)"),
    "liver":("Ung thư gan",r"(?:ung thu|ut) (?:(?:te bao|bieu mo) )*gan|hcc"),
    "t2d":("Đái tháo đường típ 2",r"(?:dai thao duong|tieu duong) (?:tip|type|typ|loai) 2"),
    # Oncology prototype topics (khoa Ung bướu, 07/11/2026).
    # Only the pleural site named in the source note (not peritoneal mesothelioma).
    "mesothelioma":("U trung biểu mô màng phổi",r"(?:u|ung thu) trung bieu mo (?:ac tinh )?(?:mang phoi|phoi)|mesothelioma(?! phuc mac)(?: mang phoi)?"),
    "head_neck":("Ung thư tế bào vảy vùng đầu cổ",r"(?:ung thu|ut) (?:te bao vay )?(?:vung )?dau(?: va)? co|(?:ung thu|ut|carcinom[a]?) (?:te bao vay )?(?:thanh quan|ha hong|hong|khoang mieng|luoi|san mieng|amidan|xoang le|xoang)"),
    "thyroid":("Ung thư tuyến giáp",r"(?:ung thu|ut) (?:(?:bieu mo|te bao) )*tuyen giap"),
    "kidney":("Ung thư thận",r"(?:ung thu|ut) (?:(?:te bao|bieu mo) )*than|rcc"),
    "prostate":("Ung thư tiền liệt tuyến",r"(?:ung thu|ut) (?:tien liet tuyen|tuyen tien liet)"),
    "cml":("Bạch cầu tủy mạn (CML)",r"bach cau (?:dong )?tuy man|cml"),
    "cll":("Bạch cầu lympho mạn (CLL)",r"bach cau lympho man|cll"),
    "gist":("U mô đệm đường tiêu hóa (GIST)",r"gist|u mo dem (?:duong )?(?:da day )?(?:ruot|tieu hoa)"),
    "nhl":("U lympho không Hodgkin",r"u lympho(?: ac tinh)? khong (?:phai )?hodgkin|lymphoma khong hodgkin|non hodgkin|nhl|dlbcl|"
           r"u lympho (?:ac tinh )?(?:te bao b lon(?: lan toa)?|the nang|nang|vung ria|te bao ao|te bao nho|lympho bao nho)|follicular lymphoma|marginal zone lymphoma"),
}

# A new disease word resets the topic; "bệnh nhân" and "điều trị" are not diseases.
DISEASE_SIGNAL = r"\b(?:ung thu|benh(?! (?:nhan|da|dang|van|con|khong|chua|tien trien|tai phat|on dinh|di can|giai doan))|dai thao duong|tang huyet ap|viem|nhiem khuan|suy tim|hen|copd|trung bieu mo|sarcom)\b"
CONTEXT_DISEASE = r"\b(?:ung thu|benh(?! nhan)|dai thao duong|tang huyet ap|dau|sot|viem|nhiem khuan|suy tim|hen|copd|trung bieu mo|lympho|bach cau|sarcom)\b"
TOPIC_NEGATION = r"(?:khong phai|khong phai la|khong bi|khong co|khong mac|chua co|chua mac|loai tru)\s*$"
SCOPE_NOTE = ("Thông tin chung theo bộ nguồn BHYT chốt 06/11/2026; chưa được bệnh viện thẩm định. "
              "Tỷ lệ của thuốc không đồng nghĩa mức hưởng cá nhân hoặc số tiền quỹ chi trả.")


def topics_in(text):
    from engine import normalize
    q=normalize(text);hits=[]
    for key,(_,pattern) in TOPICS.items():
        for m in re.finditer(r"\b(?:"+pattern+r")\b",q):
            if re.search(TOPIC_NEGATION,q[max(0,m.start()-24):m.start()]):continue
            # Secondary liver cancer (metastasis to the liver) is not hepatocellular carcinoma.
            if key=="liver" and re.search(r"\bthu phat\b|\bdi can (?:tu|den|vao) |\bdi can gan\b",q):continue
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


def rate_text(branch):
    return "không ghi tỷ lệ" if branch["rate"] is None else f"{branch['rate']}%"


def valid_facts(raw):
    """Confirmed facts from the client state: {record_id: {topic: {marker: value}}}, size-limited."""
    out={}
    if not isinstance(raw,dict):return out
    for rid,topics in list(raw.items())[:20]:
        if not isinstance(rid,str) or not isinstance(topics,dict):continue
        for topic,marks in list(topics.items())[:10]:
            if not isinstance(topic,str) or not isinstance(marks,dict):continue
            for marker,value in list(marks.items())[:12]:
                if isinstance(marker,str) and isinstance(value,str) and len(marker)<=40 and len(value)<=40:
                    out.setdefault(rid,{}).setdefault(topic,{})[marker]=value
    return out


def previous_turns(previous):
    """Earlier question turns of the same conversation (validated, newest last)."""
    turns=previous.get("turns")
    if isinstance(turns,list) and all(isinstance(t,str) and len(t)<=1000 for t in turns):
        return turns[-8:]
    context=previous.get("context","")
    return [t for t in context.split("; ") if t][-8:] if isinstance(context,str) else []


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

    def enrich(self,result,message,previous=None,named_drug=None,carry_prior=False,confirm=None):
        from engine import normalize
        result["response_type"]="general_indication_chat"
        result["requires_patient_details"]=False
        result["payment_eligibility"]=None
        result["suggested_followups"]=[]
        if not result.get("results"):return result
        previous=previous or {}
        previous_ids=previous.get("selected_ids",[])
        now_ids=result.get("state",{}).get("selected_ids",[])
        same=bool(set(previous_ids)&set(now_ids))
        prior=previous_turns(previous) if (same or carry_prior) else []
        # Confirmed facts (buttons) belong to the case under discussion; a new medicine starts a new case.
        facts=valid_facts(previous.get("facts")) if same else {}
        self._new_turn=None
        if confirm:
            # A button click adds a fact; it is not a new question and adds no text turn.
            rid,topic,marker=confirm["key"].split("|");facts.setdefault(rid,{}).setdefault(topic,{})[marker]=confirm["value"]
            turns=prior or [message];topics=topics_in("; ".join(turns))
        else:
            current_topics=topics_in(message)
            # Explicitly named medicine or disease starts a new general question.
            # Unknown diseases must not silently inherit a previous, covered cancer.
            disease_signal=bool(re.search(DISEASE_SIGNAL,normalize(message)))
            if named_drug is None:named_drug=bool(self.c.resolve(message))
            # "Còn gefitinib?" after an NSCLC question keeps the disease for the new medicine.
            reset_topic=bool(current_topics or (named_drug and not carry_prior) or disease_signal)
            turns=[message] if reset_topic or not prior else (prior+[message])[-8:]
            topics=current_topics if reset_topic else topics_in("; ".join(prior))
            self._new_turn=message
        context="; ".join(turns)[-1000:]
        has_disease=bool(topics or re.search(CONTEXT_DISEASE,normalize(context)))
        supplemental=[]
        for row in result["results"]:
            # Every answered medicine gets its own buttons; each key carries that medicine's record id.
            row["question_answer"]=self.answer(row,topics,turns,has_disease,facts,confirmable=True)
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
        result["state"]["turns"]=[t[-1000:] for t in turns]
        result["state"]["facts"]=facts
        return result

    def answer(self,row,topics,turns,has_disease,facts=None,confirmable=True):
        from engine import normalize
        context="; ".join(turns)
        name=row["ingredient"];ids=row.get("record_ids",[])
        facts=facts or {}
        answer={"status":"insufficient_evidence","conclusion":"","conditions":[],"source_rate":None,
            "indications":[TOPICS[t][0] for t in topics],"scope":SCOPE_NOTE,"_suggested":[],"confirm":[]}
        if row.get("status")=="route_unmatched":
            answer["conclusion"]="Chưa có căn cứ cho đường dùng nêu trong câu hỏi. Các đường dùng được ghi trong danh mục: "+", ".join(row.get("routes",[]))+"."
            return answer
        answer["_highlights"]=[]
        rule=self.rules.get(ids[0]) if len(ids)==1 else None
        if rule:
            answer["rule_review"]=rule.get("reviewed_by") or rule.get("review_status") or self.rules_meta["review_status"]
            if not rule.get("reviewed_by"):
                answer["scope"]+=" Nhánh điều kiện của thuốc này là bản nháp tách từ nguyên văn, chưa được Dược/BHYT duyệt."
        if rule and rule["kind"]=="indication_branches":
            self.branch_answer(answer,rule,name,ids[0],topics,turns,has_disease,facts.get(ids[0],{}),confirmable)
        elif rule and rule["kind"]=="formulation_note":
            axis=rule.get("axis","dạng bào chế")
            answer["status"]="source_conditions"
            answer["conclusion"]=name+f" có trong danh mục BHYT; ghi chú phân biệt tỷ lệ theo {axis}. Ghi chú này chưa đủ để xác nhận chi trả cho một bệnh/chỉ định cụ thể."
            fact=facts.get(ids[0],{}).get("formulation",{}).get("value")
            if fact and getattr(self,"_new_turn",None):
                # "Nếu dùng chống thải ghép thì sao?" replaces an earlier confirmed purpose.
                _,new_state=choose_formulation([self._new_turn],rule["formulations"])
                if new_state in ("chosen","unclear"):
                    facts[ids[0]]["formulation"].pop("value",None);fact=None
            chosen,state=choose_formulation(turns,rule["formulations"],fact)
            if chosen:
                f=chosen[0]
                source="Theo xác nhận" if state=="confirmed" else "Câu hỏi thuộc nhánh"
                answer["conclusion"]+=f" {source} “{f['label']}”: tỷ lệ ghi trong nguồn {f['rate']}%."
                answer["matched_branch"]=f["value"]
                answer["_highlights"]+=list(f.get("verbatim",[]))
            elif state=="unclear":
                answer["conclusion"]+=f" Câu hỏi chưa xác định rõ {axis}; chọn {axis} bên dưới để xem đúng nhánh."
            # Buttons when the choice is open, and after a confirmation so it can be changed.
            if confirmable and (not chosen or state=="confirmed"):
                answer["confirm"].append({"key":f"{ids[0]}|formulation|value","label":_capital(axis),"requires":"",
                    "options":[{"value":f["value"],"label":f"{f['label']} ({f['rate']}%)"} for f in rule["formulations"]]})
            answer["conditions"]=list(row.get("conditions",[]))
        elif rule and rule["kind"]=="rate_only":
            facility=" và điều kiện cơ sở" if rule.get("common_verbatim") else ""
            answer["status"]="source_conditions"
            answer["conclusion"]=(f"{name} có trong danh mục BHYT; ghi chú chỉ nêu tỷ lệ thanh toán {rule['rate']}%{facility}, không ghi chỉ định cụ thể. "
                "Bộ nguồn chưa đủ để xác nhận chỉ định nào được chấp nhận; cần đối chiếu nhãn thuốc đã đăng ký và hướng dẫn chẩn đoán, điều trị.")
            answer["conditions"]=[f"Tỷ lệ ghi trong nguồn: {rule['rate']}%."]+list(rule.get("common_conditions",[]))+[
                "Chỉ định được thanh toán cần Dược/BHYT xác định theo nhãn và hướng dẫn điều trị; ghi chú không tự giới hạn bệnh."]
        elif row.get("conditions"):
            answer["status"]="source_conditions"
            answer["conclusion"]=(name+" có trong danh mục BHYT và có điều kiện thanh toán riêng dưới đây. Bộ nguồn hiện chưa có đối chiếu đủ để xác nhận riêng cho bệnh/chỉ định trong câu hỏi." if has_disease
                else name+" có trong danh mục BHYT, kèm các điều kiện thanh toán ghi trong nguồn dưới đây.")
            answer["conditions"]=list(row["conditions"])
        else:
            answer["conclusion"]=(name+" có trong danh mục BHYT. Ô ghi chú không nêu điều kiện riêng, nhưng bộ nguồn hiện chưa đủ căn cứ xác nhận chi trả cho bệnh/chỉ định trong câu hỏi." if has_disease
                else name+" có trong danh mục BHYT. Ô ghi chú không nêu điều kiện riêng; thông tin này chưa đủ để xác nhận chi trả cho mọi chỉ định.")
            answer["conditions"]=["Không suy ra mức thanh toán 100% từ ô ghi chú trống.","Cần căn cứ về chỉ định trong nhãn/hướng dẫn điều trị/Dược thư và quy định thanh toán chung."]
        facility=getattr(self.c,"facility",None)
        if facility and rule and any("hạng" in v for v in rule.get("common_verbatim",[])):
            # The note limits payment to hospital classes; say what is on record for this facility and that it is unverified.
            answer["conditions"].append(f"Cơ sở: {facility['name']} — {facility['class_note']} {facility['verification']}")
        if len(row.get("routes",[]))>1:
            answer["conditions"].append("Danh mục có các đường dùng: "+" / ".join(row["routes"])+". Thông tin trên giữ phạm vi của từng dòng nguồn.")
        if rule and rule["kind"]=="rate_only":
            answer["_highlights"]+=list(rule.get("verbatim",[]))+list(rule.get("common_verbatim",[]))
        # Direct quotation: the stored source note of each row, with the sentences this answer
        # relies on (matched branch / chosen formulation / rate) marked in place.
        answer["quotes"]=self.c.source_quote(ids,answer.pop("_highlights",[]))
        if re.search(r"\b(?:2014|2015|truoc nam|chuyen tiep)\b",normalize(context)) and any(id in self.c.transition_rules["mapping"] for id in ids):
            answer["status"]="transition_requires_review";answer["source_rate"]=None;answer["_suggested"]=[];answer["confirm"]=[]
            answer.pop("matched_branch",None)
            for q in answer.get("quotes",[]):q["highlights"]=[]
            answer["conclusion"]="Câu hỏi liên quan điều kiện chuyển tiếp. Bộ nguồn có Điều 8 TT20/2022 để đối chiếu, nhưng chưa đủ tỷ lệ lịch sử và chuỗi căn cứ để kết luận riêng trường hợp này. Không áp tỷ lệ của nhánh hiện tại cho thời kỳ khác."
        return answer

    def branch_answer(self,answer,rule,name,source_id,topics,turns,has_disease,facts=None,confirmable=True):
        facts=facts or {}
        branches=rule["branches"];known={b["topic"] for b in branches}
        listing="; ".join(f"{b['scope']} ({rate_text(b)})" for b in branches)
        relevant=[t for t in topics if t in known]
        parents=[t for t in topics if t in rule.get("parent_topics",{})]
        if len(topics)==1 and relevant:
            b=next(x for x in branches if x["topic"]==relevant[0])
            answer["status"]="conditional_coverage"
            if b["rate"] is None:
                answer["conclusion"]=f"Có quy định BHYT thanh toán {name} trong {b['scope']}; ghi chú không ghi tỷ lệ thanh toán. Áp dụng khi đáp ứng đủ điều kiện dưới đây."
                rate_line="Ghi chú không ghi tỷ lệ thanh toán; không tự suy ra 100%, cần Dược/BHYT xác định cách áp dụng."
            else:
                answer["conclusion"]=f"Có quy định BHYT thanh toán {name} trong {b['scope']}, với tỷ lệ {b['rate']}% ghi trong nguồn; áp dụng khi đáp ứng đủ điều kiện dưới đây."
                rate_line=f"Tỷ lệ ghi trong nhánh nguồn: {b['rate']}%; áp dụng khi đáp ứng các điều kiện của nguồn."
                answer["source_rate"]={"percentage":b["rate"],"source_id":source_id,"conditional":True}
            answer["conditions"]=list(b["conditions"])+[rate_line]+list(rule.get("common_conditions",[]))
            answer["matched_branch"]=b["topic"]
            answer.setdefault("_highlights",[]).extend(list(b.get("verbatim",[]))+list(rule.get("common_verbatim",[])))
            answer["requirements"]=[]
            unmet=None;branch_facts=facts.get(b["topic"],{})
            for req in b.get("requirements",[]):
                requires=req.get("requires",req["label"]+" dương tính")
                fact=branch_facts.get(req["marker"])
                # A new question that says anything about this condition — a clear restatement
                # ("Nếu RAS tự nhiên thì sao?") or a doubt ("nếu chưa xét nghiệm EGFR", "nếu chưa
                # di căn" for an either/or condition) — replaces the earlier confirmation.
                if fact and getattr(self,"_new_turn",None) and requirement_status([self._new_turn],req) is not None:
                    branch_facts.pop(req["marker"],None);fact=None
                status=requirement_status(turns,req,fact)
                source="Theo xác nhận" if fact in ("met","not_met","unknown") else "Theo câu hỏi"
                answer["requirements"].append({"label":req["label"],"requires":requires,"status":status or "not_stated",
                                               "source":"confirmed" if source=="Theo xác nhận" else "question"})
                if status=="not_met" and unmet is None:
                    unmet=req;unmet_source="Thông tin đã xác nhận" if source=="Theo xác nhận" else "Câu hỏi nêu"
                elif status=="met":
                    answer["conditions"].append(f"{source}: {requires} — khớp.")
                elif status=="unknown":
                    answer["conditions"].append(f"{source}: {req['label']} chưa rõ — cần xác nhận {requires}.")
                if (status in (None,"unknown") or source=="Theo xác nhận") and confirmable:
                    # Unclear conditions get buttons; confirmed ones keep theirs so they can be changed.
                    # Never guess an unclear condition: offer explicit confirmation buttons.
                    options=req.get("options",{})
                    answer["confirm"].append({"key":f"{source_id}|{b['topic']}|{req['marker']}","label":_capital(req["label"]),"requires":requires,
                        "options":[{"value":"met","label":options.get("met",_capital(requires))},
                                   {"value":"not_met","label":options.get("not_met",_capital(req.get("negative_desc","Không đáp ứng")))},
                                   {"value":"unknown","label":"Chưa rõ"}]})
            unclear=[r for r in answer["requirements"] if r["status"]=="unknown"]
            if unclear and not unmet:
                answer["conclusion"]+=" Chưa rõ: "+"; ".join(r["requires"] for r in unclear)+" — cần xác nhận trước khi áp dụng tỷ lệ này."
            if answer["requirements"] and all(r["status"]=="met" for r in answer["requirements"]):
                answer["all_requirements_met"]=True
                answer["conclusion"]+=" Các điều kiện riêng của nhánh này đều khớp theo thông tin đã nêu/xác nhận; đây vẫn là đối chiếu với nguồn, không phải quyết định chi trả."
            if unmet:
                answer["status"]="source_condition_not_met";answer["source_rate"]=None
                answer["conclusion"]=(f"Nhánh thanh toán {name} cho {b['disease']} trong nguồn yêu cầu {unmet.get('requires',unmet['label']+' dương tính')}. "
                    f"{unmet_source} {unmet.get('negative_desc',unmet['label']+' âm tính/không dương tính')} nên không khớp điều kiện của nhánh này; chưa có căn cứ xác nhận chi trả cho tình huống được hỏi.")
            answer["_suggested"]+=["Còn "+x["disease"]+" thì sao?" for x in branches if x is not b]
        elif (topics and not relevant and not parents) or (not topics and has_disease):
            answer["conclusion"]=(f"Chưa có căn cứ xác nhận BHYT chi trả {name} cho chỉ định được hỏi trong ghi chú hiện có. "
                f"Ghi chú chỉ nêu: {listing}. Không suy ra việc chi trả cho một bệnh khác từ các nhánh này.")
            answer["_suggested"]=[f"{name} điều trị {x['disease']} thì sao?" for x in branches]
        else:
            answer["status"]="source_conditions"
            answer["conclusion"]=f"{name} có quy định thanh toán theo từng chỉ định: {listing}. Đây là các tỷ lệ có điều kiện ghi trong nguồn, không phải xác nhận chi trả cho mọi bệnh/chỉ định."
            for t in parents:answer["conclusion"]+=" "+rule["parent_topics"][t]
            answer["conditions"]=[f"{_capital(b['scope'])}: {rate_text(b)}." for b in branches]+list(rule.get("common_conditions",[]))
            answer["_suggested"]=[f"{name} điều trị {x['disease']} thì sao?" for x in branches]
