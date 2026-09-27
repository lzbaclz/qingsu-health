from __future__ import annotations

from collections import defaultdict
from itertools import product
import re

from sqlmodel import Session, select

from ..facts.store import as_expr_map, current_facts, has_direct_answer
from ..models import Entry, FactStatus, SymptomEvent
from ..protocol.expr import evaluate
from ..protocol.triage import evaluate_rule
from ..protocol.schema import Protocol
from ..util import iso

SUBJECT_LABEL = {"patient": "患者本人", "other": "他人情况", "unclear": "主体待核实"}
TIME_LABEL = {"new": "本次新发", "ongoing": "既有症状仍存在", "historical": "历史提及，当前情况待核实", "worsening": "本次加重",
              "improving": "本次减轻", "past": "历史补充（现已结束）", "unknown": "起始时间待核实"}
STATE_LABEL = {"extracted": "从原话整理，未单独核实", "patient_confirmed": "患者已核实表达",
               "doctor_confirmed": "医生已复核", "review_required": "仍需医护核实"}
OPTIONS = [
    {"value": "new", "label": "是我这次新出现的"},
    {"value": "ongoing", "label": "我以前就有，最近没有新变化"},
    {"value": "worsening", "label": "我以前就有，这次更明显了"},
    {"value": "improving", "label": "我以前就有，这次减轻了"},
    {"value": "past", "label": "我以前有，现在没有了"},
    {"value": "other", "label": "说的是别人，不是我"},
    {"value": "incorrect", "label": "这条整理不是我想表达的"},
    {"value": "unsure", "label": "说不清，请医护再核实"},
]
TIME_CUE = re.compile(r"去年|前年|以前|之前|过去|从前|多年|老毛病|今天|昨天|前天|刚刚|这次|最近|这[两几]天|(?:\d+|[一二两三四五六七八九十半]+)(?:年|个月|周|天)")
OTHER = re.compile(r"^(?:我(?:说|提到|告诉医生))?(?:我(?:的)?(?:妈(?:妈)?|爸(?:爸)?|母亲|父亲|妻子|丈夫|老公|老婆|姐姐|哥哥|朋友)|患者的(?:家人|母亲|父亲)|家人|朋友|邻居|同事|别人)")


