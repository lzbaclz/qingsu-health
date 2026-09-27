"""就诊流程编排：把身体图、文字、问答、确认、医生核对、随访串成一条可验收的流程。"""
from __future__ import annotations

from typing import Any, Optional

from sqlmodel import Session, select

from ..extraction.service import extract_and_apply
from ..config import settings
from sqlalchemy import func, update, or_
from datetime import timedelta
from sqlalchemy.exc import IntegrityError

from ..facts.store import (attach_evidence, current_facts, display_value, fact_history, fact_to_dict, has_direct_answer, init_facts,
                           mark_asked_unanswered, mark_patient_confirmed, reject_extracted_fact, set_fact)
from ..models import (Alert, AskedQuestion, AuditLog, Encounter, EncounterKind, EncounterStatus, Entry, EntryKind, FactSource, Summary,
                      FactStatus, Notification, Patient, Task, TaskStatus, UsageEvent)
from ..protocol import get_protocol
from ..protocol.loader import for_encounter
from ..protocol.loader import region_index
from ..protocol.expr import evaluate
from ..protocol.schema import Protocol
from ..questioning.engine import (active_stop_alerts, build_clarification, next_question, patient_value_label,
                                  pending_question, register_asked)
from ..summary.brief import TRIAGE, record_draft, triage_disputed_only, triage_label, triage_of, visit_brief
from ..summary.build import build_summary_content, create_summary_version, latest_summary, region_labels
from ..tasks.service import (audit, create_notification, create_task, deliver_queued, notification_to_dict,
                             task_to_dict, transition_task)
from ..util import iso, now
from ..course.hours import describe_windows, in_service_hours, route_of, urgent_view
from ..course.tasks import after_hours_callback, create_routed_task, is_overdue
from ..course.trajectory import evaluate_recovery_rules, trajectory

RESPONDENT_LABEL = {"self": "本人填写", "family": "家属代述（本人在场确认）", "staff": "前台代录"}
from ..verification.checks import latest_report, run_checks
from ..verification.scope import annotate_fact_item
from ..facts.store import as_expr_map


class FlowError(ValueError):
    pass


# ------------------------------------------------------------------ 基础
def get_encounter(session: Session, encounter_id: str) -> Encounter:
    enc = session.get(Encounter, encounter_id)
    if not enc:
        raise FlowError("就诊记录不存在")
    return enc


def _next_seq(session: Session, encounter_id: str) -> int:
    cur = session.exec(select(func.max(Entry.seq)).where(Entry.encounter_id == encounter_id)).one()
    return int(cur or 0) + 1


def add_entry(session: Session, enc: Encounter, kind: str, payload: dict) -> Entry:
    e = Entry(encounter_id=enc.id, seq=_next_seq(session, enc.id), kind=kind, payload=payload)
    session.add(e)
    enc.updated_at = now()
    session.add(enc)
    session.commit()
    session.refresh(e)
    return e


def get_or_create_patient(session: Session, display_code: Optional[str], clinic_id: str = "clinic_demo", *,
                          allow_existing: bool = True) -> Patient:
    if display_code:
        p = session.exec(select(Patient).where(Patient.display_code == display_code, Patient.clinic_id == clinic_id)).first()
        if p:
            if not allow_existing:
                raise FlowError("该编号已有记录，请使用门诊邀请")
            return p
    if not display_code:
        codes = session.exec(select(Patient.display_code).where(Patient.display_code.like("P-%"), Patient.clinic_id == clinic_id)).all()
        nums = [int(c[2:]) for c in codes if c[2:].isdigit()]
        n = (max(nums) if nums else 0) + 1
        while session.exec(select(Patient).where(Patient.display_code == f"P-{n:04d}", Patient.clinic_id == clinic_id)).first():
            n += 1
        display_code = f"P-{n:04d}"
    p = Patient(display_code=display_code, clinic_id=clinic_id)
    session.add(p)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if allow_existing:
            existing = session.exec(select(Patient).where(Patient.display_code == display_code, Patient.clinic_id == clinic_id)).first()
            if existing:
                return existing
        raise FlowError("该编号已被使用，请重试自动编号或使用门诊邀请") from None
    session.refresh(p)
    return p


def create_encounter(session: Session, *, patient_code: Optional[str], protocol_id: str, kind: str = EncounterKind.PRE_VISIT,
                     parent_encounter_id: Optional[str] = None, eligibility: Optional[dict[str, bool]] = None,
                     require_eligibility: bool = False, respondent: str = "self", respondent_relation: Optional[str] = None,
                     proxy_consent: bool = False, clinic_id: str = "clinic_demo", allow_existing_patient: bool = True) -> Encounter:
    """eligibility：开始页的适用范围确认（协议 scope.eligibility）。患者端接口 require_eligibility=True：
    协议定义了适用范围时必须逐条确认，任何一条"不对"都不创建就诊，直接返回协议写好的说明。
    评测与演示数据直接调用本函数时可不传，审计里记为"未记录"。"""
    if kind == EncounterKind.FOLLOW_UP and parent_encounter_id:
        original = get_encounter(session, parent_encounter_id)
        if not original.protocol_sha256:
            raise FlowError("上次记录没有可核验的协议快照，请联系门诊重新采集基线")
        if protocol_id != original.protocol_id:
            raise FlowError("随访必须沿用该疗程的协议")
        protocol = for_encounter(session, original)
    else:
        protocol = get_protocol(protocol_id)
    items = protocol.scope.eligibility
    if items and (eligibility is not None or require_eligibility):
        answers = eligibility or {}
        failed = [it for it in items if answers.get(it.id) is False]
        if failed:
            raise FlowError(failed[0].if_not)
        missing = [it.text for it in items if answers.get(it.id) is not True]
        if missing:
            raise FlowError("请先确认适用范围：" + "；".join(missing))
    patient = get_or_create_patient(session, patient_code, clinic_id=clinic_id, allow_existing=allow_existing_patient)
    if kind == EncounterKind.FOLLOW_UP:
        if not parent_encounter_id:
            raise FlowError("随访必须关联一次已由医生确认的就诊")
        parent = get_encounter(session, parent_encounter_id)
        if parent.status not in (EncounterStatus.DOCTOR_CONFIRMED, EncounterStatus.CLOSED):
            raise FlowError("只有医生已确认的就诊才能进入随访")
        if parent.patient_id != patient.id:
            raise FlowError("随访患者与原就诊不一致")
    if respondent not in ("self", "family", "staff"):
        raise FlowError("填写人只能是：本人 / 家属代述 / 前台代录")
    if respondent != "self" and not proxy_consent:
        raise FlowError("家属或前台代填时，需要患者本人在场并同意")
    from ..models import ProtocolSnapshot
    if not session.get(ProtocolSnapshot, protocol.content_sha256):
        session.add(ProtocolSnapshot(id=protocol.content_sha256, protocol_id=protocol.protocol_id,
                                     version=protocol.version, content=protocol.model_dump(mode="json")))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            if not session.get(ProtocolSnapshot, protocol.content_sha256):
                raise
    enc = Encounter(patient_id=patient.id, clinic_id=patient.clinic_id, protocol_id=protocol.protocol_id,
                    protocol_sha256=protocol.content_sha256,
                    protocol_version=protocol.version, kind=kind, parent_encounter_id=parent_encounter_id,
                    parent_plan_version_id=((parent.followup_plan or {}).get("version_id") if kind == EncounterKind.FOLLOW_UP else None),
                    respondent=respondent, respondent_relation=(respondent_relation or None) if respondent != "self" else None,
                    proxy_consent=proxy_consent if respondent != "self" else False)
    session.add(enc)
    session.commit()
    session.refresh(enc)
    init_facts(session, enc, protocol)
    if items:
        audit(session, "patient" if eligibility is not None else "system", "encounter.eligibility", "encounter", enc.id,
              {"attested": eligibility is not None, "answers": eligibility or {},
               "items": [{"id": it.id, "text": it.text} for it in items]})
    return enc


def eligibility_record(session: Session, enc: Encounter) -> Optional[dict]:
    a = session.exec(select(AuditLog).where(AuditLog.action == "encounter.eligibility", AuditLog.target_id == enc.id)
                     .order_by(AuditLog.created_at.desc())).first()
    return {**a.detail, "at": iso(a.created_at)} if a else None


# ------------------------------------------------------------------ 患者输入
def _side_from_marks(marks: list[dict]) -> str | None:
    idx = region_index()
    sides = {idx[m["region_id"]]["side"] for m in marks if m.get("kind", "primary") == "primary" and m["region_id"] in idx}
    lateral = sides - {"center"}
    if not sides:
        return None
    if not lateral:
        return "center"
    return lateral.pop() if len(lateral) == 1 else "both"


