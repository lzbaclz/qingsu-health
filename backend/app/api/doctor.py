from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..protocol.loader import for_encounter
from ..security import Principal, require_staff, require_clinical, require_doctor, staff_encounter
from ..course.tasks import (closure_spec, complete_with_closure, escalate_to_doctor,
                            record_contact_attempt, sweep_no_response)
from ..models import Encounter, Task, TaskStatus
from ..services import encounter as svc
from ..tasks.service import TransitionError, task_to_dict, transition_task
from . import schemas as S

router = APIRouter(prefix="/api/doctor", tags=["doctor"])


def _enc(session: Session, encounter_id: str, user: Principal) -> Encounter:
    return staff_encounter(session, encounter_id, user)


def _run(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except svc.FlowError as e:
        raise HTTPException(400, str(e))
    except TransitionError as e:
        raise HTTPException(409, str(e))


@router.get("/encounters")
def list_encounters(status: Optional[str] = None, user: Principal = Depends(require_clinical), session: Session = Depends(get_session)):
    sweep_no_response(session)  # 到期未签到 → 电话回访任务（幂等）
    q = select(Encounter).where(Encounter.clinic_id == user.clinic_id).order_by(Encounter.updated_at.desc())
    if status:
        q = q.where(Encounter.status == status)
    rows = [svc.encounter_brief(session, e) for e in session.exec(q).all()]
    # 按紧急程度排：紧急 > 当天联系 > 常规 > 无红旗；同一级里等医生看的在前，其余按最近更新（sort 是稳定排序）
    waiting = {"ready_for_doctor", "under_review"}
    rows.sort(key=lambda r: (r["triage_rank"], 0 if r["status"] in waiting else 1))
    return rows


@router.get("/encounters/{encounter_id}")
def get_encounter(encounter_id: str, actor: Optional[str] = Query(default=None), user: Principal = Depends(require_clinical), session: Session = Depends(get_session)):
    return svc.doctor_view(session, _enc(session, encounter_id, user), user.actor)


@router.post("/encounters/{encounter_id}/summary/edit")
def edit_summary(encounter_id: str, body: S.SummaryEditIn, user: Principal = Depends(require_doctor), session: Session = Depends(get_session)):
    return _run(svc.doctor_edit_summary, session, _enc(session, encounter_id, user), user.actor, body.edits, body.note)


@router.post("/encounters/{encounter_id}/facts/correct")
def correct_fact(encounter_id: str, body: S.FactCorrectionIn, user: Principal = Depends(require_doctor), session: Session = Depends(get_session)):
    return _run(svc.doctor_correct_fact, session, _enc(session, encounter_id, user), user.actor, body.key, body.status, body.value, body.note)


@router.post("/encounters/{encounter_id}/confirm")
def confirm(encounter_id: str, body: S.DoctorConfirmIn, user: Principal = Depends(require_doctor), session: Session = Depends(get_session)):
    return _run(svc.doctor_confirm, session, _enc(session, encounter_id, user), user.actor, body.override_reason)


@router.post("/encounters/{encounter_id}/followup-plan")
def followup_plan(encounter_id: str, body: S.FollowupPlanIn, user: Principal = Depends(require_doctor), session: Session = Depends(get_session)):
    return _run(svc.set_followup_plan, session, _enc(session, encounter_id, user), user.actor, body.model_dump())


@router.post("/encounters/{encounter_id}/followup-draft")
def followup_draft(encounter_id: str, body: S.FollowupDraftIn, user: Principal = Depends(require_doctor), session: Session = Depends(get_session)):
    """把医生要点改写成患者看得懂的说明（不发送）。医生核对、修改后再用 followup-plan 发送。"""
    return _run(svc.followup_draft, session, _enc(session, encounter_id, user), user.actor, body.notes, body.interval_days)


@router.get("/encounters/{encounter_id}/entries/{entry_id}/lexicon-replay")
def lexicon_replay(encounter_id: str, entry_id: str, user: Principal = Depends(require_clinical), session: Session = Depends(get_session)):
    """用离线词表重放同一句原话（只读），与模型结果对照。"""
    return _run(svc.lexicon_replay, session, _enc(session, encounter_id, user), entry_id)


@router.get("/encounters/{encounter_id}/verification")
def verification(encounter_id: str, user: Principal = Depends(require_clinical), session: Session = Depends(get_session)):
    from ..protocol import get_protocol
    from ..verification.checks import run_checks
    enc = _enc(session, encounter_id, user)
    r = run_checks(session, enc, for_encounter(session, enc), persist=False)
    return {"id": r.id, "passed": r.passed, "checks": r.checks}


@router.get("/tasks")
def list_tasks(status: Optional[str] = None, user: Principal = Depends(require_staff), session: Session = Depends(get_session)):
    sweep_no_response(session)
    q = select(Task).join(Encounter, Task.encounter_id == Encounter.id).where(Encounter.clinic_id == user.clinic_id).order_by(Task.created_at.desc())
    if user.role not in {"doctor", "nurse"}:
        q = q.where(Task.assignee_role == user.role)
    if status:
        q = q.where(Task.status == status)
    out = []
    for t in session.exec(q).all():
        d = task_to_dict(t)
        enc = session.get(Encounter, t.encounter_id)
        d["encounter"] = svc.encounter_brief(session, enc) if enc else None
        out.append(d)
    return out


@router.post("/tasks/{task_id}/transition")
def task_transition(task_id: str, body: S.TaskTransitionIn, user: Principal = Depends(require_staff), session: Session = Depends(get_session)):
    t = session.get(Task, task_id)
    if not t:
        raise HTTPException(404, "任务不存在")
    _enc(session, t.encounter_id, user)
    if user.role not in {"doctor", "nurse"} and t.assignee_role != user.role:
        raise HTTPException(403, "此任务不属于当前角色")
    if (body.closure or {}).get("advice") == "not_urgent_by_doctor" and user.role != "doctor":
        raise HTTPException(403, "医学复评结论需要医生记录")
    if body.to == TaskStatus.COMPLETED:
        if t.kind in {"event_review", "teachback_review"}:
            raise HTTPException(409, "请在对应的事件／复述卡完成核实，不能只点任务完成")
        # 红旗任务结案必须填处置记录（联系上没有、给了什么建议、谁处理）
        from ..protocol import get_protocol
        enc = session.get(Encounter, t.encounter_id)
        protocol = for_encounter(session, enc) if enc else None
        return task_to_dict(_run(complete_with_closure, session, protocol, t, user.actor, body.closure, body.note, user.role))
    if body.to == TaskStatus.ESCALATED:
        return task_to_dict(_run(escalate_to_doctor, session, t, user.actor, body.note))
    return task_to_dict(_run(transition_task, session, t, body.to, user.actor, body.note))


@router.post("/tasks/{task_id}/contact-attempt")
def contact_attempt(task_id: str, body: S.ContactAttemptIn, user: Principal = Depends(require_staff),
                    session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    _enc(session, task.encounter_id, user)
    if user.role not in {"doctor", "nurse"} and task.assignee_role != user.role:
        raise HTTPException(403, "此任务不属于当前角色")
    return task_to_dict(_run(record_contact_attempt, session, task, user.actor, body.result, body.note))


@router.get("/tasks/closure-spec")
def closure_form(protocol_id: Optional[str] = None, user: Principal = Depends(require_staff)):
    from ..config import settings
    from ..protocol import get_protocol
    return closure_spec(get_protocol(protocol_id or settings.default_protocol_id))


@router.get("/tasks/{task_id}/closure-spec")
def task_closure_form(task_id: str, user: Principal = Depends(require_staff), session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    enc = _enc(session, task.encounter_id, user)
    if user.role not in {"doctor", "nurse"} and task.assignee_role != user.role:
        raise HTTPException(403, "此任务不属于当前角色")
    spec = closure_spec(for_encounter(session, enc))
    return {**spec, "advice": {**spec["advice"], "options": [o for o in spec["advice"]["options"]
            if not o.get("allowed_roles") or user.role in o["allowed_roles"]]}}


@router.get("/handover")
def handover(user: Principal = Depends(require_staff), session: Session = Depends(get_session)):
    """早班交接单：没结案的红旗与回访、超时任务、恢复提醒，按截止时间排序。"""
    sweep_no_response(session)
    open_tasks = session.exec(select(Task).join(Encounter, Task.encounter_id == Encounter.id).where(Task.status != TaskStatus.COMPLETED, Encounter.clinic_id == user.clinic_id)).all()
    rows = []
    for t in open_tasks:
        if user.role not in {"doctor", "nurse"} and t.assignee_role != user.role:
            continue
        d = task_to_dict(t)
        if not (d["overdue"] or t.kind in ("red_flag_review", "after_hours_callback", "recovery_review", "no_response")):
            continue
        enc = session.get(Encounter, t.encounter_id)
        d["encounter"] = svc.encounter_brief(session, enc) if enc else None
        rows.append(d)
    sev = {"urgent": 0, "same_day": 1, "routine": 2}
    rows.sort(key=lambda d: (0 if d["overdue"] else 1, sev.get(d.get("severity") or "", 3), d.get("due_at") or "9999"))
    from ..course.hours import local_now
    return {"generated_at_local": local_now().strftime("%Y-%m-%d %H:%M"), "tasks": rows}


@router.post("/encounters/{encounter_id}/events/{event_id}/review")
def review_event(encounter_id: str, event_id: str, body: S.EventReviewIn,
                 user: Principal = Depends(require_doctor), session: Session = Depends(get_session)):
    from ..events.service import doctor_review
    enc = _enc(session, encounter_id, user)
    return _run(doctor_review, session, enc, for_encounter(session, enc), event_id,
                subject=body.subject, time_relation=body.time_relation, note=body.note, actor=user.actor)


@router.post("/encounters/{encounter_id}/teachbacks/{response_id}/review")
def review_teachback(encounter_id: str, response_id: str, body: S.TeachbackReviewIn,
                     user: Principal = Depends(require_clinical), session: Session = Depends(get_session)):
    from ..course.teachback import review_response
    enc = _enc(session, encounter_id, user)
    return _run(review_response, session, enc, response_id, user.actor, body.result, body.note)