def infer_context(text: str, quote: str, candidate=None, respondent: str = "self") -> dict:
    """词表模式的保守上下文基线；真实模型字段只有在引文约束满足时才采用。"""
    start = text.find(quote)
    if start < 0:
        raise ValueError("事件引文不在原文")
    left = max([text.rfind(s, 0, start) for s in "。；;！？!?\n"] + [-1]) + 1
    after = start + len(quote)
    right = min([i for sep in "。；;！？!?\n" if (i := text.find(sep, after)) >= 0] or [len(text)])
    context = text[left:right].strip()
    supplied = getattr(candidate, "context_quote", "") or ""
    issues = []
    if supplied:
        if supplied in text and context in supplied:
            context = supplied
        elif supplied in text and quote in supplied:
            issues.append("模型上下文过窄，保留原句主体与时间关系")
        else:
            issues.append("模型上下文引文不合法，已退回原文窗口")
    subject = "patient" if respondent == "self" else "unclear"
    reported_patient = bool(re.search(r"(?:说|觉得|发现|看到|看见|告诉医生)[，,]?我(?!的?(?:妈|爸|母亲|父亲|朋友|家人))", context))
    other_cue = bool(OTHER.search(context)) and not reported_patient
    if other_cue and re.search(r"(?:但是|但我|而我|不过我)", context):
        other_cue = False
        subject = "unclear"
    if other_cue:
        subject = "other"
    elif re.match(r"[他她](?!说我)", context):
        subject = "unclear"
    model_subject = getattr(candidate, "subject", None)
    if model_subject in SUBJECT_LABEL and supplied and supplied in text:
        if model_subject == "other" and not other_cue:
            issues.append("他人主体缺少明确原文支持，需核实")
            subject = "unclear"
        elif model_subject == "patient" and other_cue:
            issues.append("模型主体与明确的家属表述不一致")
            subject = "other"
        else:
            subject = model_subject
    relation = "unknown"
    if respondent != "self" and subject == "patient" and not re.search(r"患者|本人|他|她|说我|觉得我", context):
        subject = "unclear"
        issues.append("代填语句中的主体需由本人核实")
    if re.search(r"(?:以前|去年|之前|过去).*?(?:现在|目前|早就).{0,5}(?:没有|不麻|不痛|好了|没事)", context):
        relation = "past"
    elif re.search(r"更(?:麻|痛|疼|明显|严重)|加重|越来越", context):
        relation = "worsening"
    elif re.search(r"减轻|轻了|好一些|好点|缓解", context):
        relation = "improving"
    elif re.search(r"(?:今天|这次|最近|刚刚|这[两几]天).{0,8}(?:才|开始|新出现)|突然|刚开始", context) and not re.search(r"才(?:想起|提起|提到|说起|告诉|记起)", context):
        relation = "new"
    elif re.search(r"一直.*(?:麻|痛|疼)|(?:去年|以前|之前|多年|老毛病).*(?:现在还|仍然|一直|没变化|没变|依然)", context):
        relation = "ongoing"
    elif re.search(r"去年|前年|以前|之前|多年|老毛病", context):
        relation = "historical"
    first_time = TIME_CUE.search(context)
    if relation in {"historical", "ongoing", "past"}:
        first_time = re.search(r"去年|前年|以前|之前|多年|老毛病", context) or first_time
    time_text = first_time.group(0) if first_time else ""
    model_time = getattr(candidate, "time_relation", None)
    model_time_text = getattr(candidate, "time_text", "") or ""
    source = "context_baseline"
    if model_time in TIME_LABEL and supplied and supplied in text:
        if model_time_text and model_time_text not in supplied:
            issues.append("模型时间线索不在上下文，未采用")
        elif model_time == "new" and re.search(r"才(?:想起|提起|提到|说起|告诉|记起)", supplied):
            issues.append("报告时间不能作为新发依据")
        elif model_time == "past" and not re.search(r"(?:现在|目前|后来|早就|已经).{0,8}(?:没有|不麻|不痛|好了|没事|消失)", supplied):
            issues.append("过去起病不代表已经结束，未按历史结束排除当前症状")
        elif model_time != "unknown" and not (model_time_text or TIME_CUE.search(supplied)):
            issues.append("模型起病判断没有时间线索，保留未知")
        elif relation != "unknown" and model_time != relation:
            issues.append("模型时间与原句明确线索不同，保留线索供核实")
        else:
            relation, source = model_time, "model_context"
            time_text = model_time_text or time_text
    # 条件作用范围只取症状所在分句的前文，避免把后一句独立的现实症状一并忽略。
    clause_left = max([text.rfind(s, left, start) for s in "，,"] + [left - 1]) + 1
    prefix = text[clause_left:start + len(quote)]
    hypothetical = bool(re.search(r"如果|假如|万一|倘若|要是", prefix))
    return {"quote": context, "subject": subject, "assertion_type": "hypothetical" if hypothetical else "asserted", "time_relation": relation, "time_text": time_text,
            "inference_source": source, "inference_issues": issues}


def record_candidate(session: Session, enc, protocol: Protocol, entry: Entry, cand, value) -> tuple[SymptomEvent | None, bool]:
    spec = protocol.event_verification
    if not spec.enabled or cand.key not in spec.fact_keys:
        return None, True
    info = infer_context(entry.payload["text"], cand.quote, cand, enc.respondent)
    existing = session.exec(select(SymptomEvent).where(SymptomEvent.entry_id == entry.id)).all()
    candidate_value = {"status": cand.status, "value": value, "quote": cand.quote}
    event = next((e for e in existing if all(getattr(e, k) == info[k] for k in ("quote", "subject", "assertion_type", "time_relation", "time_text"))
                  and (cand.key not in e.candidates or e.candidates[cand.key] == candidate_value)), None)
    if event is None:
        event = SymptomEvent(encounter_id=enc.id, entry_id=entry.id, reported_at=entry.created_at, **info)
    event.fact_keys = list(dict.fromkeys([*event.fact_keys, cand.key]))
    event.candidates = {**event.candidates, cand.key: candidate_value}
    session.add(event); session.commit(); session.refresh(event)
    # 明确他人事件进入事件记录，不污染本人事实。明确过去已结束的症状仍待直接问当前情况。
    apply = info["assertion_type"] != "hypothetical" and info["subject"] != "other" and not (info["time_relation"] == "past" and cand.key not in spec.lifetime_fact_keys)
    return event, apply