def add_body_map(session: Session, enc: Encounter, marks: list[dict]) -> dict:
    _assert_editable(enc)
    protocol = for_encounter(session, enc)
    idx = region_index()
    for m in marks:
        if m["region_id"] not in idx:
            raise FlowError(f"未知身体区域: {m['region_id']}")
    entry = add_entry(session, enc, EntryKind.BODY_MAP, {"marks": marks})
    primary = sorted({m["region_id"] for m in marks if m.get("kind", "primary") == "primary"})
    radiation = sorted({m["region_id"] for m in marks if m.get("kind") == "radiation"})
    bm = protocol.body_map
    if primary:
        quote = "身体图标记：" + "、".join(idx[r]["label"] for r in primary)
        set_fact(session, enc, protocol, bm.regions_fact_key, status=FactStatus.PRESENT, value=primary,
                 evidence=[{"entry_id": entry.id, "quote": quote, "kind": "body_map"}], source=FactSource.BODY_MAP)
        side = _side_from_marks(marks)
        if side:
            set_fact(session, enc, protocol, bm.side_fact_key, status=FactStatus.PRESENT, value=side,
                     evidence=[{"entry_id": entry.id, "quote": quote, "kind": "body_map"}], source=FactSource.BODY_MAP)
    if radiation and bm.radiation_fact_key:
        quote = "身体图放射标记：" + "、".join(idx[r]["label"] for r in radiation)
        set_fact(session, enc, protocol, bm.radiation_fact_key, status=FactStatus.PRESENT, value=radiation,
                 evidence=[{"entry_id": entry.id, "quote": quote, "kind": "body_map"}], source=FactSource.BODY_MAP)
        if "radiation_present" in protocol.fact_index:  # 有"是否放射"事实的协议才推导（膝痛等协议没有）
            set_fact(session, enc, protocol, "radiation_present", status=FactStatus.PRESENT, value=True,
                     evidence=[{"entry_id": entry.id, "quote": quote, "kind": "body_map"}], source=FactSource.BODY_MAP)
    # 注意：没有放射标记 ≠ 否认放射。radiation_present 保持 not_asked，由问询确认。
    if enc.status == EncounterStatus.DRAFT:
        enc.status = EncounterStatus.QUESTIONING
        session.add(enc)
        session.commit()
    alerts = evaluate_red_flags(session, enc, protocol)
    return {"entry_id": entry.id, "new_alerts": [_alert_to_dict(a) for a in alerts]}


def add_text(session: Session, enc: Encounter, text: str, *, origin_answer_id: str | None = None) -> dict:
    _assert_editable(enc)
    protocol = for_encounter(session, enc)
    text = text.strip()
    if not text:
        raise FlowError("描述不能为空")
    payload = {"text": text}
    if origin_answer_id:
        payload["origin_answer_id"] = origin_answer_id
    entry = add_entry(session, enc, EntryKind.FREE_TEXT, payload)
    # 随访专用事实只在随访阶段抽取
    result = extract_and_apply(session, enc, _stage_protocol_view(protocol, enc), entry)
    # 抽取过程记审计（原始记录保持不可变）：用了哪个模型、写入/丢弃几条、协议外提到了什么（带标记），医生端逐条可见
    audit(session, "system", "extraction.completed", "entry", entry.id, {
        "provider": result["provider"], "applied": [a["key"] for a in result["applied"]],
        "applied_detail": [{"key": a["key"], "status": a["status"], "pass": a.get("pass", "main")} for a in result["applied"]],
        "red_flag_pass": result.get("red_flag_pass"),
        "context_events": result.get("context_events", []),
        "rejected": [{"key": r["candidate"].get("key"), "reason": r["reason"]} for r in result["rejected"]],
        "unmapped": result.get("unmapped_flagged", [])})
    if enc.status == EncounterStatus.DRAFT:
        enc.status = EncounterStatus.QUESTIONING
        session.add(enc)
        session.commit()
    alerts = evaluate_red_flags(session, enc, protocol)
    return {"entry_id": entry.id, "extraction": result, "new_alerts": [_alert_to_dict(a) for a in alerts]}


def lexicon_replay(session: Session, enc: Encounter, entry_id: str) -> dict:
    """"用词表重放这句"（第 1 轮团队评审 · 计算机）：同一句原话交给离线词表再读一遍，只读、不写库，
    与当时模型的结果左右对照——让医生和评委看到"读出来的差别"具体在哪。"""
    from ..llm.provider import MockProvider, red_flag_keys_for_pass

    protocol = for_encounter(session, enc)
    entry = session.get(Entry, entry_id)
    if entry is None or entry.encounter_id != enc.id or entry.kind != EntryKind.FREE_TEXT:
        raise FlowError("找不到这条原话")
    text = entry.payload.get("text", "")
    view = _stage_protocol_view(protocol, enc)
    fi = protocol.fact_index
    screen = set(red_flag_keys_for_pass(protocol))

    def item(key: str, status: str, value: Any, quote: str | None) -> dict:
        d = fi[key]
        return {"key": key, "label": d.label, "status": status, "value_label": display_value(d, status, value),
                "quote": quote, "red_flag": key in screen}

    lex = []
    for c in MockProvider().extract(text, view).facts:
        if c.key in fi and c.quote and c.quote in text:
            lex.append(item(c.key, c.status, c.value, c.quote))
    log = session.exec(select(AuditLog).where(AuditLog.action == "extraction.completed", AuditLog.target_id == entry.id)).first()
    detail = (log.detail if log else {}) or {}
    model = [{"key": a["key"], "label": fi[a["key"]].label if a["key"] in fi else a["key"], "status": a["status"],
              "pass": a.get("pass"), "red_flag": a["key"] in screen} for a in detail.get("applied_detail", [])]
    lk = {(x["key"], x["status"]) for x in lex}
    mk = {(x["key"], x["status"]) for x in model}
    return {"entry_id": entry.id, "text": text, "provider": detail.get("provider"), "model": model, "lexicon": lex,
            "only_model": sorted({k for k, _ in mk - lk}), "only_lexicon": sorted({k for k, _ in lk - mk}),
            "red_flag_pass": detail.get("red_flag_pass"),
            "note": "离线词表只读、不写库；模型一栏是当时实际写入的整理结果。"}


def _stage_protocol_view(protocol: Protocol, enc: Encounter) -> Protocol:
    if enc.kind == EncounterKind.FOLLOW_UP:
        return protocol
    return protocol.model_copy(update={"facts": [f for f in protocol.facts if f.category != "followup"]})


def get_next_question(session: Session, enc: Encounter) -> Optional[dict]:
    protocol = for_encounter(session, enc)
    if enc.status in (EncounterStatus.DRAFT, EncounterStatus.QUESTIONING):
        pending = pending_question(session, enc.id)
        if pending and active_stop_alerts(session, enc, protocol):
            if pending.kind != "verification" or (pending.payload or {}).get("scope") != "urgent":
                pending.answer_status = "superseded"
                session.add(pending); session.commit()
                audit(session, "system", "question.interrupted_for_urgent", "encounter", enc.id,
                      {"question_id": pending.question_id})
                pending = None
        if pending:
            payload = _asked_to_payload(pending, protocol)
            if payload:
                return payload
        q = next_question(session, enc, protocol)
        if q is None:
            enc.status = EncounterStatus.AWAITING_PATIENT_CONFIRMATION
            session.add(enc)
            session.commit()
            return None
        register_asked(session, enc, q)
        return q
    return None


def stop_info(session: Session, enc: Encounter) -> dict:
    """问询是否因紧急红旗而终止；患者端据此显示"立即联系门诊 / 拨打急救电话"页。"""
    protocol = for_encounter(session, enc)
    stops = active_stop_alerts(session, enc, protocol)
    if not stops or pending_question(session, enc.id):
        return {"stop_reason": None, "stop_alerts": []}
    alerts = [_alert_to_dict(a) for a in stops]
    return {"stop_reason": "urgent_red_flag", "stop_alerts": alerts, "urgent_view": urgent_view(protocol, alerts)}


def _asked_to_payload(aq: AskedQuestion, protocol: Protocol) -> Optional[dict]:
    if aq.payload:
        return aq.payload
    fact_key = aq.fact_keys[0]
    if aq.kind == "red_flag_grid":
        from ..questioning.engine import GRID_OPTIONS
        return {"question_id": aq.question_id, "fact_key": fact_key, "fact_keys": aq.fact_keys,
                "text": aq.text, "preface": protocol.screening.grid_preface,
                "type": "grid", "kind": "red_flag_grid", "tier": 1,
                "allow_unknown": False, "allow_skip": False, "items": aq.options, "options": GRID_OPTIONS}
    if aq.kind == "verification":
        scope = aq.question_id.split(":")[1] if aq.question_id.count(":") >= 2 else "normal"
        return {"question_id": aq.question_id, "fact_key": fact_key, "fact_keys": aq.fact_keys, "text": aq.text,
                "type": "verify", "kind": "verification", "scope": scope, "tier": 1, "allow_unknown": True,
                "allow_skip": False, "items": aq.options,
                "options": [{"value": "confirm", "label": "对"}, {"value": "reject", "label": "不对"},
                            {"value": "unsure", "label": "不确定"}]}
    if aq.kind == "clarification":
        return {"question_id": aq.question_id, "fact_key": fact_key, "text": aq.text, "type": "single_choice",
                "kind": "clarification", "allow_unknown": True, "allow_skip": False, "options": aq.options}
    q = protocol.question_index.get(aq.question_id)
    if not q:
        return None
    from ..questioning.engine import _question_to_payload
    return _question_to_payload(q, protocol)


