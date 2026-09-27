from __future__ import annotations

from datetime import timedelta
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..models import LoginThrottle, PatientInvite, StaffAccount
from ..security import (Principal, aware, check_password, digest, hash_password, issue_session,
                        protocol_for_use, real_now, require_clinical, require_staff, revoke_session,
                        staff_encounter)
from ..config import settings
from ..services import encounter as svc
from ..tasks.service import audit

router = APIRouter(prefix="/api/auth", tags=["access"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class InviteIn(BaseModel):
    patient_code: str | None = Field(default=None, max_length=80)
    protocol_id: str | None = None
    parent_encounter_id: str | None = None


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)


def public_user(user: Principal) -> dict:
    return {"id": user.id, "display_name": user.display_name, "clinic_id": user.clinic_id,
            "role": user.role, "actor": user.actor}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, session: Session = Depends(get_session)):
    username = body.username.strip()
    # 每账号和来源分别限流，避免轮换用户名绕过单个客户端限制。
    keys = [digest("user:" + username), digest("ip:" + (request.client.host if request.client else "unknown"))]
    throttles = []
    for key in keys:
        t = session.get(LoginThrottle, key)
        if t and real_now() - aware(t.window_started) >= timedelta(minutes=10):
            t.failures, t.window_started = 0, real_now()
        t = t or LoginThrottle(id=key, window_started=real_now())
        if t.failures >= 10:
            raise HTTPException(429, "登录尝试过多，请十分钟后再试")
        throttles.append(t)
    account = session.exec(select(StaffAccount).where(StaffAccount.username == username)).first()
    # 不存在的账号也进行同等成本的计算，不返回账号存在信息。
    dummy = "scrypt-p5$" + "00" * 16 + "$" + "00" * 64
    valid = check_password(body.password, account.password_hash if account else dummy)
    if not account or account.disabled or not valid:
        for t in throttles:
            t.failures += 1
            session.add(t)
        session.commit()
        raise HTTPException(401, "账号或口令不正确")
    throttles[0].failures = 0
    if not account.password_hash.startswith("scrypt-p5$"):
        account.password_hash = hash_password(body.password)
        session.add(account)
    for t in throttles:
        session.add(t)
    revoke_session(session, request, response, "staff")
    issue_session(session, response, "staff", account.id, account.clinic_id)
    audit(session, f"staff:{account.id}", "auth.login", "staff", account.id)
    return public_user(Principal(account.id, account.clinic_id, account.role, account.display_name))


@router.get("/me")
def me(user: Principal = Depends(require_staff)):
    return public_user(user)


@router.post("/logout")
def logout(request: Request, response: Response, session: Session = Depends(get_session)):
    revoke_session(session, request, response, "staff")
    return {"ok": True}


@router.post("/patient/logout")
def patient_logout(request: Request, response: Response, session: Session = Depends(get_session)):
    revoke_session(session, request, response, "patient")
    return {"ok": True}


@router.post("/invites")
def invite(body: InviteIn, user: Principal = Depends(require_clinical), session: Session = Depends(get_session)):
    parent = staff_encounter(session, body.parent_encounter_id, user) if body.parent_encounter_id else None
    p = protocol_for_use(parent.protocol_id if parent else (body.protocol_id or settings.default_protocol_id))
    if parent:
        from ..models import EncounterStatus, Patient
        if parent.status not in {EncounterStatus.DOCTOR_CONFIRMED, EncounterStatus.CLOSED}:
            raise HTTPException(409, "请先由医生确认，再发随访邀请")
        patient = session.get(Patient, parent.patient_id)
    else:
        patient = svc.get_or_create_patient(session, body.patient_code, clinic_id=user.clinic_id)
    token = secrets.token_urlsafe(32)
    expires = real_now() + timedelta(hours=max(1, min(settings.invite_hours, 168)))
    session.add(PatientInvite(id=digest(token), patient_id=patient.id, clinic_id=user.clinic_id,
                             protocol_id=p.protocol_id, parent_encounter_id=parent.id if parent else None,
                             expires_at=expires, created_by=user.actor))
    session.commit()
    audit(session, user.actor, "patient.invite_created", "patient", patient.id,
          {"expires_at": expires.isoformat(), "parent_encounter_id": parent.id if parent else None})
    return {"token": token, "path": "/p#invite=" + token, "expires_at": expires.isoformat(),
            "patient_code": patient.display_code, "protocol_id": p.protocol_id}


def active_invite(session: Session, token: str) -> PatientInvite:
    i = session.get(PatientInvite, digest(token))
    if not i or i.consumed_at is not None or aware(i.expires_at) <= real_now():
        raise HTTPException(401, "邀请无效、已使用或已过期，请联系门诊获取新邀请")
    return i


@router.post("/invites/inspect")
def inspect_invite(body: TokenIn, session: Session = Depends(get_session)):
    i = active_invite(session, body.token)
    from ..models import Patient
    patient = session.get(Patient, i.patient_id)
    return {"protocol_id": i.protocol_id, "patient_code": patient.display_code,
            "parent_encounter_id": i.parent_encounter_id, "kind": "follow_up" if i.parent_encounter_id else "pre_visit"}