def events_for(session: Session, encounter_id: str) -> list[SymptomEvent]:
    return list(session.exec(select(SymptomEvent).where(SymptomEvent.encounter_id == encounter_id)
                             .order_by(SymptomEvent.reported_at, SymptomEvent.id)).all())


def interpreted_values(event: SymptomEvent, protocol: Protocol, subject: str, relation: str) -> dict:
    values = {}
    for key, c in event.candidates.items():
        if subject == "other":
            values[key] = (FactStatus.NOT_ASKED, None)
        elif relation == "past" and key not in protocol.event_verification.lifetime_fact_keys:
            values[key] = (FactStatus.DENIED, None)
        elif relation == "ongoing" and key in protocol.event_verification.new_change_fact_keys:
            values[key] = (FactStatus.DENIED, None)
        elif subject == "unclear" or (relation == "historical" and key not in protocol.event_verification.lifetime_fact_keys) or (relation == "unknown" and key in protocol.event_verification.new_change_fact_keys):
            values[key] = (FactStatus.UNCERTAIN, None)
        else:
            values[key] = (c["status"], c.get("value"))
    return values


def action_set(protocol: Protocol, base: dict, event: SymptomEvent, subject: str, relation: str,
               fixed_keys: set[str] | None = None) -> list[dict]:
    """用实际协议表达式计算每一候选分支，不用模型自评分代替规则执行。"""
    if event.assertion_type == "hypothetical":
        return []
    overrides = {k: v for k, v in interpreted_values(event, protocol, subject, relation).items() if k not in (fixed_keys or set())}
    values = {**base, **overrides}
    actions = []
    for rule in protocol.red_flags:
        triggered, provisional = evaluate_rule(rule, values)
        if triggered:
            route = protocol.course.task_routing.get(rule.severity)
            actions.append({"id": rule.id, "label": rule.label, "severity": rule.severity,
                            "role": route.assignee_role if route else "doctor", "stop": rule.on_trigger == "stop_questioning",
                            "provisional": provisional})
    if subject == "patient":
        for rule in protocol.event_verification.review_rules:
            relevant = set(event.fact_keys) & set(rule.fact_keys)
            if relation in rule.changes and any(values.get(k, (None, None))[0] in {"present", "uncertain", "conflicting"} for k in relevant):
                actions.append({"id": "event:" + rule.id, "label": rule.label, "severity": rule.severity,
                                "role": rule.assignee_role, "stop": False})
    return sorted(actions, key=lambda a: a["id"])