def answer_question(session: Session, enc: Encounter, question_id: str, *, value: Any = None,
                    unknown: bool = False, skipped: bool = False) -> dict:
    _assert_editable(enc)
    protocol = for_encounter(session, enc)
    aq = session.exec(select(AskedQuestion).where(AskedQuestion.encounter_id == enc.id,
                                                  AskedQuestion.question_id == question_id,
                                                  AskedQuestion.answer_status == "pending")).first()
    if not aq:
        raise FlowError("没有待回答的该问题")
    fact_key = aq.fact_keys[0]
    fdef = protocol.fact(fact_key)
    if aq.kind == "event_context":
        from ..events.service import apply_answer
        entry, rejected = apply_answer(session, enc, protocol, aq, value, unknown or skipped)
        _dispute_alerts_after_rejection(session, enc, protocol, rejected, entry)
        alerts = evaluate_red_flags(session, enc, protocol)
        return {"entry_id": entry.id, "new_alerts": [_alert_to_dict(a) for a in alerts]}
    if aq.kind == "verification":
        return _answer_verification(session, enc, protocol, aq, value, unknown=unknown or skipped)
    if aq.kind == "red_flag_grid":
        if unknown or skipped:
            raise FlowError("红旗一屏每一行都需要选择：有 / 没有 / 不确定")
        return _answer_red_flag_grid(session, enc, protocol, aq, value)
    payload = {"question_id": question_id, "fact_key": fact_key, "value": value, "unknown": unknown, "skipped": skipped,
               "question_text": aq.text}
    if not (unknown or skipped) and aq.kind != "clarification":
        _interpret_answer(fdef, aq, value)  # 先校验，非法值不落原始记录
    entry = add_entry(session, enc, EntryKind.ANSWER, payload)
    aq.answer_entry_id = entry.id

    if unknown or skipped:
        aq.answer_status = "unknown" if unknown else "skipped"
        if aq.kind == "clarification":
            _resolve_clarification(session, enc, protocol, fact_key, "unknown", entry)
        elif unknown and fact_key in protocol.red_flag_screen_keys:
            # 红旗题上的"不清楚"是患者表达不确定，要让 rf_uncertain_red_flag 接住（第 1 轮团队评审 P0-2）
            set_fact(session, enc, protocol, fact_key, status=FactStatus.UNCERTAIN, value=None,
                     evidence=[{"entry_id": entry.id, "quote": "患者选择：不清楚", "kind": "answer"}],
                     source=FactSource.ANSWER, is_correction=False)
        else:
            mark_asked_unanswered(session, enc, fact_key, {"entry_id": entry.id, "quote": "患者选择：不清楚" if unknown else "患者选择：跳过", "kind": "answer"})
    else:
        aq.answer_status = "answered"
        if aq.kind == "clarification":
            opt = next((o for o in aq.options if str(o.get("value")) == str(value)), None)
            if not opt:
                raise FlowError("无效的澄清选项")
            _resolve_clarification(session, enc, protocol, fact_key, opt["resolve"], entry, opt.get("label"))
        else:
            status, val, quote = _interpret_answer(fdef, aq, value)
            cur = current_facts(session, enc.id)[fact_key]
            # 红旗筛查题的直接回答，优先于模型读出的"有 / 没有"（红旗不对称信任）；其它事实照旧：不一致就进澄清
            override = fact_key in protocol.red_flag_screen_keys and cur.status != status and not has_direct_answer(cur) \
                and cur.status not in (FactStatus.NOT_ASKED, FactStatus.ASKED_UNANSWERED)
            set_fact(session, enc, protocol, fact_key, status=status, value=val,
                     evidence=[{"entry_id": entry.id, "quote": quote, "kind": "answer"}], source=FactSource.ANSWER,
                     is_correction=override)
    session.add(aq)
    session.commit()
    qdef = protocol.question_index.get(aq.question_id)
    if not (unknown or skipped) and aq.kind == "protocol" and qdef and qdef.extract_answer:
        # 这是明确的新症状输入：保留原问答，再经同一原话抽取/证据/红旗流程。
        # 复述与执行安排等文本没有此标记，避免把医嘱中的条件句当成现实症状。
        symptom = add_text(session, enc, str(value), origin_answer_id=entry.id)
        return {"entry_id": entry.id, "symptom_entry_id": symptom["entry_id"], "new_alerts": symptom["new_alerts"]}
    alerts = evaluate_red_flags(session, enc, protocol)
    return {"entry_id": entry.id, "new_alerts": [_alert_to_dict(a) for a in alerts]}


_GRID_STATUS = {"yes": (FactStatus.PRESENT, True, "有"), "no": (FactStatus.DENIED, None, "没有"),
                "unsure": (FactStatus.UNCERTAIN, None, "不确定")}


def _answer_red_flag_grid(session: Session, enc: Encounter, protocol: Protocol, aq: AskedQuestion, value: Any) -> dict:
    """红旗一屏：每一行是一次直接回答。直接回答与模型读出的结果不一致时以直接回答为准（红旗不对称信任），
    被取代的抽取证据留在版本链里供医生追溯。"""
    items = [i for i in (aq.options or []) if isinstance(i, dict)]
    if not isinstance(value, dict):
        raise FlowError("红旗一屏的回答格式应为 {题目: yes|no|unsure}")
    answers = {i["question_id"]: str(value.get(i["question_id"], "")) for i in items}
    if any(v not in _GRID_STATUS for v in answers.values()):
        raise FlowError("每一行都需要选择：有 / 没有 / 不确定")
    entry = add_entry(session, enc, EntryKind.ANSWER, {"question_id": aq.question_id, "kind": "red_flag_grid",
                                                       "answers": answers, "question_text": aq.text,
                                                       "items": [{"question_id": i["question_id"], "fact_key": i["fact_key"],
                                                                  "text": i["text"]} for i in items]})
    aq.answer_entry_id = entry.id
    aq.answer_status = "answered"
    session.add(aq)
    session.commit()
    for it in items:
        status, val, word = _GRID_STATUS[answers[it["question_id"]]]
        cur = current_facts(session, enc.id)[it["fact_key"]]
        override = cur.status != status and cur.status not in (FactStatus.NOT_ASKED, FactStatus.ASKED_UNANSWERED) \
            and not has_direct_answer(cur)
        set_fact(session, enc, protocol, it["fact_key"], status=status, value=val,
                 evidence=[{"entry_id": entry.id, "kind": "answer", "quote": f"回答「{it['text']}」：{word}"}],
                 source=FactSource.ANSWER, is_correction=override)
    alerts = evaluate_red_flags(session, enc, protocol)
    return {"entry_id": entry.id, "new_alerts": [_alert_to_dict(a) for a in alerts]}


def _answer_verification(session: Session, enc: Encounter, protocol: Protocol, aq: AskedQuestion, value: Any,
                         *, unknown: bool) -> dict:
    """一键核对：confirm 追加一条患者确认证据；reject 让事实回到"未询问"并由协议问题重问；unsure 记为不确定。"""
    items = aq.options or []
    keys = [i["fact_key"] for i in items]
    if unknown:
        decisions = {k: "unsure" for k in keys}
    else:
        if not isinstance(value, dict):
            raise FlowError("核对题的回答格式应为 {事实: confirm|reject|unsure}")
        decisions = {k: str(value.get(k, "")) for k in keys}
        bad = [k for k, v in decisions.items() if v not in ("confirm", "reject", "unsure")]
        if bad:
            raise FlowError("每一条都需要选择：对 / 不对 / 不确定")
    entry = add_entry(session, enc, EntryKind.ANSWER, {"question_id": aq.question_id, "kind": "verification",
                                                       "decisions": decisions, "question_text": aq.text,
                                                       "items": [{"fact_key": i["fact_key"], "label": i["label"],
                                                                  "value_label": i["value_label"], "quote": i["quote"]} for i in items]})
    aq.answer_entry_id = entry.id
    aq.answer_status = "unknown" if unknown else "answered"
    session.add(aq)
    session.commit()
    word = {"confirm": "对", "reject": "不对", "unsure": "不确定"}
    facts = current_facts(session, enc.id)
    for it in items:
        k, d = it["fact_key"], decisions[it["fact_key"]]
        f = facts.get(k)
        if f is None or f.status not in (FactStatus.PRESENT, FactStatus.DENIED, FactStatus.UNCERTAIN):
            continue  # 核对期间事实已被其它输入改变，以当前为准
        ev = {"entry_id": entry.id, "kind": "answer",
              "quote": f"患者核对「{it['label']}：{it['value_label']}」：{word[d]}"}
        if d == "confirm":
            attach_evidence(session, enc, k, ev)
        elif d == "reject":
            reject_extracted_fact(session, enc, k, ev)
        else:
            set_fact(session, enc, protocol, k, status=FactStatus.UNCERTAIN, value=f.value, evidence=[ev],
                     source=FactSource.CORRECTION, is_correction=True)
    _dispute_alerts_after_rejection(session, enc, protocol, [k for k, d in decisions.items() if d == "reject"], entry)
    alerts = evaluate_red_flags(session, enc, protocol)
    return {"entry_id": entry.id, "new_alerts": [_alert_to_dict(a) for a in alerts]}


