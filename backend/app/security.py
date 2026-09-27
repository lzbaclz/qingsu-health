"""带期限的服务端会话、角色与机构访问控制。医疗资质仍由实际机构核验。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets

from fastapi import Depends, HTTPException, Request, Response
from sqlmodel import Session

from .config import settings
from .db import get_session
from .models import AccessSession, Encounter, StaffAccount

STAFF_COOKIE = "tiji_staff"
PATIENT_COOKIE = "tiji_patient"
ROLES = {"doctor", "nurse", "frontdesk", "admin"}


def real_now() -> datetime:
    # 演示时钟不得延长凭据或登录锁定期限。
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 256:
        raise ValueError("口令需为 12–256 个字符")
    salt = os.urandom(16)
    # OWASP 的 16 MiB 选项：N=2^14,r=8,p=5；适合本机门诊运行。
    value = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=5)
    return f"scrypt-p5${salt.hex()}${value.hex()}"


def check_password(password: str, encoded: str) -> bool:
    if len(password) > 256:
        return False
    try:
        algorithm, salt, wanted = encoded.split("$")
        if algorithm not in {"scrypt", "scrypt-p5"}:
            return False
        value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8,
                               p=5 if algorithm == "scrypt-p5" else 1)
        return hmac.compare_digest(value.hex(), wanted)
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class Principal:
    id: str
    clinic_id: str
    role: str
    display_name: str

    @property
    def actor(self) -> str:
        return f"staff:{self.id}"


def issue_session(session: Session, response: Response, kind: str, subject_id: str, clinic_id: str) -> None:
    token = secrets.token_urlsafe(32)
    ttl = max(1, min(settings.session_hours, 24)) * 3600
    cookie = STAFF_COOKIE if kind == "staff" else PATIENT_COOKIE
    session.add(AccessSession(id=digest(token), kind=kind, subject_id=subject_id,
                              clinic_id=clinic_id, expires_at=real_now() + timedelta(seconds=ttl)))
    session.commit()
    response.set_cookie(cookie, token, max_age=ttl, httponly=True, samesite="strict",
                        secure=settings.app_mode != "demo", path="/api")


def revoke_session(session: Session, request: Request, response: Response, kind: str) -> None:
    cookie = STAFF_COOKIE if kind == "staff" else PATIENT_COOKIE
    token = request.cookies.get(cookie)
    row = session.get(AccessSession, digest(token)) if token else None
    if row and row.kind == kind:
        row.revoked = True
        session.add(row)
        session.commit()
    response.delete_cookie(cookie, path="/api", httponly=True, samesite="strict",
                           secure=settings.app_mode != "demo")


def access_session(session: Session, request: Request, kind: str) -> AccessSession:
    token = request.cookies.get(STAFF_COOKIE if kind == "staff" else PATIENT_COOKIE)
    row = session.get(AccessSession, digest(token)) if token else None
    if not row or row.kind != kind or row.revoked or aware(row.expires_at) <= real_now():
        raise HTTPException(401, "登录或患者访问已失效，请重新登录或联系门诊获取邀请")
    return row


def require_staff(request: Request, session: Session = Depends(get_session)) -> Principal:
    access = access_session(session, request, "staff")
    user = session.get(StaffAccount, access.subject_id)
    if not user or user.disabled or user.clinic_id != access.clinic_id:
        raise HTTPException(401, "账号不可用")
    return Principal(user.id, user.clinic_id, user.role, user.display_name)


def require_doctor(user: Principal = Depends(require_staff)) -> Principal:
    if user.role != "doctor":
        raise HTTPException(403, "此操作需要医生角色")
    return user


def require_clinical(user: Principal = Depends(require_staff)) -> Principal:
    if user.role not in {"doctor", "nurse"}:
        raise HTTPException(403, "此记录需要医生或护士角色")
    return user


def require_admin(user: Principal = Depends(require_staff)) -> Principal:
    if user.role != "admin":
        raise HTTPException(403, "此操作需要机构管理员")
    return user


def patient_encounter(session: Session, request: Request, encounter_id: str) -> Encounter:
    access = access_session(session, request, "patient")
    enc = session.get(Encounter, encounter_id)
    if not enc or enc.patient_id != access.subject_id or enc.clinic_id != access.clinic_id:
        raise HTTPException(404, "就诊记录不存在或无访问权限")
    return enc


def staff_encounter(session: Session, encounter_id: str, user: Principal) -> Encounter:
    enc = session.get(Encounter, encounter_id)
    if not enc or enc.clinic_id != user.clinic_id:
        raise HTTPException(404, "就诊记录不存在或无访问权限")
    return enc


def protocol_for_use(protocol_id: str):
    from .protocol import get_protocol
    try:
        p = get_protocol(protocol_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "协议不存在")
    return ensure_protocol_approved(p)


def ensure_protocol_approved(p):
    if settings.app_mode != "demo":
        lead = p.owners.get("clinical_lead") if isinstance(p.owners, dict) else getattr(p.owners, "clinical_lead", None)
        reviewer = p.owners.get("clinical_reviewer") if isinstance(p.owners, dict) else getattr(p.owners, "clinical_reviewer", None)
        if (p.status != "approved" or p.course.simulated or p.review_gaps() or not lead or not reviewer
                or p.review.get("decided_by") == "simulated_clinical_lead"
                or not p.review.get("real_doctor_decided")):
            raise HTTPException(409, "该协议尚未完成真实临床审核和独立复核，仅允许模拟演示")
    return p