def decision_trace(session: Session, enc, protocol: Protocol, event: SymptomEvent) -> dict:
    current = current_facts(session, enc.id)
    facts = as_expr_map(current)
    fixed = {k for k, f in current.items() if has_direct_answer(f)}
    subjects = ["patient", "other"] if event.subject == "unclear" else [event.subject]
    times = ["new", "ongoing", "past", "worsening"] if event.time_relation in {"unknown", "historical"} else [event.time_relation]
    variants = [{"subject": sub, "time_relation": rel, "actions": action_set(protocol, facts, event, sub, rel, fixed)}
                for sub, rel in product(subjects, times)]
    signatures = {tuple((a["id"], a["severity"], a["role"], a["stop"]) for a in v["actions"]) for v in variants}
    priority = min([{"urgent": 0, "same_day": 1, "routine": 2}.get(a["severity"], 3)
                    for v in variants for a in v["actions"]] or [3])
    uncertain = event.subject == "unclear" or event.time_relation in {"unknown", "historical"} or bool(event.inference_issues)
    positive = any(c["status"] in {"present", "uncertain"} for c in event.candidates.values())
    relevant = uncertain and positive and event.verification_state == "extracted" and event.assertion_type != "hypothetical"
    ask = relevant and (protocol.event_verification.strategy == "all" or len(signatures) > 1)
    return {"variants": variants, "distinct_action_sets": len(signatures), "priority": priority,
            "should_ask": ask, "reason": "这是条件句中的假设提及，未作为当前症状" if event.assertion_type == "hypothetical" else "候选解释会改变协议处理路径" if ask else
            ("候选解释对应同一处理；保留未明细节给医护" if uncertain else "原话已有明确主体或时间线索，仍供核对"),
            "protocol_sha256": protocol.content_sha256, "strategy": protocol.event_verification.strategy}


def apply_answer(session: Session, enc, protocol: Protocol, question, value: str, unknown: bool = False,
                  explicit_correction: bool = False) -> tuple[Entry, list[str]]:
    from ..services.encounter import FlowError, add_entry
    from ..facts.store import attach_evidence, reject_extracted_fact, set_fact
    from ..models import EntryKind, FactSource
    from ..tasks.service import audit
    event_id = (question.payload or {}).get("event_id") or question.question_id.split(":", 1)[-1]
    event = session.get(SymptomEvent, event_id)
    if not event or event.encounter_id != enc.id:
        raise FlowError("找不到对应的病程事件")
    choice = "unsure" if unknown else str(value)
    selected = next((o for o in question.options if o["value"] == choice), None)
    if not selected:
        raise FlowError("请选择一项事件核实回答")
    if choice != "unsure":
        event.assertion_type = "asserted"
    entry = add_entry(session, enc, EntryKind.ANSWER,
                      {"kind": "event_context", "question_id": question.question_id, "event_id": event.id,
                       "question_text": question.text, "value": choice, "label": selected["label"], "source_quote": event.quote})
    before = {"subject": event.subject, "time_relation": event.time_relation, "verification_state": event.verification_state}
    if choice == "other":
        event.subject = "other"
    elif choice in TIME_LABEL:
        event.subject, event.time_relation = "patient", choice
    else:
        event.subject = "unclear" if choice == "incorrect" else event.subject
        event.time_relation = "unknown"
    event.verification_state = "review_required" if choice in {"unsure", "incorrect"} else "patient_confirmed"
    event.confirmed_entry_id = entry.id
    event.history = [*event.history, {"at": iso(entry.created_at), "by": f"patient:{enc.patient_id}", "before": before,
                                     "choice": choice, "label": selected["label"], "entry_id": entry.id}]
    session.add(event)
    question.answer_entry_id, question.answer_status = entry.id, "unknown" if choice == "unsure" else "answered"
    session.add(question); session.commit()
    rejected = []
    source_entry = session.get(Entry, event.entry_id)
    values = interpreted_values(event, protocol, event.subject, event.time_relation)
    for key, (status, val) in values.items():
        current = current_facts(session, enc.id)[key]
        # 原事件回答不能覆盖后来在另一段原话中报告的同类症状。
        other_entries = [session.get(Entry, ev.get("entry_id")) for ev in current.evidence if ev.get("entry_id")]
        newer = any(e and e.kind == "free_text" and e.seq > source_entry.seq for e in other_entries)
        if newer:
            event.verification_state = "review_required"
            session.add(event); session.commit()
            continue
        evidence = {"entry_id": entry.id, "kind": "context_answer" if choice in {"other", "incorrect"} else "answer",
                    "quote": f"患者核实事件「{event.quote}」：{selected['label']}"}
        if choice == "unsure":
            continue  # 不知道时间或主体，不等于改变症状值或已经直接确认它
        if choice in {"other", "incorrect"}:
            if any(ev.get("entry_id") == event.entry_id for ev in current.evidence) and not has_direct_answer(current):
                reject_extracted_fact(session, enc, key, evidence)
                rejected.append(key)
        elif (status, val) == (current.status, current.value):
            attach_evidence(session, enc, key, evidence, source=FactSource.ANSWER)
        else:
            # 已有独立直接回答时保留冲突；仅对当前这段抽取作明确纠正。
            set_fact(session, enc, protocol, key, status=status, value=val, evidence=[evidence],
                     source=FactSource.ANSWER, is_correction=explicit_correction or not has_direct_answer(current))
            if status == FactStatus.DENIED:
                rejected.append(key)
    create_event_review_tasks(session, enc, protocol, event)
    audit(session, f"patient:{enc.patient_id}", "event.context_confirmed", "symptom_event", event.id,
          {"entry_id": entry.id, "choice": choice})
    return entry, rejected


