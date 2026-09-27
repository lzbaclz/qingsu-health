from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import update
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..models import Encounter, Notification, NotificationStatus, Patient, PatientInvite
from ..security import ensure_protocol_approved, issue_session, patient_encounter, protocol_for_use, real_now
from ..protocol.loader import for_encounter
from .auth import active_invite
from ..services import encounter as svc
from ..tasks.service import TransitionError, transition_notification
from . import schemas as S

router = APIRouter(prefix="/api/patient", tags=["patient"])


def _enc(session: Session, encounter_id: str, request: Request):
    return patient_encounter(session, request, encounter_id)


def _run(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except svc.FlowError as e:
        raise HTTPException(400, str(e))
    except TransitionError as e:
        raise HTTPException(409, str(e))


@router.post("/encounters")
def create_encounter(body: S.CreateEncounterIn, request: Request, response: Response, session: Session = Depends(get_session)):
    invite = active_invite(session, body.invite_token) if body.invite_token else None
    clinic_id = "clinic_demo"
    code, parent_id, kind = body.patient_code, body.parent_encounter_id, body.kind
    protocol_id = body.protocol_id or settings.default_protocol_id
    if invite:
        patient = session.get(Patient, invite.patient_id)
        code, clinic_id, protocol_id = patient.display_code, invite.clinic_id, invite.protocol_id
        parent_id, kind = invite.parent_encounter_id, "follow_up" if invite.parent_encounter_id else "pre_visit"
    elif kind == "follow_up":
        parent = _enc(session, parent_id or "", request)
        patient = session.get(Patient, parent.patient_id)
        code, clinic_id, protocol_id = patient.display_code, patient.clinic_id, parent.protocol_id
    elif settings.app_mode != "demo":
        raise HTTPException(401, "请使用门诊发给你的采集邀请")
    elif code and session.exec(select(Patient).where(Patient.display_code == code, Patient.clinic_id == clinic_id)).first():
        # 即使是演示，也不能仅凭可猜测编号领取已有患者的访问权。
        raise HTTPException(409, "该编号已有记录，请使用门诊邀请或一个新的模拟编号")
    if parent_id:
        # 邀请和后续请求也检查原疗程快照，而不是同名协议的最新文件。
        original = session.get(Encounter, parent_id)
        if not original or original.clinic_id != clinic_id:
            raise HTTPException(404, "原就诊不存在")
        ensure_protocol_approved(for_encounter(session, original))
    else:
        protocol_for_use(protocol_id)
    if invite:
        result = session.exec(update(PatientInvite).where(PatientInvite.id == invite.id,
                                                         PatientInvite.consumed_at.is_(None))
                              .values(consumed_at=real_now()))
        if result.rowcount != 1:
            raise HTTPException(409, "邀请已使用")
        session.commit()
    try:
        enc = _run(svc.create_encounter, session, patient_code=code, clinic_id=clinic_id,
                   allow_existing_patient=invite is not None or kind == "follow_up",
                   protocol_id=protocol_id, kind=kind, parent_encounter_id=parent_id,
                   eligibility=body.eligibility, require_eligibility=True, respondent=body.respondent,
                   respondent_relation=body.respondent_relation, proxy_consent=body.proxy_consent)
    except HTTPException:
        if invite:
            session.exec(update(PatientInvite).where(PatientInvite.id == invite.id).values(consumed_at=None))
            session.commit()
        raise
    issue_session(session, response, "patient", enc.patient_id, enc.clinic_id)
    return svc.patient_state(session, enc)


@router.get("/encounters/{encounter_id}")
def get_state(encounter_id: str, request: Request, session: Session = Depends(get_session)):
    return svc.patient_state(session, _enc(session, encounter_id, request))


@router.post("/encounters/{encounter_id}/body-map")
def body_map(encounter_id: str, body: S.BodyMapIn, request: Request, session: Session = Depends(get_session)):
    enc = _enc(session, encounter_id, request)
    return _run(svc.add_body_map, session, enc, [m.model_dump() for m in body.marks])


@router.post("/encounters/{encounter_id}/text")
def free_text(encounter_id: str, body: S.TextIn, request: Request, session: Session = Depends(get_session)):
    enc = _enc(session, encounter_id, request)
    return _run(svc.add_text, session, enc, body.text)


@router.get("/encounters/{encounter_id}/next-question")
def next_question(encounter_id: str, request: Request, session: Session = Depends(get_session)):
    enc = _enc(session, encounter_id, request)
    q = svc.get_next_question(session, enc)
    session.refresh(enc)
    return {"question": q, "status": enc.status, "question_count": enc.question_count,
            "question_metrics": svc.question_metrics(session, enc.id),
            "notices": svc.active_notices(session, enc), **svc.stop_info(session, enc)}


@router.post("/encounters/{encounter_id}/answer")
def answer(encounter_id: str, body: S.AnswerIn, request: Request, session: Session = Depends(get_session)):
    enc = _enc(session, encounter_id, request)
    res = _run(svc.answer_question, session, enc, body.question_id, value=body.value, unknown=body.unknown, skipped=body.skipped)
    q = svc.get_next_question(session, enc)
    session.refresh(enc)
    return {**res, "next": q, "status": enc.status, "question_count": enc.question_count,
            "question_metrics": svc.question_metrics(session, enc.id), **svc.stop_info(session, enc)}


@router.get("/encounters/{encounter_id}/confirmation")
def confirmation(encounter_id: str, request: Request, session: Session = Depends(get_session)):
    return svc.confirmation_view(session, _enc(session, encounter_id, request))


@router.post("/encounters/{encounter_id}/confirm")
def confirm(encounter_id: str, body: S.ConfirmIn, request: Request, session: Session = Depends(get_session)):
    enc = _enc(session, encounter_id, request)
    return _run(svc.patient_confirm, session, enc, [c.model_dump() for c in body.corrections])


@router.post("/encounters/{encounter_id}/notifications/{notification_id}/event")
def notification_event(encounter_id: str, notification_id: str, body: S.NotificationEventIn, request: Request, session: Session = Depends(get_session)):
    _enc(session, encounter_id, request)
    n = session.get(Notification, notification_id)
    if not n or n.encounter_id != encounter_id:
        raise HTTPException(404, "通知不存在")
    to = NotificationStatus.SEEN if body.event == "seen" else NotificationStatus.ACKNOWLEDGED
    return _run(lambda: transition_notification(session, n, to, f"patient:{encounter_id}"))


@router.post("/encounters/{encounter_id}/events")
def usage_event(encounter_id: str, body: S.UsageEventIn, request: Request, session: Session = Depends(get_session)):
    enc = _enc(session, encounter_id, request)
    return _run(svc.record_event, session, enc, body.type, body.payload, body.client_ts)


@router.post("/encounters/{encounter_id}/symptom-events/{event_id}/correct")
def correct_event(encounter_id: str, event_id: str, body: S.EventCorrectionIn, request: Request,
                   session: Session = Depends(get_session)):
    from ..events.service import patient_correct_event
    enc = _enc(session, encounter_id, request)
    return _run(patient_correct_event, session, enc, for_encounter(session, enc), event_id, body.choice)


@router.post("/encounters/{encounter_id}/plans/{plan_version_id}/teachback")
def submit_teachback(encounter_id: str, plan_version_id: str, body: S.TeachbackIn, request: Request,
                     session: Session = Depends(get_session)):
    from ..course.teachback import submit_response
    enc = _enc(session, encounter_id, request)
    return _run(submit_response, session, enc, for_encounter(session, enc), plan_version_id,
                body.response_text, body.execution_status, body.barrier_text, body.submission_key)


@router.post("/encounters/{encounter_id}/functional-goals")
def functional_goal(encounter_id: str, body: S.FunctionalGoalIn, request: Request, session: Session = Depends(get_session)):
    from ..course.goals import create_goal
    return _run(create_goal, session, _enc(session, encounter_id, request), **body.model_dump())


@router.post("/encounters/{encounter_id}/functional-goals/{goal_id}/observations")
def functional_observation(encounter_id: str, goal_id: str, body: S.FunctionalObservationIn, request: Request,
                           session: Session = Depends(get_session)):
    from ..course.goals import add_observation
    return _run(add_observation, session, _enc(session, encounter_id, request), goal_id, body.model_dump())
