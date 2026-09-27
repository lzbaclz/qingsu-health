"""任务派发、时限与结案（第 1 轮团队评审 · 医学 / 工业设计）：每件事有人接、几点前、怎么结案都有记录。

- 派给哪个角色、几点前处理，按协议 course.task_routing 与门诊服务时段计算；协议没写时不派、不设时限（v0.1）。
- 停诊时段触发的紧急 / 当天红旗：额外建一条"次日开门第一件：回访是否已就诊"。
- 红旗任务"已完成"前必须填处置记录：联系上没有、给了什么建议、谁处理；联系不上要至少两次尝试。
- 到期未签到（随访计划到期后仍没有新的签到）：建"电话回访"任务，只建一次。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from ..models import Encounter, Task, TaskStatus
from ..protocol.loader import for_encounter
from ..protocol.schema import Protocol
from ..tasks.service import TransitionError, audit, create_task
from ..util import iso, now
from .hours import end_of_today, in_service_hours, local_now, next_open, tz

ROLE_LABEL = {"frontdesk": "前台", "nurse": "护士", "therapist": "治疗师", "doctor": "医生"}
CLOSURE_KINDS = {"red_flag_review", "after_hours_callback"}

# 协议没写结案表单时的保守默认（与模拟临床稿同义）
DEFAULT_CLOSURE = {
    "reached": {"options": [{"value": "reached", "label": "已联系上患者或家属"},
                            {"value": "unreached", "label": "没联系上", "unreached": True}],
                "min_attempts_if_unreached": 2},
    "advice": {"options": [{"value": "go_ed_now", "label": "请立即去急诊 / 已帮忙叫 120"},
                           {"value": "come_today", "label": "请今天来门诊"},
                           {"value": "already_seen", "label": "患者已在急诊或医院就诊"},
                           {"value": "not_urgent_by_doctor", "label": "医生判断无需紧急处理", "requires_reason": True}]},
}


def _due(protocol: Protocol, route_key: str, at: datetime) -> tuple[str | None, datetime | None, str | None]:
    """返回 (负责角色, 截止时间, 时限说明)。"""
    tr = protocol.course.task_routing.get(route_key)
    if tr is None:
        return None, None, None
    open_now = in_service_hours(protocol, at)
    if route_key == "urgent":
        if open_now is not False:
            m = tr.due_minutes_in_hours or 30
            return tr.assignee_role, at + timedelta(minutes=m), f"收到后 {m} 分钟内"
        nxt = next_open(protocol, at)
        return tr.assignee_role, (nxt + timedelta(minutes=30)) if nxt else None, "下一个开诊时段开门后 30 分钟内"
    if route_key == "same_day":
        if open_now is not False:
            eod = end_of_today(protocol, at)
            due = at + timedelta(minutes=tr.due_minutes_in_hours or 120)
            return tr.assignee_role, min(eod, due) if eod else due, "2 小时内或本时段停诊前（取较早）"
        nxt = next_open(protocol, at)
        return tr.assignee_role, (nxt + timedelta(hours=2)) if nxt else None, "下一个开诊日上午"
    if tr.due_days:
        return tr.assignee_role, at + timedelta(days=tr.due_days), f"{tr.due_days} 天内"
    if route_key == "recovery" or tr.due == "before_next_session":
        days = getattr(tr, "fallback_due_days", None) or 2
        return tr.assignee_role, at + timedelta(days=days), f"下次治疗前；未约时间时 {days} 天内"
    return tr.assignee_role, None, None


def create_routed_task(session: Session, protocol: Protocol, encounter_id: str, kind: str, title: str, *,
                       severity: str | None = None, route_key: str | None = None, alert_id: str | None = None,
                       assignee_role: str | None = None, due_at: datetime | None = None, detail: dict | None = None) -> Task:
    dedupe = (detail or {}).get("dedupe_key")
    if dedupe:
        existing = session.exec(select(Task).where(Task.dedupe_key == dedupe)).first()
        if existing:
            return existing
    t = create_task(session, encounter_id, kind, title, alert_id=alert_id, dedupe_key=dedupe)
    role, due, due_label = _due(protocol, route_key or severity or "routine", now())
    t.assignee_role = assignee_role or role
    t.due_at = due_at or due
    t.severity = severity
    t.detail = {**(detail or {}), **({"due_label": due_label} if due_label and not due_at else {})}
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def after_hours_callback(session: Session, protocol: Protocol, encounter_id: str, alert) -> Task | None:
    """停诊时段触发的紧急 / 当天红旗：患者端已被引导去急诊；门诊下一个开诊时段第一件事回访结果。"""
    if alert.severity not in ("urgent", "same_day") or in_service_hours(protocol) is not False:
        return None
    spec = protocol.course.callback_task
    nxt = next_open(protocol)
    due = nxt + timedelta(minutes=spec.due_minutes_after_open) if nxt else None
    return create_routed_task(session, protocol, encounter_id, "after_hours_callback", spec.title, severity=alert.severity,
                              alert_id=alert.id, assignee_role=spec.assignee_role, due_at=due,
                              detail={"rule_label": alert.label, "triggered_local": local_now().strftime("%m-%d %H:%M"),
                                      "due_label": "下一个开诊时段开门后 %d 分钟内" % spec.due_minutes_after_open})


def closure_spec(protocol: Protocol) -> dict:
    return protocol.course.closure or DEFAULT_CLOSURE


def validate_closure(protocol: Protocol, closure: dict | None, role: str = "doctor") -> dict:
    """红旗任务结案的处置记录。不合格抛 TransitionError（界面显示原因）。"""
    if not isinstance(closure, dict):
        raise TransitionError("红旗任务结案前，请填写处置记录：联系上没有、给了什么建议")
    spec = closure_spec(protocol)
    r_opts = {o["value"]: o for o in (spec.get("reached") or {}).get("options", [])}
    a_opts = {o["value"]: o for o in (spec.get("advice") or {}).get("options", [])}
    reached = closure.get("reached")
    if reached not in r_opts:
        raise TransitionError("请选择是否联系上患者")
    attempts = int(closure.get("attempts") or 1)
    if r_opts[reached].get("unreached"):
        raise TransitionError("没联系上不能记为完成。请记录联系尝试并升级给医生，保留待处理任务")
    advice = closure.get("advice")
    if not r_opts[reached].get("unreached"):
        if advice not in a_opts:
            raise TransitionError("请选择给患者的建议")
        if a_opts[advice].get("requires_reason") and not str(closure.get("reason") or "").strip():
            raise TransitionError("选择这一项需要写明理由")
        allowed = a_opts[advice].get("allowed_roles")
        if allowed and role not in allowed:
            raise TransitionError("这一处置结论需要协议指定的医护角色")
    if not str(closure.get("note") or "").strip():
        raise TransitionError("请写明联系结果与后续安排")
    out = {"reached": reached, "reached_label": r_opts[reached].get("label"), "attempts": attempts,
           "advice": advice if advice in a_opts else None, "advice_label": a_opts.get(advice, {}).get("label"),
           "reason": (closure.get("reason") or "").strip() or None, "note": (closure.get("note") or "").strip() or None,
           "outcome_followup": closure.get("outcome_followup")}
    return out


def complete_with_closure(session: Session, protocol: Protocol, task: Task, actor: str, closure: dict | None, note: str | None,
                          role: str = "doctor") -> Task:
    from ..tasks.service import transition_task

    if TaskStatus.COMPLETED not in TaskStatus.TRANSITIONS.get(task.status, set()):
        raise TransitionError("当前任务状态不能结案")
    attempts = list((task.detail or {}).get("contact_attempts") or [])
    payload = {**(closure or {}), "note": (closure or {}).get("note") or note, "attempts": len(attempts)}
    rec = validate_closure(protocol, payload, role) if task.kind in CLOSURE_KINDS else (closure or None)
    if task.kind in CLOSURE_KINDS and not any(a.get("result") in {"reached", "in_person"} for a in attempts):
        raise TransitionError("结案前请记录一次已联系上或当面处理的结果；系统不把状态按钮当作联系证据")
    if rec is not None:
        task.closure = {**rec, "by": actor, "at": iso(now())}
        session.add(task)
        session.commit()
    t = transition_task(session, task, TaskStatus.COMPLETED, actor, note)
    if rec is not None:
        audit(session, actor, "task.closure", "task", task.id, task.closure or {})
    return t


def record_contact_attempt(session: Session, task: Task, actor: str, result: str, note: str) -> Task:
    if task.status == TaskStatus.COMPLETED:
        raise TransitionError("已结案任务不能补写联系记录")
    if result not in {"reached", "unreached", "in_person"} or not note.strip():
        raise TransitionError("请选择联系结果并写明说明")
    attempts = list((task.detail or {}).get("contact_attempts") or [])
    attempts.append({"at": iso(now()), "by": actor, "result": result, "note": note.strip(), "source": "staff_report"})
    task.detail = {**(task.detail or {}), "contact_attempts": attempts}
    task.updated_at = now()
    session.add(task)
    session.commit()
    audit(session, actor, "task.contact_recorded", "task", task.id, attempts[-1])
    return task


def escalate_to_doctor(session: Session, task: Task, actor: str, reason: str | None) -> Task:
    from ..tasks.service import transition_task
    if not (reason or "").strip():
        raise TransitionError("升级时请写明原因和待接手事项")
    task = transition_task(session, task, TaskStatus.ESCALATED, actor, reason)
    task.assignee_role, task.assignee = "doctor", None
    task.detail = {**(task.detail or {}), "escalated_at": iso(now()), "escalation_reason": reason}
    session.add(task)
    session.commit()
    return task


def is_overdue(t: Task) -> bool:
    if t.due_at is None or t.status == TaskStatus.COMPLETED:
        return False
    due = t.due_at if t.due_at.tzinfo else t.due_at.replace(tzinfo=timezone.utc)
    return due < now()


def task_extra(t: Task) -> dict[str, Any]:
    """任务卡上的"谁 · 几点前"。"""
    due_local = None
    if t.due_at is not None:
        due = t.due_at if t.due_at.tzinfo else t.due_at.replace(tzinfo=timezone.utc)
        due_local = due.astimezone(tz()).strftime("%m-%d %H:%M")
    return {"assignee_role": t.assignee_role, "assignee_role_label": ROLE_LABEL.get(t.assignee_role or "", None),
            "severity": t.severity, "due_at": iso(t.due_at), "due_local": due_local, "overdue": is_overdue(t),
            "detail": t.detail, "closure": t.closure, "needs_closure": t.kind in CLOSURE_KINDS}


def sweep_no_response(session: Session) -> list[Task]:
    """到期未签到：医生设了随访计划，到期后超过 hours_after_due 仍没有新的签到 → 建一次"电话回访"任务。
    后台定时运行；页面读取也可补偿检查。按每份随访计划幂等。"""
    from ..protocol import get_protocol

    made = []
    encs = session.exec(select(Encounter).where(Encounter.followup_plan.is_not(None))).all()  # type: ignore[union-attr]
    for e in encs:
        plan = e.followup_plan or {}
        try:
            protocol = for_encounter(session, e)
        except Exception:  # noqa: BLE001
            continue
        rule = protocol.course.no_response
        if rule is None or not plan.get("set_at"):
            continue
        set_at = datetime.fromisoformat(str(plan["set_at"]).replace("Z", "+00:00"))
        due = set_at + timedelta(days=int(plan.get("interval_days") or protocol.followup.default_interval_days))
        if now() < due + timedelta(hours=rule.hours_after_due):
            continue
        kids = session.exec(select(Encounter).where(Encounter.parent_encounter_id == e.id)).all()
        if any(k.patient_confirmed_at is not None and (not plan.get("version_id") or k.parent_plan_version_id == plan["version_id"]) and
               (k.patient_confirmed_at if k.patient_confirmed_at.tzinfo else k.patient_confirmed_at.replace(tzinfo=timezone.utc)) >= set_at
               for k in kids):
            continue
        key = f"no-response:{e.id}:{plan.get('version_id') or plan['set_at']}"
        if session.exec(select(Task).where(Task.dedupe_key == key)).first():
            continue
        made.append(create_routed_task(session, protocol, e.id, "no_response", rule.title, severity="routine",
                                       route_key="routine", assignee_role=rule.assignee_role,
                                       detail={"due_was": iso(due), "hours_after_due": rule.hours_after_due, "dedupe_key": key}))
    return made