def patient_correct_event(session: Session, enc, protocol: Protocol, event_id: str, choice: str):
    from ..services import encounter as svc
    from ..questioning.engine import register_asked
    svc._assert_editable(enc)
    event = session.get(SymptomEvent, event_id)
    if not event or event.encounter_id != enc.id:
        raise svc.FlowError("病程事件不存在")
    if choice not in {o["value"] for o in OPTIONS}:
        raise svc.FlowError("事件修改选项无效")
    payload = {"question_id": f"context:{event.id}:correction:{len(event.history) + 1}", "event_id": event.id,
               "fact_key": event.fact_keys[0], "fact_keys": event.fact_keys, "kind": "event_context", "tier": 1,
               "type": "single_choice", "text": "患者修改这段话的主体或时间：" + event.quote, "options": OPTIONS}
    q = register_asked(session, enc, payload)
    entry, rejected = apply_answer(session, enc, protocol, q, choice, explicit_correction=True)
    svc._dispute_alerts_after_rejection(session, enc, protocol, rejected, entry)
    svc.evaluate_red_flags(session, enc, protocol)
    return svc.confirmation_view(session, enc)


def patient_event_dict(event: SymptomEvent) -> dict:
    return {"id": event.id, "entry_id": event.entry_id, "fact_keys": event.fact_keys, "quote": event.quote, "subject": event.subject,
            "subject_label": SUBJECT_LABEL[event.subject], "assertion_type": event.assertion_type, "time_relation": event.time_relation,
            "time_label": TIME_LABEL[event.time_relation], "time_text": event.time_text,
            "reported_at": iso(event.reported_at), "verification_label": STATE_LABEL[event.verification_state]}


def doctor_review(session: Session, enc, protocol: Protocol, event_id: str, *, subject: str, time_relation: str,
                  note: str, actor: str) -> dict:
    from ..services.encounter import FlowError
    from ..models import Task, TaskStatus
    from ..tasks.service import audit, transition_task
    event = session.get(SymptomEvent, event_id)
    if not event or event.encounter_id != enc.id:
        raise FlowError("病程事件不存在")
    if subject not in SUBJECT_LABEL or time_relation not in TIME_LABEL or not note.strip():
        raise FlowError("请选择主体和时间关系，并写明核实依据")
    before = {"subject": event.subject, "time_relation": event.time_relation, "verification_state": event.verification_state}
    event.subject, event.time_relation = subject, time_relation
    event.verification_state = "review_required" if subject == "unclear" or (subject != "other" and time_relation in {"unknown", "historical"}) else "doctor_confirmed"
    from ..util import now
    event.history = [*event.history, {"at": iso(now()), "by": actor, "before": before, "subject": subject,
                                     "time_relation": time_relation, "note": note.strip()}]
    session.add(event); session.commit()
    audit(session, actor, "event.doctor_reviewed", "symptom_event", event.id, event.history[-1])
    if event.verification_state == "review_required":
        create_event_review_tasks(session, enc, protocol, event)
    if event.verification_state == "doctor_confirmed":
        for task in session.exec(select(Task).where(Task.encounter_id == enc.id, Task.kind == "event_review")).all():
            if (task.detail or {}).get("event_id") == event.id and task.status != TaskStatus.COMPLETED:
                if task.status == TaskStatus.UNVIEWED:
                    transition_task(session, task, TaskStatus.VIEWED, actor, note)
                transition_task(session, task, TaskStatus.COMPLETED, actor, "事件语义已复核：" + note)
    # 语义复核不自动改病历事实，不取消红旗；需要变更事实时仍走已有的独立修正与处置流程。
    return event_dict(session, enc, protocol, event)