def _dispute_alerts_after_rejection(session: Session, enc: Encounter, protocol: Protocol, rejected: list[str],
                                    entry: Entry) -> None:
    """触发红旗的整理被患者否定、且规则条件已不再成立：红旗与任务保留给医生复核，但不再终止问询。"""
    if not rejected:
        return
    rules = {r.id: r for r in protocol.red_flags}
    expr_map = as_expr_map(current_facts(session, enc.id))
    for a in session.exec(select(Alert).where(Alert.encounter_id == enc.id)).all():
        rule = rules.get(a.rule_id)
        if not rule or a.patient_disputed or not (set(rule.fact_keys) & set(rejected)):
            continue
        if evaluate(rule.when, expr_map):
            continue
        a.patient_disputed = True
        a.dispute_entry_id = entry.id
        session.add(a)
        add_entry(session, enc, EntryKind.SYSTEM_NOTICE,
                  {"text": f"患者核对时表示触发「{a.label}」的整理不对；红旗与任务保留，请医生复核。", "rule_id": a.rule_id,
                   "kind": "patient_disputed"})
        for t in session.exec(select(Task).where(Task.alert_id == a.id)).all():
            t.history = t.history + [{"to": t.status, "by": "system", "at": iso(now()),
                                      "note": "患者核对时表示该整理不对，请电话确认"}]
            t.updated_at = now()
            session.add(t)
    session.commit()


def _interpret_answer(fdef, aq: AskedQuestion, value: Any) -> tuple[str, Any, str]:
    labels = {str(o.get("value")): o.get("label") for o in aq.options}
    if fdef.type == "bool":
        v = str(value).strip().lower()
        if v in ("no", "false", "0", "否", "没有"):
            return FactStatus.DENIED, None, f"回答「{aq.text}」：没有"
        if v in ("yes", "true", "1", "是", "有"):
            return FactStatus.PRESENT, True, f"回答「{aq.text}」：有"
        raise FlowError("是/否题只接受 yes / no；不清楚请用 unknown，跳过请用 skipped")
    if fdef.type == "enum" and labels and str(value) not in labels:
        raise FlowError(f"无效选项：{value}")
    if fdef.type in ("multi_enum",) and labels:
        vals = value if isinstance(value, list) else [value]
        if not vals or any(str(v) not in labels for v in vals):
            raise FlowError("多选题包含无效选项")
    if fdef.type in ("scale", "number"):
        try:
            num = float(value)
        except (TypeError, ValueError):
            raise FlowError("请填写数字")
        if (fdef.min is not None and num < fdef.min) or (fdef.max is not None and num > fdef.max):
            raise FlowError(f"数值应在 {fdef.min}–{fdef.max} 之间")
    if fdef.type in ("multi_enum", "body_regions"):
        vals = value if isinstance(value, list) else [value]
        if fdef.type == "body_regions":
            idx = region_index()
            text = "、".join(idx.get(v, {}).get("label", v) for v in vals)
        else:
            text = "、".join(labels.get(str(v), str(v)) for v in vals)
        return FactStatus.PRESENT, vals, f"回答「{aq.text}」：{text}"
    if fdef.type in ("scale", "number"):
        return FactStatus.PRESENT, value, f"回答「{aq.text}」：{value}"
    if fdef.type == "enum":
        return FactStatus.PRESENT, str(value), f"回答「{aq.text}」：{labels.get(str(value), value)}"
    return FactStatus.PRESENT, str(value), f"回答「{aq.text}」：{value}"


def _resolve_clarification(session: Session, enc: Encounter, protocol: Protocol, fact_key: str, resolve: Any,
                           entry: Entry, label: str | None = None) -> None:
    facts = current_facts(session, enc.id)
    f = facts[fact_key]
    cands = (f.value or {}).get("candidates", [])
    first, second = cands[0], cands[-1]
    ev = [{"entry_id": entry.id, "quote": f"澄清回答：{label or resolve}", "kind": "answer"}]
    if resolve == "keep_first":
        set_fact(session, enc, protocol, fact_key, status=first["status"], value=first.get("value"), evidence=ev,
                 source=FactSource.CORRECTION, is_correction=True)
    elif resolve in ("keep_second", "changed_to_second"):
        set_fact(session, enc, protocol, fact_key, status=second["status"], value=second.get("value"), evidence=ev,
                 source=FactSource.CORRECTION, is_correction=True)
        if resolve == "changed_to_second":
            add_entry(session, enc, EntryKind.SYSTEM_NOTICE, {"text": f"患者说明「{protocol.fact(fact_key).label}」发生了变化", "fact_key": fact_key})
    elif resolve == "both":
        fdef = protocol.fact(fact_key)
        if fdef.type == "enum" and any(o.value == "both" for o in fdef.options):
            set_fact(session, enc, protocol, fact_key, status=FactStatus.PRESENT, value="both", evidence=ev,
                     source=FactSource.CORRECTION, is_correction=True)
        elif fdef.type in ("multi_enum", "body_regions"):
            merged = sorted(set((first.get("value") or []) + (second.get("value") or [])))
            set_fact(session, enc, protocol, fact_key, status=FactStatus.PRESENT, value=merged, evidence=ev,
                     source=FactSource.CORRECTION, is_correction=True)
        else:
            set_fact(session, enc, protocol, fact_key, status=FactStatus.UNCERTAIN, value=second.get("value"),
                     evidence=ev + first.get("evidence", []) + second.get("evidence", []),
                     source=FactSource.CORRECTION, is_correction=True)
    elif isinstance(resolve, dict):
        set_fact(session, enc, protocol, fact_key, status=resolve.get("status", FactStatus.PRESENT),
                 value=resolve.get("value"), evidence=ev, source=FactSource.CORRECTION, is_correction=True)
    else:  # unknown
        set_fact(session, enc, protocol, fact_key, status=FactStatus.UNCERTAIN, value=None,
                 evidence=ev + first.get("evidence", []) + second.get("evidence", []),
                 source=FactSource.CORRECTION, is_correction=True)
    _propagate_side_to_regions(session, enc, protocol, fact_key, ev)


def _propagate_side_to_regions(session: Session, enc: Encounter, protocol: Protocol, fact_key: str, ev: list[dict]) -> None:
    """患者澄清"其实是右侧"之后，身体图上与之矛盾的左侧标记不能继续当作事实。"""
    bm = protocol.body_map
    if fact_key != bm.side_fact_key:
        return
    facts = current_facts(session, enc.id)
    side, regions = facts[bm.side_fact_key], facts[bm.regions_fact_key]
    if side.status != FactStatus.PRESENT or side.value not in ("left", "right", "center") or regions.status != FactStatus.PRESENT:
        return
    idx = region_index()
    kept = [r for r in (regions.value or []) if idx.get(r, {}).get("side") in (side.value, "center")]
    if kept == list(regions.value or []):
        return
    if kept:
        set_fact(session, enc, protocol, bm.regions_fact_key, status=FactStatus.PRESENT, value=kept,
                 evidence=regions.evidence + ev, source=FactSource.CORRECTION, is_correction=True)
    else:
        set_fact(session, enc, protocol, bm.regions_fact_key, status=FactStatus.UNCERTAIN, value=None,
                 evidence=regions.evidence + ev, source=FactSource.CORRECTION, is_correction=True)


