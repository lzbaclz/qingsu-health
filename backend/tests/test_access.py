"""使用真实 cookie 与 API 验证身份边界，不覆写认证依赖。"""
from dataclasses import replace
from datetime import timedelta
import secrets

from fastapi.testclient import TestClient
from sqlmodel import select

from app.main import app
from app.models import AccessSession, AuditLog, PatientInvite, StaffAccount, TaskStatus
from app.security import PATIENT_COOKIE, digest, hash_password, real_now
from app.services import encounter as svc
from app.tasks.service import create_notification, create_task, deliver_queued

ELIG = {"adult": True, "not_pregnant": True, "no_major_trauma": True}
PASSWORD = "testing-private-passphrase"


def account(session, role="doctor", clinic="clinic_demo"):
    u = StaffAccount(username="test_" + secrets.token_hex(6), display_name="模拟医护", role=role,
                     clinic_id=clinic, password_hash=hash_password(PASSWORD))
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def login(c, u):
    r = c.post("/api/auth/login", json={"username": u.username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    assert "httponly" in r.headers["set-cookie"].lower()
    return r.json()


def patient(c):
    r = c.post("/api/patient/encounters", json={"eligibility": ELIG})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_no_authentication_no_clinical_access():
    with TestClient(app) as c:
        assert c.get("/api/doctor/encounters").status_code == 401
        assert c.get("/api/doctor/tasks").status_code == 401
        assert c.post("/api/llm/probe").status_code == 401


def test_patient_cookie_cannot_read_or_acknowledge_another_patient(session):
    with TestClient(app) as a, TestClient(app) as b:
        ea, eb = patient(a), patient(b)
        n = create_notification(session, ea, "模拟说明", "doctor:test")
        deliver_queued(session, ea)
        assert b.get(f"/api/patient/encounters/{ea}").status_code == 404
        for eid in (ea, eb):
            assert b.post(f"/api/patient/encounters/{eid}/notifications/{n.id}/event", json={"event": "seen"}).status_code == 404
        assert a.post(f"/api/patient/encounters/{ea}/notifications/{n.id}/event", json={"event": "seen"}).status_code == 200
        assert a.post(f"/api/patient/encounters/{ea}/notifications/{n.id}/event", json={"event": "acknowledged"}).status_code == 200


def test_clinic_isolation_and_server_actor(session):
    clinic_a, clinic_b = "isolation-a", "isolation-b"
    ua, ub = account(session, clinic=clinic_a), account(session, clinic=clinic_b)
    ea = svc.create_encounter(session, patient_code="shared", clinic_id=clinic_a, protocol_id="lbp_adult_v0.2")
    eb = svc.create_encounter(session, patient_code="shared", clinic_id=clinic_b, protocol_id="lbp_adult_v0.2")
    assert ea.patient_id != eb.patient_id
    t = create_task(session, ea.id, "review", "模拟任务")
    with TestClient(app) as c:
        me = login(c, ua)
        assert {r["id"] for r in c.get("/api/doctor/encounters").json()} == {ea.id}
        assert c.get(f"/api/doctor/encounters/{eb.id}").status_code == 404
        r = c.post(f"/api/doctor/tasks/{t.id}/transition", json={"actor": "forged_admin", "to": "viewed"})
        assert r.status_code == 200
        assert r.json()["history"][-1]["by"] == me["actor"]
        c.post("/api/auth/logout")
        assert c.get("/api/doctor/encounters").status_code == 401
        login(c, ub)
        assert c.post(f"/api/doctor/tasks/{t.id}/transition", json={"actor": "forged", "to": "completed"}).status_code == 404


def test_nurse_cannot_confirm_or_change_medical_plan(session):
    u = account(session, role="nurse")
    enc = svc.create_encounter(session, patient_code=None, protocol_id="lbp_adult_v0.2")
    with TestClient(app) as c:
        login(c, u)
        assert c.get(f"/api/doctor/encounters/{enc.id}").status_code == 200
        assert c.post(f"/api/doctor/encounters/{enc.id}/confirm", json={"actor": "doctor:forged"}).status_code == 403
        assert c.post(f"/api/doctor/encounters/{enc.id}/followup-plan", json={"actor": "doctor:forged", "patient_message": "模拟"}).status_code == 403


def test_invites_are_bound_single_use_and_expire(session):
    u = account(session, clinic="invite-clinic")
    with TestClient(app) as doctor, TestClient(app) as p:
        login(doctor, u)
        issue = doctor.post("/api/auth/invites", json={"patient_code": "INV-TEST"})
        assert issue.status_code == 200, issue.text
        token = issue.json()["token"]
        assert session.get(PatientInvite, digest(token))
        r = p.post("/api/patient/encounters", json={"invite_token": token, "patient_code": "forged", "eligibility": ELIG})
        assert r.status_code == 200, r.text
        assert r.json()["patient_code"] == "INV-TEST"
        assert p.post("/api/patient/encounters", json={"invite_token": token, "eligibility": ELIG}).status_code == 401
        expired = doctor.post("/api/auth/invites", json={}).json()["token"]
        inv = session.get(PatientInvite, digest(expired))
        inv.expires_at = real_now() - timedelta(seconds=1)
        session.add(inv)
        session.commit()
        assert p.post("/api/auth/invites/inspect", json={"token": expired}).status_code == 401


def test_patient_expiry_and_logout(session):
    with TestClient(app) as c:
        eid = patient(c)
        row = session.get(AccessSession, digest(c.cookies.get(PATIENT_COOKIE)))
        row.expires_at = real_now() - timedelta(seconds=1)
        session.add(row)
        session.commit()
        assert c.get(f"/api/patient/encounters/{eid}").status_code == 401
        eid = patient(c)
        assert c.post("/api/auth/patient/logout").status_code == 200
        assert c.get(f"/api/patient/encounters/{eid}").status_code == 401


def test_draft_protocol_never_creates_production_patient(session, monkeypatch):
    from app import security
    from app.api import patient as patient_api
    prod = replace(security.settings, app_mode="production")
    u = account(session)
    with TestClient(app) as doctor, TestClient(app) as c:
        login(doctor, u)
        token = doctor.post("/api/auth/invites", json={}).json()["token"]
        monkeypatch.setattr(security, "settings", prod)
        monkeypatch.setattr(patient_api, "settings", prod)
        assert c.post("/api/patient/encounters", json={"eligibility": ELIG}).status_code == 401
        r = c.post("/api/patient/encounters", json={"invite_token": token, "eligibility": ELIG})
        assert r.status_code == 409


def test_cross_site_mutation_rejected():
    with TestClient(app) as c:
        assert c.post("/api/auth/logout", headers={"Origin": "https://attacker.invalid"}).status_code == 403


def test_demo_cannot_claim_existing_patient_by_code(session):
    enc = svc.create_encounter(session, patient_code="DO-NOT-CLAIM", protocol_id="lbp_adult_v0.2")
    with TestClient(app) as c:
        assert c.post("/api/patient/encounters", json={"patient_code": "DO-NOT-CLAIM", "eligibility": ELIG}).status_code == 409
        assert c.get(f"/api/patient/encounters/{enc.id}").status_code == 401
