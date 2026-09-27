"""验证缺配置、空随访、联系失败和通知回执这些真实失效路径。"""
from datetime import datetime, timedelta, timezone
from dataclasses import replace
import json

import pytest
from sqlmodel import select

from app.models import EncounterStatus, Task, TaskDelivery, TaskStatus
from app.services import encounter as svc
from app.protocol import get_protocol
from app.protocol.loader import for_encounter
from app.course.tasks import (_due, complete_with_closure, create_routed_task, escalate_to_doctor,
                              record_contact_attempt, sweep_no_response)
from app.tasks.service import TransitionError, transition_task
from app.util import iso, now, set_clock
from app.security import real_now


@pytest.fixture(autouse=True)
def clock():
    set_clock(datetime(2026, 9, 28, 1, 0, tzinfo=timezone.utc))
    yield
    set_clock(None)


def encounter(session, code=None, clinic="clinic_demo"):
    return svc.create_encounter(session, patient_code=code, protocol_id="lbp_adult_v0.2", clinic_id=clinic)


def plan(session, enc):
    enc.status = EncounterStatus.DOCTOR_CONFIRMED
    enc.followup_plan = {"interval_days": 1, "set_at": iso(now()), "patient_message": "模拟"}
    session.add(enc)
    session.commit()


def test_default_protocol_has_course_and_deadline():
    p = get_protocol("lbp_adult_v0.2")
    assert p.version == "0.2.6" and p.status == "draft" and p.course.simulated
    assert p.course.no_response and len(p.course.outcomes) == 3 and p.course.task_routing
    role, due, _ = _due(p, "same_day", now())
    assert role == "nurse" and (due - now()).total_seconds() == pytest.approx(7200, abs=1)
    late = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)  # 17:00 开诊，17:30 截止
    _, due, _ = _due(p, "same_day", late)
    assert (due - late).total_seconds() == 1800


def test_draft_followup_does_not_suppress_and_confirmed_one_does(session):
    e1, e2 = encounter(session, "NR-DRAFT"), encounter(session, "NR-DONE")
    plan(session, e1); plan(session, e2)
    c1 = svc.create_encounter(session, patient_code="NR-DRAFT", protocol_id=e1.protocol_id,
                              kind="follow_up", parent_encounter_id=e1.id)
    c2 = svc.create_encounter(session, patient_code="NR-DONE", protocol_id=e2.protocol_id,
                              kind="follow_up", parent_encounter_id=e2.id)
    c2.patient_confirmed_at = now() + timedelta(days=1)
    c2.status = EncounterStatus.READY_FOR_DOCTOR
    session.add(c2); session.commit()
    set_clock(now() + timedelta(days=4))
    sweep_no_response(session); sweep_no_response(session)
    tasks = session.exec(select(Task).where(Task.kind == "no_response", Task.encounter_id.in_([e1.id, e2.id]))).all()
    assert len(tasks) == 1 and tasks[0].encounter_id == e1.id
    assert c1.patient_confirmed_at is None


def test_unreached_keeps_open_and_escalation_assigns_doctor(session):
    enc = encounter(session)
    p = for_encounter(session, enc)
    t = create_routed_task(session, p, enc.id, "red_flag_review", "模拟红旗", severity="urgent")
    transition_task(session, t, TaskStatus.VIEWED, "staff:test")
    with pytest.raises(TransitionError, match="不能记为完成"):
        complete_with_closure(session, p, t, "staff:test", {"reached": "not_reached", "attempts": 99}, "未接通")
    assert t.status != TaskStatus.COMPLETED and not t.closure
    record_contact_attempt(session, t, "staff:test", "unreached", "拨打未接通")
    escalate_to_doctor(session, t, "staff:test", "未联系上，请医生继续接手")
    assert t.assignee_role == "doctor" and t.assignee is None and t.status == TaskStatus.ESCALATED
    with pytest.raises(TransitionError, match="联系证据"):
        complete_with_closure(session, p, t, "staff:doctor", {"reached": "patient", "advice": "ed_now"}, "已告知")
    record_contact_attempt(session, t, "staff:doctor", "reached", "患者已接电话，记录后续安排")
    complete_with_closure(session, p, t, "staff:doctor", {"reached": "patient", "advice": "ed_now"}, "患者表示已了解安排")
    assert t.status == TaskStatus.COMPLETED and t.closure["attempts"] == 2