# ------------------------------------------------------------------ 红旗
def evaluate_red_flags(session: Session, enc: Encounter, protocol: Protocol) -> list[Alert]:
    from ..protocol.triage import evaluate_rule
    facts = current_facts(session, enc.id)
    expr_map = as_expr_map(facts)
    existing = {a.rule_id: a for a in session.exec(select(Alert).where(Alert.encounter_id == enc.id)).all()}
    new_alerts = []
    for rule in protocol.red_flags:
        triggered, provisional = evaluate_rule(rule, expr_map)
        if not triggered:
            continue
        if rule.id in existing:
            a = existing[rule.id]
            if a.provisional != provisional:
                a.provisional = provisional
                a.label = ("待核实：" if provisional else "") + rule.label
                a.patient_message = (rule.conflict_patient_message or rule.patient_message) if provisional else rule.patient_message
                session.add(a); session.commit()
                notice = add_entry(session, enc, EntryKind.SYSTEM_NOTICE, {"text": a.patient_message, "rule_id": rule.id,
                    "severity": rule.severity, "provisional": provisional, "kind": "red_flag_status_updated", "approved_content": True})
                a.notice_entry_id = notice.id
                session.add(a); session.commit()
            if a.patient_disputed:  # 患者之前否认了误抽，现在有新表达或矛盾候选 → 重新核实
                a.patient_disputed = False
                session.add(a)
                add_entry(session, enc, EntryKind.SYSTEM_NOTICE,
                          {"text": f"「{a.label}」收到新的相关表达，重新列为待核实事项。", "rule_id": a.rule_id, "kind": "reactivated"})
                session.commit()
                new_alerts.append(a)
            continue
        evidence = []
        for k in rule.fact_keys:
            f = facts.get(k)
            if f is not None and f.status != FactStatus.NOT_ASKED:
                evidence.append({"fact_key": k, "status": f.status, "value": f.value, "evidence": f.evidence})
        alert = Alert(encounter_id=enc.id, rule_id=rule.id, severity=rule.severity, label=("待核实：" if provisional else "") + rule.label,
                      provisional=provisional,
                      patient_message=(rule.conflict_patient_message or rule.patient_message) if provisional else rule.patient_message, evidence=evidence,
                      route=route_of(protocol, rule.id, rule.severity), in_service_hours=in_service_hours(protocol))
        session.add(alert)
        session.commit()
        session.refresh(alert)
        if rule.action == "immediate_notice_and_task":
            notice = add_entry(session, enc, EntryKind.SYSTEM_NOTICE,
                               {"text": alert.patient_message, "rule_id": rule.id, "severity": rule.severity, "approved_content": True,
                                "provisional": provisional})
            alert.notice_entry_id = notice.id
            session.add(alert)
            session.commit()
        create_routed_task(session, protocol, enc.id, rule.task_kind, f"[{rule.severity}] {rule.label}",
                           severity=rule.severity, alert_id=alert.id)
        after_hours_callback(session, protocol, enc.id, alert)
        new_alerts.append(alert)
    return new_alerts


def _alert_to_dict(a: Alert) -> dict:
    return {"id": a.id, "rule_id": a.rule_id, "severity": a.severity, "label": a.label,
            "patient_message": a.patient_message, "evidence": a.evidence, "notice_shown": bool(a.notice_entry_id), "provisional": a.provisional,
            "patient_disputed": bool(a.patient_disputed), "route": a.route, "in_service_hours": a.in_service_hours,
            "created_at": iso(a.created_at)}


def active_notices(session: Session, enc: Encounter) -> list[dict]:
    """患者端任何页面都要显示的、协议批准的紧急提示。"""
    alerts = session.exec(select(Alert).where(Alert.encounter_id == enc.id)).all()
    return [_alert_to_dict(a) for a in alerts if a.notice_entry_id]


# ------------------------------------------------------------------ 患者确认
def confirmation_view(session: Session, enc: Encounter) -> dict:
    from ..events.service import OPTIONS, events_for, patient_event_dict
    protocol = for_encounter(session, enc)
    facts = current_facts(session, enc.id)
    fi = protocol.fact_index
    groups = {"confirmed": [], "uncertain": [], "unanswered": [], "conflicting": []}
    for k in [x for x in protocol.summary.key_facts_order if x in facts] + [x for x in facts if x not in protocol.summary.key_facts_order]:
        f, d = facts[k], fi[k]
        if enc.kind != EncounterKind.FOLLOW_UP and d.category == "followup":
            continue
        item = fact_to_dict(f, d)
        item["options"] = [{"value": o.value, "label": o.label} for o in d.options]
        if f.status in (FactStatus.PRESENT, FactStatus.DENIED, FactStatus.UNCERTAIN):
            item["patient_value_label"] = patient_value_label(d, f.status, f.value)  # 给患者看："没有 / 好像有"，不用医生术语
        if f.status in (FactStatus.PRESENT, FactStatus.DENIED):
            groups["confirmed"].append(item)
        elif f.status == FactStatus.UNCERTAIN:
            groups["uncertain"].append(item)
        elif f.status == FactStatus.CONFLICTING:
            groups["conflicting"].append(item)
        elif f.status == FactStatus.ASKED_UNANSWERED or (d.required and f.status == FactStatus.NOT_ASKED):
            groups["unanswered"].append(item)
    stop = stop_info(session, enc)
    urgent = stop["stop_reason"] == "urgent_red_flag"
    more_questions = not bool(active_stop_alerts(session, enc, protocol)) and bool(pending_question(session, enc.id) or next_question(session, enc, protocol))
    return {"encounter_id": enc.id, "status": enc.status, "groups": groups, "notices": active_notices(session, enc),
            "symptom_events": [patient_event_dict(e) for e in events_for(session, enc.id)], "context_options": OPTIONS,
            **stop,
            "requires_more_questions": more_questions,
            "can_confirm": not more_questions and (urgent or not groups["conflicting"])
            and enc.status in (EncounterStatus.AWAITING_PATIENT_CONFIRMATION, EncounterStatus.QUESTIONING)}


def patient_confirm(session: Session, enc: Encounter, corrections: list[dict] | None = None) -> dict:
    protocol = for_encounter(session, enc)
    if enc.status not in (EncounterStatus.AWAITING_PATIENT_CONFIRMATION, EncounterStatus.QUESTIONING):
        raise FlowError(f"当前状态 {enc.status} 不能确认")
    # 不能通过直接打开确认页绕过安全问询；已经触发紧急提示时仍允许立即交接已有记录。
    urgent_handoff = bool(active_stop_alerts(session, enc, protocol))
    if not urgent_handoff and (pending_question(session, enc.id) or next_question(session, enc, protocol)):
        raise FlowError("仍有待回答或核实的问题，请先完成；拿不准请如实选择不清楚")
    for c in corrections or []:
        key = c["fact_key"]
        fdef = protocol.fact(key)
        entry = add_entry(session, enc, EntryKind.CORRECTION, {"fact_key": key, "value": c.get("value"), "status": c.get("status", "present")})
        status = c.get("status", FactStatus.PRESENT)
        set_fact(session, enc, protocol, key, status=status, value=c.get("value"),
                 evidence=[{"entry_id": entry.id, "quote": f"患者在确认页修改「{fdef.label}」为：{display_value(fdef, status, c.get('value'))}", "kind": "correction"}],
                 source=FactSource.CORRECTION, is_correction=True)
    facts = current_facts(session, enc.id)
    urgent = urgent_handoff
    if any(f.status == FactStatus.CONFLICTING for f in facts.values()) and not urgent:
        raise FlowError("仍有矛盾未澄清，不能确认")  # 紧急终止时允许带矛盾提交，矛盾照常呈现给医生
    evaluate_red_flags(session, enc, protocol)
    mark_patient_confirmed(session, enc.id)
    enc.patient_confirmed_at = now()
    enc.status = EncounterStatus.READY_FOR_DOCTOR
    session.add(enc)
    session.commit()
    content = build_summary_content(session, enc, protocol)
    create_summary_version(session, enc, content, author="system")
    create_task(session, enc.id, "doctor_review", "待医生核对就诊摘要" if enc.kind == EncounterKind.PRE_VISIT else "待医生查看随访变化")
    from ..events.service import create_event_review_tasks, events_for
    for event in events_for(session, enc.id):
        create_event_review_tasks(session, enc, protocol, event)
    evaluate_recovery_rules(session, enc, protocol)
    report = run_checks(session, enc, protocol)
    return {"status": enc.status, "verification_passed": report.passed, "next_step": next_step_text(session, enc)}


def next_step_text(session: Session, enc: Encounter) -> str:
    protocol = for_encounter(session, enc)
    return (f"你的描述已经交给门诊医生核对。服务时间：{protocol.scope.service_hours}。"
            "如果出现页面上方提示的紧急情况，请不要等待线上回复。")


# ------------------------------------------------------------------ 医生端
def encounter_brief(session: Session, enc: Encounter) -> dict:
    patient = session.get(Patient, enc.patient_id)
    alerts = session.exec(select(Alert).where(Alert.encounter_id == enc.id)).all()
    tasks = session.exec(select(Task).where(Task.encounter_id == enc.id)).all()
    facts = current_facts(session, enc.id)
    return {
        "id": enc.id, "patient_code": patient.display_code if patient else None, "kind": enc.kind, "status": enc.status,
        "protocol_id": enc.protocol_id, "parent_encounter_id": enc.parent_encounter_id,
        "created_at": iso(enc.created_at), "updated_at": iso(enc.updated_at),
        "patient_confirmed_at": iso(enc.patient_confirmed_at), "doctor_confirmed_at": iso(enc.doctor_confirmed_at),
        "alert_max_severity": _max_severity([a.severity for a in alerts]),
        "triage": triage_of(alerts), "triage_rank": TRIAGE[triage_of(alerts)][0],
        "triage_label": triage_label(alerts), "triage_disputed": triage_disputed_only(alerts),
        "open_tasks": sum(1 for t in tasks if t.status != TaskStatus.COMPLETED),
        "conflicts": sum(1 for f in facts.values() if f.status == FactStatus.CONFLICTING),
        "respondent": enc.respondent, "respondent_label": RESPONDENT_LABEL.get(enc.respondent or "self"),
        "recovery_flags": [{"rule_id": (t.detail or {}).get("rule_id"), "label": (t.detail or {}).get("label"),
                            "slip_line": (t.detail or {}).get("slip_line"), "severity": t.severity}
                           for t in tasks if t.kind == "recovery_review" and t.status != TaskStatus.COMPLETED],
        "overdue_tasks": sum(1 for t in tasks if is_overdue(t)),
    }


