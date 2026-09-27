"""任务、通知、审计：状态由人推进，系统只创建。"""
from __future__ import annotations

from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import object_session

from ..models import AuditLog, Encounter, Notification, NotificationStatus, PlanVersion, Task, TaskDelivery, TaskStatus
from ..util import iso, now


class TransitionError(ValueError):
    pass


def audit(session: Session, actor: str, action: str, target_type: str, target_id: str, detail: dict | None = None) -> AuditLog:
    log = AuditLog(actor=actor, action=action, target_type=target_type, target_id=target_id, detail=detail or {})
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


def create_task(session: Session, encounter_id: str, kind: str, title: str, alert_id: str | None = None,
                dedupe_key: str | None = None) -> Task:
    if dedupe_key:
        existing = session.exec(select(Task).where(Task.dedupe_key == dedupe_key)).first()
        if existing:
            return existing
    t = Task(encounter_id=encounter_id, kind=kind, title=title, alert_id=alert_id,
             dedupe_key=dedupe_key,
             history=[{"to": TaskStatus.UNVIEWED, "by": "system", "at": iso(now()), "note": "系统创建"}])
    session.add(t)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if dedupe_key:
            existing = session.exec(select(Task).where(Task.dedupe_key == dedupe_key)).first()
            if existing:
                return existing
        raise
    session.refresh(t)
    return t


def transition_task(session: Session, task: Task, to: str, actor: str, note: str | None = None) -> Task:
    if to not in TaskStatus.TRANSITIONS.get(task.status, set()):
        raise TransitionError(f"任务不能从 {task.status} 变为 {to}")
    if not actor or actor == "system":
        raise TransitionError("任务状态只能由人推进")
    task.status = to
    task.assignee = task.assignee or actor
    task.history = task.history + [{"to": to, "by": actor, "at": iso(now()), "note": note}]
    task.updated_at = now()
    session.add(task)
    session.commit()
    session.refresh(task)
    audit(session, actor, f"task.{to}", "task", task.id, {"note": note})
    return task


def create_notification(session: Session, encounter_id: str, content: str, by: str, channel: str = "in_app") -> Notification:
    n = Notification(encounter_id=encounter_id, content=content, channel=channel,
                     history=[{"to": NotificationStatus.QUEUED, "by": by, "at": iso(now())}])
    session.add(n)
    session.commit()
    session.refresh(n)
    return n


def transition_notification(session: Session, n: Notification, to: str, by: str) -> Notification:
    if to not in NotificationStatus.TRANSITIONS.get(n.status, set()):
        raise TransitionError(f"通知不能从 {n.status} 变为 {to}")
    if to in (NotificationStatus.SEEN, NotificationStatus.ACKNOWLEDGED) and not by.startswith("patient"):
        raise TransitionError("已看到/已确认只能由患者端记录")
    n.status = to
    n.history = n.history + [{"to": to, "by": by, "at": iso(now())}]
    session.add(n)
    session.commit()
    session.refresh(n)
    return n


def deliver_queued(session: Session, encounter_id: str) -> list[Notification]:
    """患者取回页面时记录站内提供；不代表短信/微信送达或患者已看到。"""
    out = []
    for n in session.exec(select(Notification).where(Notification.encounter_id == encounter_id,
                                                     Notification.status == NotificationStatus.QUEUED)).all():
        out.append(transition_notification(session, n, NotificationStatus.SENT, "system:in_app_response"))
    return out


def task_to_dict(t: Task) -> dict:
    session = object_session(t)
    deliveries = session.execute(select(TaskDelivery).where(TaskDelivery.task_id == t.id)).scalars().all() if session else []
    return {"id": t.id, "encounter_id": t.encounter_id, "alert_id": t.alert_id, "kind": t.kind, "title": t.title,
            "deliveries": [{"state": d.state, "attempts": d.attempts, "event": d.event,
                            "delivered_at": iso(d.delivered_at)} for d in deliveries],
            "status": t.status, "assignee": t.assignee, "history": t.history,
            "allowed_transitions": sorted(TaskStatus.TRANSITIONS.get(t.status, set()) - ({TaskStatus.COMPLETED} if t.kind in {"event_review", "teachback_review"} else set())),
            "created_at": iso(t.created_at), "updated_at": iso(t.updated_at), **_course_extra(t)}


def _course_extra(t: Task) -> dict:
    from ..course.tasks import task_extra  # 避免循环导入
    return task_extra(t)


def notification_to_dict(n: Notification) -> dict:
    session = object_session(n)
    plan = session.get(PlanVersion, n.plan_version_id) if session and n.plan_version_id else None
    enc = session.get(Encounter, n.encounter_id) if session else None
    return {"id": n.id, "encounter_id": n.encounter_id, "channel": n.channel, "content": n.content, "status": n.status,
            "plan_version_id": n.plan_version_id, "plan_version": plan.version if plan else None,
            "is_current_plan": bool(plan and enc and (enc.followup_plan or {}).get("version_id") == plan.id),
            "understanding_points": plan.content.get("understanding_points", []) if plan else [],
            "teachback_enabled": bool(plan and plan.content.get("teachback_enabled")),
            "history": n.history, "created_at": iso(n.created_at)}