def next_context_question(session: Session, enc, protocol: Protocol, restrict_keys: set[str] | None = None) -> dict | None:
    if not protocol.event_verification.enabled:
        return None
    choices = []
    for event in events_for(session, enc.id):
        if restrict_keys is not None and not set(event.fact_keys) & restrict_keys:
            continue
        trace = decision_trace(session, enc, protocol, event)
        if trace["should_ask"]:
            choices.append((trace["priority"], -trace["distinct_action_sets"], event.reported_at, event.id, event, trace))
    if not choices:
        return None
    *_, event, trace = min(choices, key=lambda x: x[:4])
    return {"question_id": f"context:{event.id}", "event_id": event.id, "fact_key": event.fact_keys[0],
            "fact_keys": event.fact_keys, "text": protocol.event_verification.question.format(quote=event.quote),
            "type": "single_choice", "kind": "event_context", "tier": 1, "allow_unknown": True,
            "allow_skip": False, "options": OPTIONS, "quote": event.quote,
            "reason": "这段话的时间或说话对象会影响后续核实，请按实际情况选择。", "decision_trace": trace}


def event_dict(session: Session, enc, protocol: Protocol, event: SymptomEvent) -> dict:
    return {"id": event.id, "entry_id": event.entry_id, "fact_keys": event.fact_keys,
            "labels": [protocol.fact(k).label for k in event.fact_keys], "quote": event.quote,
            "subject": event.subject, "subject_label": SUBJECT_LABEL[event.subject], "assertion_type": event.assertion_type,
            "time_relation": event.time_relation, "time_label": TIME_LABEL[event.time_relation],
            "time_text": event.time_text, "reported_at": iso(event.reported_at),
            "verification_state": event.verification_state, "verification_label": STATE_LABEL[event.verification_state],
            "inference_source": event.inference_source, "inference_issues": event.inference_issues,
            "history": event.history, "decision_trace": decision_trace(session, enc, protocol, event)}


def create_event_review_tasks(session: Session, enc, protocol: Protocol, event: SymptomEvent):
    from ..course.tasks import create_routed_task
    from ..models import Task, TaskStatus
    if event.verification_state == "doctor_confirmed" or event.assertion_type == "hypothetical":
        return
    pending = session.exec(select(Task).where(Task.encounter_id == enc.id, Task.kind == "event_review",
                                             Task.status != TaskStatus.COMPLETED)).all()
    if any((t.detail or {}).get("event_id") == event.id for t in pending):
        return
    facts = current_facts(session, enc.id)
    for rule in protocol.event_verification.review_rules:
        relevant = set(event.fact_keys) & set(rule.fact_keys)
        if event.subject == "patient" and event.time_relation in rule.changes and any(facts[k].status in {"present", "uncertain", "conflicting"} for k in relevant):
            create_routed_task(session, protocol, enc.id, "event_review", rule.label, severity=rule.severity,
                               assignee_role=rule.assignee_role,
                               detail={"event_id": event.id, "dedupe_key": f"event:{event.id}:{rule.id}:revision:{len(event.history)}",
                                       "source": "patient_report", "quote": event.quote})
    if event.verification_state == "review_required":
        create_routed_task(session, protocol, enc.id, "event_review", "病程事件的主体或时间仍需核实", severity="routine",
                           assignee_role="doctor", detail={"event_id": event.id, "dedupe_key": f"event:{event.id}:unresolved:{len(event.history)}"})