def _max_severity(sevs: list[str]) -> str | None:
    order = ["urgent", "same_day", "routine"]
    for s in order:
        if s in sevs:
            return s
    return None


def _extraction_logs(session: Session, entries: list[Entry]) -> list[dict]:
    ids = [e.id for e in entries if e.kind == EntryKind.FREE_TEXT]
    if not ids:
        return []
    logs = session.exec(select(AuditLog).where(AuditLog.action == "extraction.completed", AuditLog.target_id.in_(ids))
                        .order_by(AuditLog.created_at)).all()
    return [{"entry_id": a.target_id, "at": iso(a.created_at), **a.detail} for a in logs]


def doctor_view(session: Session, enc: Encounter, actor: str | None = None) -> dict:
    from ..events.service import event_dict, events_for
    from ..course.teachback import doctor_responses
    from ..course.goals import view as functional_goals_view
    protocol = for_encounter(session, enc)
    if enc.status == EncounterStatus.READY_FOR_DOCTOR and actor:
        enc.status = EncounterStatus.UNDER_REVIEW
        session.add(enc)
        session.commit()
        audit(session, actor, "encounter.opened", "encounter", enc.id)
    facts = current_facts(session, enc.id)
    fi = protocol.fact_index
    entries = session.exec(select(Entry).where(Entry.encounter_id == enc.id).order_by(Entry.seq)).all()
    summary = latest_summary(session, enc.id)
    if summary is None and enc.status not in (EncounterStatus.DRAFT, EncounterStatus.QUESTIONING, EncounterStatus.AWAITING_PATIENT_CONFIRMATION):
        summary = create_summary_version(session, enc, build_summary_content(session, enc, protocol), "system")
    summary_out = None
    if summary:
        summary_out = {"id": summary.id, "version": summary.version, "author": summary.author, "note": summary.note,
                       "content": summary.content, "created_at": iso(summary.created_at), "provisional": False}
    elif enc.status != EncounterStatus.DRAFT and any(True for _ in session.exec(select(Alert).where(Alert.encounter_id == enc.id)).all()):
        # 患者还没确认、但已有红旗：给医护一份临时整理（不落库、不算版本），便于立即电话联系
        summary_out = {"id": None, "version": 0, "author": "system", "note": "患者尚未确认，以下为临时整理",
                       "content": build_summary_content(session, enc, protocol), "created_at": iso(now()), "provisional": True}
    # 浏览时只计算、不落库；状态变化（确认、修正、编辑）时才保存报告
    report = run_checks(session, enc, protocol, persist=False) if summary_out else latest_report(session, enc.id)
    versions = session.exec(select(Summary).where(Summary.encounter_id == enc.id).order_by(Summary.version)).all()
    order = [k for k in protocol.summary.key_facts_order if k in facts] + [k for k in facts if k not in protocol.summary.key_facts_order]
    alerts_all = session.exec(select(Alert).where(Alert.encounter_id == enc.id)).all()
    tasks_all = session.exec(select(Task).where(Task.encounter_id == enc.id)).all()
    elig = eligibility_record(session, enc)
    return {
        # 接诊速览：紧急程度 + 一句话主诉 + 面诊要当面确认的几件事（确定性整理，不做诊断）
        "brief": visit_brief(protocol, enc, facts, alerts_all, tasks_all, summary_out),
        # 病历初稿：只用患者确认过的事实拼成主诉 / 现病史，医生核对后复制到门诊病历
        "record_draft": record_draft(protocol, enc, facts, alerts_all, elig, enc.patient_confirmed_at is not None,
                                     iso(enc.patient_confirmed_at or now())[:10]),
        "encounter": encounter_brief(session, enc),
        "protocol": {"id": protocol.protocol_id, "version": protocol.version, "status": protocol.status, "title": protocol.title},
        "protocol_snapshot": {**protocol.model_dump(mode="json"), "review_gaps": protocol.review_gaps(),
                              "content_sha256": enc.protocol_sha256, "snapshot_verified": bool(enc.protocol_sha256)},
        "clinic_timezone": settings.clinic_tz,
        "symptom_events": [event_dict(session, enc, protocol, e) for e in events_for(session, enc.id)],
        "teachback_responses": doctor_responses(session, enc),
        "functional_goals": functional_goals_view(session, enc),
        "summary": summary_out,
        "summary_versions": [{"id": s.id, "version": s.version, "author": s.author, "note": s.note, "created_at": iso(s.created_at)} for s in versions],
        "facts": [annotate_fact_item(fact_to_dict(facts[k], fi[k]), fi[k], protocol) for k in order
                  if (enc.kind == EncounterKind.FOLLOW_UP or fi[k].category != "followup")],
        "extractions": _extraction_logs(session, entries),
        "eligibility": elig,
        "stop": stop_info(session, enc),
        "entries": [{"id": e.id, "seq": e.seq, "kind": e.kind, "payload": e.payload, "created_at": iso(e.created_at)} for e in entries],
        "alerts": [_alert_to_dict(a) for a in session.exec(select(Alert).where(Alert.encounter_id == enc.id)).all()],
        "tasks": [task_to_dict(t) for t in session.exec(select(Task).where(Task.encounter_id == enc.id)).all()],
        "notifications": [notification_to_dict(n) for n in session.exec(select(Notification).where(Notification.encounter_id == enc.id)).all()],
        "verification": {"id": report.id, "passed": report.passed, "checks": report.checks,
                         "created_at": iso(report.created_at or now())} if report else None,
        "change_card": change_card(session, enc) if enc.kind == EncounterKind.FOLLOW_UP else None,
        # 恢复轨迹卡：以首诊为基线、按医生设定的最小临床重要差异判读（首诊时只有基线一点）
        "trajectory": trajectory(session, enc, protocol),
        "respondent": {"value": enc.respondent, "label": RESPONDENT_LABEL.get(enc.respondent or "self"),
                       "relation": enc.respondent_relation, "proxy_consent": enc.proxy_consent},
        "followup_plan": enc.followup_plan,
        "questions": [{"question_id": a.question_id, "text": a.text, "kind": a.kind, "answer_status": a.answer_status, "asked_at": iso(a.asked_at)}
                      for a in session.exec(select(AskedQuestion).where(AskedQuestion.encounter_id == enc.id).order_by(AskedQuestion.asked_at)).all()],
    }


def doctor_edit_summary(session: Session, enc: Encounter, actor: str, edits: dict, note: str | None) -> dict:
    protocol = for_encounter(session, enc)
    base = latest_summary(session, enc.id)
    if not base:
        raise FlowError("尚无摘要可修改")
    allowed = {"headline", "narrative", "doctor_notes"}
    bad = set(edits) - allowed
    if bad:
        raise FlowError(f"不允许修改的字段: {sorted(bad)}")
    content = dict(base.content)
    content["doctor_edits"] = {**base.content.get("doctor_edits", {}), **edits}
    for k, v in edits.items():
        if k in ("headline", "narrative"):
            content[k] = v
    content["edit_log"] = base.content.get("edit_log", []) + [{"by": actor, "at": iso(now()), "fields": sorted(edits), "note": note}]
    s = create_summary_version(session, enc, content, author=f"doctor:{actor}", note=note)
    audit(session, actor, "summary.edited", "summary", s.id, {"fields": sorted(edits), "base_version": base.version})
    run_checks(session, enc, protocol)
    return {"summary_id": s.id, "version": s.version}