def test_nurse_cannot_record_doctor_only_disposition(session):
    e = encounter(session); p = for_encounter(session, e)
    t = create_routed_task(session, p, e.id, "red_flag_review", "模拟", severity="same_day")
    transition_task(session, t, TaskStatus.VIEWED, "staff:nurse")
    record_contact_attempt(session, t, "staff:nurse", "in_person", "当面联系")
    with pytest.raises(TransitionError, match="角色"):
        complete_with_closure(session, p, t, "staff:nurse",
                              {"reached": "in_person", "advice": "no_urgent_action", "reason": "模拟"}, "安排", "nurse")


def test_worker_delivery_not_configured_is_not_success(session, monkeypatch):
    from app.course import worker
    monkeypatch.setattr(worker, "settings", replace(worker.settings, delivery_config=""))
    e = encounter(session, clinic="without-channel")
    t = create_routed_task(session, for_encounter(session, e), e.id, "red_flag_review", "模拟", severity="urgent")
    worker.tick(deliver=lambda *_: pytest.fail("没有配置不应调用通道"))
    rows = session.exec(select(TaskDelivery).where(TaskDelivery.task_id == t.id)).all()
    assert len(rows) == 1 and rows[0].state == "unconfigured" and rows[0].attempts == 0
    assert t.status == TaskStatus.UNVIEWED


def test_delivery_idempotent_and_does_not_close_task(session, monkeypatch, tmp_path):
    from app.course import worker
    cfg = tmp_path / "channels.json"
    cfg.write_text(json.dumps({"delivery-only": {"url": "https://receiver.invalid/", "secret": "test-only-secret"}}))
    monkeypatch.setattr(worker, "settings", replace(worker.settings, delivery_config=str(cfg)))
    e = encounter(session, clinic="delivery-only")
    t = create_routed_task(session, for_encounter(session, e), e.id, "red_flag_review", "患者原话不可发送", severity="urgent")
    sent = []
    worker.tick(deliver=lambda url, body, headers: sent.append((json.loads(body), headers)))
    worker.tick(deliver=lambda *_: pytest.fail("同一通知不能重复发送"))
    assert len(sent) == 1 and sent[0][0]["task_id"] == t.id
    assert "患者" not in json.dumps(sent) and sent[0][1]["X-Tiji-Signature"]
    session.refresh(t)
    assert t.status == TaskStatus.UNVIEWED


def test_channel_three_failures_stops_until_operator_intervenes(session, monkeypatch, tmp_path):
    from app.course import worker
    cfg = tmp_path / "channels.json"
    cfg.write_text(json.dumps({"failure-only": {"url": "https://receiver.invalid/", "secret": "test-secret"}}))
    monkeypatch.setattr(worker, "settings", replace(worker.settings, delivery_config=str(cfg)))
    e = encounter(session, clinic="failure-only")
    t = create_routed_task(session, for_encounter(session, e), e.id, "red_flag_review", "模拟", severity="urgent")
    def fail(*_):
        raise RuntimeError("模拟未接收")
    for _ in range(3):
        worker.tick(deliver=fail)
        session.expire_all()
        row = session.exec(select(TaskDelivery).where(TaskDelivery.task_id == t.id)).one()
        row.next_attempt_at = real_now() - timedelta(seconds=1)
        session.add(row); session.commit()
    assert row.state == "failed" and row.attempts == 3
    worker.tick(deliver=lambda *_: pytest.fail("三次失败后不得后台续发"))


def test_encounter_protocol_remains_pinned_after_file_change(session, monkeypatch, tmp_path):
    from app.protocol import loader
    import yaml
    original = get_protocol("lbp_adult_v0.2")
    e = encounter(session)
    changed = original.model_dump(mode="json")
    changed["max_questions"] = original.max_questions + 10
    (tmp_path / "lbp_adult_v0.2.yaml").write_text(yaml.safe_dump(changed, allow_unicode=True))
    monkeypatch.setattr(loader, "settings", replace(loader.settings, protocol_dir=tmp_path))
    assert loader.get_protocol(e.protocol_id).max_questions != original.max_questions
    assert for_encounter(session, e).max_questions == original.max_questions