def doctor_correct_fact(session: Session, enc: Encounter, actor: str, key: str, status: str, value: Any, note: str) -> dict:
    protocol = for_encounter(session, enc)
    if key not in protocol.fact_index:
        raise FlowError("未知事实")
    if not note:
        raise FlowError("医生修正必须写明依据")
    entry = add_entry(session, enc, EntryKind.DOCTOR_NOTE, {"fact_key": key, "status": status, "value": value, "note": note, "by": actor})
    f = set_fact(session, enc, protocol, key, status=status, value=value,
                 evidence=[{"entry_id": entry.id, "quote": f"医生修正：{note}", "kind": "doctor_note"}],
                 source=FactSource.DOCTOR, is_correction=True)
    audit(session, actor, "fact.corrected", "fact", f.id, {"key": key, "status": status, "value": value, "note": note})
    content = build_summary_content(session, enc, protocol)
    base = latest_summary(session, enc.id)
    if base:
        content["doctor_edits"] = base.content.get("doctor_edits", {})
        content["edit_log"] = base.content.get("edit_log", []) + [{"by": actor, "at": iso(now()), "fields": [f"fact:{key}"], "note": note}]
        for k, v in content["doctor_edits"].items():
            if k in ("headline", "narrative"):
                content[k] = v
    create_summary_version(session, enc, content, author=f"doctor:{actor}", note=f"修正事实 {key}")
    run_checks(session, enc, protocol)
    return {"fact_id": f.id, "version": f.version}


def doctor_confirm(session: Session, enc: Encounter, actor: str, override_reason: str | None = None) -> dict:
    protocol = for_encounter(session, enc)
    if enc.status not in (EncounterStatus.READY_FOR_DOCTOR, EncounterStatus.UNDER_REVIEW):
        raise FlowError(f"当前状态 {enc.status} 不能确认")
    if not enc.patient_confirmed_at:
        raise FlowError("患者尚未确认自己的表达")
    report = run_checks(session, enc, protocol)
    if not report.passed and not override_reason:
        raise FlowError("验收检查未通过；如需继续，必须填写 override_reason 并记录审计")
    enc.status = EncounterStatus.DOCTOR_CONFIRMED
    enc.doctor_confirmed_at = now()
    enc.doctor_confirmed_by = actor
    session.add(enc)
    session.commit()
    audit(session, actor, "encounter.doctor_confirmed", "encounter", enc.id, {"override_reason": override_reason, "verification_passed": report.passed})
    for t in session.exec(select(Task).where(Task.encounter_id == enc.id, Task.kind == "doctor_review")).all():
        if t.status == TaskStatus.UNVIEWED:
            transition_task(session, t, TaskStatus.VIEWED, actor, "医生打开摘要")
        if t.status != TaskStatus.COMPLETED:
            transition_task(session, t, TaskStatus.COMPLETED, actor, "医生已核对确认")
    run_checks(session, enc, protocol)
    return {"status": enc.status, "verification_passed": report.passed}


def _rewrite_mode() -> str:
    """给患者说明的改写方式：glossary（默认，医生审定的术语对照表，不调用模型）| llm（模型改写措辞，新内容拦截 + AI 标注）。"""
    import os

    from ..config import settings
    m = (os.environ.get("TIJI_PATIENT_REWRITE") or settings.patient_rewrite or "glossary").strip().lower()
    return m if m in ("glossary", "llm") else "glossary"


def _draft_frame(protocol: Protocol, interval: int) -> tuple[str, str, str]:
    """系统按协议附上的三句：问候、复诊时间、紧急提示。医学内容只来自医生要点。"""
    return ("你好，医生已经看过你这次填写的情况。",
            f"请在 {interval} 天后回到这里，更新你的情况。",
            f"如果出现以下情况，请不要等待，立即联系门诊或前往就近医院急诊：{protocol.scope.emergency_notice}")


def remaining_new_terms(protocol: Protocol, notes: str, message: str, interval: Optional[int] = None) -> list[dict]:
    """发出去的说明里，还有哪些医学内容是医生要点里没有的（去掉系统附上的句子、AI 标注与术语对照的解释之后再比）。"""
    import re as _re

    from ..verification.rewrite_guard import AI_LABEL, new_terms, strip_system_parts
    greet, back, emerg = _draft_frame(protocol, interval or protocol.followup.default_interval_days)
    removable = [greet, back, emerg, AI_LABEL, protocol.scope.emergency_notice] + \
                [f"（{g.plain}）" for g in protocol.followup.plain_language]
    core = strip_system_parts(message, removable)
    core = _re.sub(r"请在\s*\d+\s*天后回到这里，更新你的情况。", " ", core)
    return new_terms(notes, core, protocol.scope_guard.forbidden_patterns)


def set_followup_plan(session: Session, enc: Encounter, actor: str, plan: dict) -> dict:
    from ..verification.rewrite_guard import AI_LABEL, describe
    protocol = for_encounter(session, enc)
    if enc.status != EncounterStatus.DOCTOR_CONFIRMED:
        raise FlowError("只有医生确认后的就诊才能设置随访计划")
    if (enc.followup_plan or {}).get("version_id") != plan.get("expected_plan_version_id"):
        raise FlowError("计划版本已改变，请刷新后再确认，避免覆盖其他医护的更新")
    interval = int(plan.get("interval_days") or protocol.followup.default_interval_days)
    if not 1 <= interval <= 365:
        raise FlowError("随访间隔需为 1–365 天")
    message = plan.get("patient_message") or ""
    if not message.strip():
        raise FlowError("随访计划必须包含医生确认后发给患者的说明（系统可以帮你改写措辞，但内容由医生决定、由医生发送）")
    draft_meta: dict = {}
    if plan.get("draft_id"):
        # 由"改写"起草的说明：发送前复查要点以外的新内容（第三轮评审 T5）；模型改写过的自动加 AI 标注
        log = session.get(AuditLog, plan["draft_id"])
        if not log or log.action != "followup.draft_generated" or log.target_id != enc.id:
            raise FlowError("找不到这份说明的草稿，请重新点「改写」后再发送")
        notes = log.detail.get("notes", "")
        ai_assisted = bool(log.detail.get("ai_assisted"))
        if ai_assisted and AI_LABEL not in message:
            message = message.rstrip() + "\n" + AI_LABEL
        remaining = remaining_new_terms(protocol, notes, message, interval)
        reason = (plan.get("override_reason") or "").strip()
        if remaining and not reason:
            raise FlowError(f"说明里有你的要点里没有的内容（{describe(remaining)}）。请删掉；如果确实要保留，写一句理由后再发送。")
        draft_meta = {"draft_id": log.id, "rewrite_mode": log.detail.get("mode"), "ai_assisted": ai_assisted}
        if remaining:
            draft_meta.update(override_terms=[t["term"] for t in remaining], override_reason=reason)
            audit(session, actor, "followup.rewrite_override", "encounter", enc.id, {"terms": remaining, "reason": reason})
    content = {"interval_days": interval, "watch_facts": plan.get("watch_facts") or protocol.followup.change_facts,
                         "patient_message": message, "set_by": actor, "set_at": iso(now()),
                         **({"drafted_with": plan["drafted_with"]} if plan.get("drafted_with") else {}), **draft_meta}
    from ..course.teachback import save_version
    version = save_version(session, enc, protocol, actor, content, plan.get("understanding_points"))
    final = {**version.content, "version_id": version.id, "version": version.version, "content_sha256": version.content_sha256}
    expected = plan.get("expected_plan_version_id")
    guard = (Encounter.followup_plan["version_id"].as_string() == expected) if expected else or_(Encounter.followup_plan.is_(None), Encounter.followup_plan["version_id"].as_string().is_(None))
    changed = session.exec(update(Encounter).where(Encounter.id == enc.id, Encounter.status == EncounterStatus.DOCTOR_CONFIRMED, guard)
                           .values(followup_plan=final, updated_at=now()))
    if changed.rowcount != 1:
        session.rollback()
        raise FlowError("计划已被其他操作更新，请刷新后重试")
    from ..models import NotificationStatus
    n = Notification(encounter_id=enc.id, content=message, plan_version_id=version.id,
                     history=[{"to": NotificationStatus.QUEUED, "by": f"doctor:{actor}", "at": iso(now())}])
    task = Task(encounter_id=enc.id, kind="followup_check", title=f"随访 D+{interval}：检查患者是否提交、是否看到说明",
                assignee_role="frontdesk", due_at=now() + timedelta(days=interval),
                detail={"plan_version_id": version.id},
                history=[{"to": TaskStatus.UNVIEWED, "by": "system", "at": iso(now()), "note": "系统创建"}])
    session.add(n); session.add(task)
    session.add(AuditLog(actor=actor, action="followup.plan_set", target_type="encounter", target_id=enc.id, detail=final))
    session.commit(); session.refresh(enc); session.refresh(n)
    return {"followup_plan": enc.followup_plan, "notification_id": n.id}


def followup_draft(session: Session, enc: Encounter, actor: str, notes: str, interval_days: Optional[int] = None) -> dict:
    """把医生写的要点整理成患者看得懂的说明，供医生核对后发送（不自动发送）。

    默认（glossary）：按协议里医生审定的术语对照表分条、在术语后加一句大白话，医生的字一个不改，不调用模型。
    llm：由模型改写措辞。改写里出现要点以外的医学内容（药名、剂量频次与时间、检查、诊断式说法、处置与活动建议）
    会被列出，发送时必须删掉或写理由；模型改写过的说明自动加 AI 标注。复诊时间与紧急提示由系统按协议附上，不交给模型写。"""
    import re as _re

    from ..llm import get_provider
    from ..verification.rewrite_guard import AI_LABEL, describe, glossary_explain
    protocol = for_encounter(session, enc)
    if enc.status != EncounterStatus.DOCTOR_CONFIRMED:
        raise FlowError("只有医生确认后的就诊才能起草给患者的说明")
    notes = (notes or "").strip()
    if not notes:
        raise FlowError("请先写下你要告诉患者的要点（可以简写），系统只负责整理成通俗说法")
    interval = int(interval_days or protocol.followup.default_interval_days)
    mode = _rewrite_mode()
    if mode == "llm":
        provider = get_provider()
        body = provider.patient_explain(notes, protocol).strip()
        used = getattr(provider, "last_used", provider.name)
    else:
        body = glossary_explain(notes, protocol.followup.plain_language)[0]
        used = "glossary"
    ai_assisted = mode == "llm" and not str(used).startswith("mock")
    terms = remaining_new_terms(protocol, notes, body, interval)
    warnings = [f"改写里出现了你的要点里没有的内容（{describe(terms)}）。请删掉；如果确实要保留，发送时写一句理由。"] if terms else []
    times = _re.findall(r"(?:\d+|[一二两三四五六七八九十半]+)\s*(?:天|日|周|星期|个月|月)", notes)
    if interval_days is None and times:
        warnings.append(f"你的要点里写了时间（{'、'.join(times)}），但随访间隔还是默认的 {interval} 天；"
                        "请先填好随访间隔再改写，两处要一致。")
    greet, back, emerg = _draft_frame(protocol, interval)
    draft = "\n".join([greet, body, back, emerg] + ([AI_LABEL] if ai_assisted else []))
    log = audit(session, actor, "followup.draft_generated", "encounter", enc.id,
                {"provider": used, "mode": mode, "ai_assisted": ai_assisted, "notes": notes, "body": body,
                 "new_terms": terms, "warnings": warnings, "interval_days": interval})
    return {"draft": draft, "provider": used, "mode": mode, "ai_assisted": ai_assisted, "warnings": warnings,
            "new_terms": terms, "draft_id": log.id, "interval_days": interval}


def change_card(session: Session, enc: Encounter) -> dict | None:
    if not enc.parent_encounter_id:
        return None
    protocol = for_encounter(session, enc)
    parent = get_encounter(session, enc.parent_encounter_id)
    pf, cf = current_facts(session, parent.id), current_facts(session, enc.id)
    fi = protocol.fact_index
    changed, new, unconfirmed, same = [], [], [], []
    for k in protocol.followup.change_facts:
        p, c, d = pf[k], cf[k], fi[k]
        before, after = display_value(d, p.status, p.value), display_value(d, c.status, c.value)
        item = {"key": k, "label": d.label, "before": before, "after": after, "before_status": p.status, "after_status": c.status,
                "evidence": c.evidence}
        if c.status in FactStatus.UNKNOWN:
            unconfirmed.append(item)
        elif p.status in FactStatus.UNKNOWN and c.status in (FactStatus.PRESENT, FactStatus.UNCERTAIN):
            new.append(item)
        elif (p.status, p.value) != (c.status, c.value):
            changed.append(item)
        else:
            same.append(item)
    for k in ("fu_change_overall", "fu_new_symptom", "fu_new_symptom_desc", "fu_plan_understood", "fu_plan_adherence"):
        if k in cf:
            c, d = cf[k], fi[k]
            new.append({"key": k, "label": d.label, "before": "—", "after": display_value(d, c.status, c.value),
                        "before_status": None, "after_status": c.status, "evidence": c.evidence}) if c.status not in FactStatus.UNKNOWN else \
                unconfirmed.append({"key": k, "label": d.label, "before": "—", "after": display_value(d, c.status, c.value),
                                    "before_status": None, "after_status": c.status, "evidence": c.evidence})
    alerts = session.exec(select(Alert).where(Alert.encounter_id == enc.id)).all()
    plan_notifications = session.exec(select(Notification).where(Notification.encounter_id == parent.id)).all()
    return {"parent_encounter_id": parent.id, "parent_confirmed_at": iso(parent.doctor_confirmed_at),
            "changed": changed, "new": new, "unconfirmed": unconfirmed, "unchanged": same,
            "triggered": [_alert_to_dict(a) for a in alerts],
            "plan_delivery": [notification_to_dict(n) for n in plan_notifications],
            "followup_plan": parent.followup_plan}


def _assert_editable(enc: Encounter) -> None:
    if enc.status not in (EncounterStatus.DRAFT, EncounterStatus.QUESTIONING, EncounterStatus.AWAITING_PATIENT_CONFIRMATION):
        raise FlowError(f"当前状态 {enc.status} 不能再修改患者输入")


def patient_state(session: Session, enc: Encounter) -> dict:
    from ..course.goals import view as functional_goals_view
    protocol = for_encounter(session, enc)
    patient = session.get(Patient, enc.patient_id)
    facts = current_facts(session, enc.id)
    bm = protocol.body_map
    deliver_queued(session, enc.id)
    notifs = session.exec(select(Notification).where(Notification.encounter_id == enc.id)).all()
    parent_notifs = []
    if enc.parent_encounter_id:
        deliver_queued(session, enc.parent_encounter_id)
        parent_notifs = session.exec(select(Notification).where(Notification.encounter_id == enc.parent_encounter_id)).all()
    return {
        "id": enc.id, "patient_code": patient.display_code if patient else None, "kind": enc.kind, "status": enc.status,
        "clinic_timezone": settings.clinic_tz,
        "protocol": {"id": protocol.protocol_id, "title": protocol.title, "service_hours": protocol.scope.service_hours,
                     "service_notice": protocol.scope.service_notice, "emergency_notice": protocol.scope.emergency_notice,
                     "contact_label": protocol.scope.contact_label, "contact_phone": protocol.scope.contact_phone,
                     "emergency_phone": protocol.scope.emergency_phone, "body_map_view": protocol.body_map.initial_view},
        **stop_info(session, enc),
        "question_count": enc.question_count, "max_questions": protocol.max_questions,
        "question_metrics": question_metrics(session, enc.id),
        "functional_goals_enabled": protocol.course.functional_goals_enabled,
        "functional_goals": functional_goals_view(session, enc),
        "body_map": {"primary": facts[bm.regions_fact_key].value if facts[bm.regions_fact_key].status == FactStatus.PRESENT else [],
                     "radiation": facts[bm.radiation_fact_key].value if bm.radiation_fact_key and facts[bm.radiation_fact_key].status == FactStatus.PRESENT else []},
        "notices": active_notices(session, enc),
        "notifications": [notification_to_dict(n) for n in list(notifs) + list(parent_notifs)],
        "parent_encounter_id": enc.parent_encounter_id,
        "respondent": enc.respondent,
        # 疗程安全网给患者端的静态信息（内容来自模拟临床负责人，待医生审定）
        "course": {"time_budget": protocol.course.time_budget.get("checkin" if enc.kind == EncounterKind.FOLLOW_UP else "pre_visit"),
                   "safety_card": protocol.course.safety_card.model_dump() if protocol.course.safety_card else None,
                   "respondent_options": [o.model_dump() for o in protocol.course.respondent.options] if protocol.course.respondent else [],
                   "service_hours": describe_windows(protocol), "in_service_hours": in_service_hours(protocol),
                   "simulated": protocol.course.simulated},
    }


# ------------------------------------------------------------------ 可用性测试埋点
def question_metrics(session: Session, encounter_id: str) -> dict:
    rows = session.exec(select(AskedQuestion).where(AskedQuestion.encounter_id == encounter_id)).all()
    def decisions(q):
        return len(q.options) if q.kind in {"verification", "red_flag_grid"} else 1
    return {"screens_shown": len(rows), "items_shown": sum(decisions(q) for q in rows),
            "items_answered": sum(decisions(q) for q in rows if q.answer_status in {"answered", "unknown", "skipped"}),
            "note": "不含适用范围、身体图、自由描述与最终确认；一屏每一行单独计数"}


ALLOWED_EVENT_TYPES = {"page_view", "step_submit", "answer", "verification", "confirm_edit", "confirm_submit",
                       "urgent_screen", "urgent_action", "notice_toggle", "notification_event", "session_start", "back",
                       "red_flag_grid", "body_undo", "voice_hint", "kiosk_reset", "safety_card"}


def record_event(session: Session, enc: Encounter, type_: str, payload: dict | None, client_ts: str | None) -> dict:
    if type_ not in ALLOWED_EVENT_TYPES:
        raise FlowError(f"未知事件类型：{type_}")
    payload = {k: v for k, v in (payload or {}).items() if isinstance(v, (str, int, float, bool)) or v is None}
    ev = UsageEvent(encounter_id=enc.id, type=type_, payload=payload, client_ts=client_ts)
    session.add(ev)
    session.commit()
    return {"ok": True, "id": ev.id}
