import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.course import teachback
from app.facts.store import current_facts
from app.llm.provider import MockProvider, OllamaProvider
from app.main import app
from app.models import Encounter, EncounterStatus, Notification, NotificationStatus, PlanVersion, Task, TaskStatus, TeachbackResponse
from app.protocol.loader import for_encounter
from app.services import encounter as svc
from app.tasks.service import notification_to_dict

MESSAGE = "请一周后复查。"
ELIG = {"adult": True, "not_pregnant": True, "no_major_trauma": True}


def plan(session, message=MESSAGE, enc=None):
    enc = enc or svc.create_encounter(session, patient_code=None, protocol_id="lbp_adult_v0.2")
    enc.status = EncounterStatus.DOCTOR_CONFIRMED
    session.add(enc); session.commit()
    result = svc.set_followup_plan(session, enc, "staff:doctor-test", {
        "patient_message": message, "understanding_points": [message], "interval_days": 7,
        "expected_plan_version_id": (enc.followup_plan or {}).get("version_id")})
    return enc, result["followup_plan"]["version_id"]


class SemanticReader:
    name = last_used = "test:semantic"

    def __init__(self, quote="明天", verdict="contradicts"):
        self.quote, self.verdict = quote, verdict

    def structured_task(self, kind, system, user, schema):
        content = json.loads(user)
        return schema(items=[{"point_id": p["id"], "verdict": self.verdict,
                              "plan_quote": p["text"], "response_quote": self.quote, "issue": "time"}
                             for p in content["approved_points"]])


def test_plan_versions_are_immutable_and_stale_update_is_rejected(session):
    enc, first_id = plan(session)
    first = session.get(PlanVersion, first_id)
    old_sha, old_content = first.content_sha256, dict(first.content)
    _, second_id = plan(session, "请两周后复查。", enc)
    assert second_id != first_id
    session.refresh(first)
    assert first.content == old_content and first.content_sha256 == old_sha
    with pytest.raises(svc.FlowError, match="版本已改变"):
        svc.set_followup_plan(session, enc, "staff:other", {"patient_message": MESSAGE,
            "understanding_points": [MESSAGE], "expected_plan_version_id": first_id})
    assert len(session.exec(select(PlanVersion).where(PlanVersion.encounter_id == enc.id)).all()) == 2
    ns = session.exec(select(Notification).where(Notification.encounter_id == enc.id)).all()
    assert len(ns) == 2 and all(n.status == NotificationStatus.QUEUED for n in ns)
    assert {n.plan_version_id for n in ns} == {first_id, second_id}
    flags = {n.plan_version_id: notification_to_dict(n)["is_current_plan"] for n in ns}
    assert not flags[first_id] and flags[second_id]


def test_review_points_cannot_add_new_medical_content(session):
    enc = svc.create_encounter(session, patient_code=None, protocol_id="lbp_adult_v0.2")
    enc.status = EncounterStatus.DOCTOR_CONFIRMED
    session.add(enc); session.commit()
    with pytest.raises(svc.FlowError, match="至少一个"):
        svc.set_followup_plan(session, enc, "staff:test", {"patient_message": MESSAGE})
    with pytest.raises(svc.FlowError, match="逐字"):
        svc.set_followup_plan(session, enc, "staff:test", {"patient_message": MESSAGE, "understanding_points": ["每天增加一次药物"]})
    assert not session.exec(select(PlanVersion).where(PlanVersion.encounter_id == enc.id)).all()
    assert enc.followup_plan is None


def test_semantic_candidate_never_automatically_confirms_understanding_or_execution(session, monkeypatch):
    enc, pid = plan(session)
    monkeypatch.setattr(teachback, "get_provider", lambda: SemanticReader())
    result = teachback.submit_response(session, enc, for_encounter(session, enc), pid, "我明天就去复查。", "planned", "", "test-submit-1")
    row = session.get(TeachbackResponse, result["id"])
    assert row.analysis["source"] == "model" and row.analysis["items"][0]["verdict"] == "contradicts"
    assert not row.reviewed and row.execution_status == "planned"
    assert row.analysis["requires_human_review"]
    task = session.exec(select(Task).where(Task.encounter_id == enc.id, Task.kind == "teachback_review")).one()
    assert task.status != TaskStatus.COMPLETED
    teachback.review_response(session, enc, row.id, "staff:nurse", "needs_explanation", "已经重新说明复查时机，仍需核实")
    session.refresh(task)
    assert task.status == TaskStatus.PENDING and not row.reviewed


def test_literal_match_is_not_semantic_success(session, monkeypatch):
    enc, pid = plan(session)
    monkeypatch.setattr(teachback, "get_provider", lambda: MockProvider())
    r = teachback.submit_response(session, enc, for_encounter(session, enc), pid,
        "你说“请一周后复查。”，但我没准备去。", "unable", "时间安排有困难", "literal-test-1")
    row = session.get(TeachbackResponse, r["id"])
    assert row.analysis["source"] == "literal_only"
    assert row.analysis["items"][0]["verdict"] == "literal_match"
    assert not row.reviewed and row.execution_status == "unable"


def test_model_invented_quote_is_rejected_but_original_response_survives(session, monkeypatch):
    enc, pid = plan(session)
    monkeypatch.setattr(teachback, "get_provider", lambda: SemanticReader(quote="患者实际没说过"))
    r = teachback.submit_response(session, enc, for_encounter(session, enc), pid, "我明天去。", "not_started", "", "invalid-cite-1")
    row = session.get(TeachbackResponse, r["id"])
    assert row.response_text == "我明天去。"
    assert row.analysis["source"] == "manual_required"
    assert row.analysis["diagnostic_code"] == "response_quote_not_verbatim"
    assert row.analysis["items"][0]["verdict"] == "unclear"
    assert not row.reviewed


def test_submission_retry_does_not_create_duplicate_task(session, monkeypatch):
    enc, pid = plan(session)
    monkeypatch.setattr(teachback, "get_provider", lambda: MockProvider())
    args = (session, enc, for_encounter(session, enc), pid, "我理解了部分。", "unclear", "", "retry-identical-1")
    one = teachback.submit_response(*args); two = teachback.submit_response(*args)
    assert one["id"] == two["id"]
    assert len(session.exec(select(Task).where(Task.encounter_id == enc.id, Task.kind == "teachback_review")).all()) == 1
    with pytest.raises(svc.FlowError, match="内容发生变化"):
        teachback.submit_response(session, enc, for_encounter(session, enc), pid, "我改了内容", "unclear", "", "retry-identical-1")


def test_old_response_remains_bound_to_old_plan(session, monkeypatch):
    enc, old_id = plan(session)
    _, new_id = plan(session, "请两周后复查。", enc)
    monkeypatch.setattr(teachback, "get_provider", lambda: MockProvider())
    result = teachback.submit_response(session, enc, for_encounter(session, enc), old_id, MESSAGE, "planned", "", "old-version-1")
    assert "历史计划" in result["message"]
    rows = teachback.doctor_responses(session, enc)
    assert rows[0]["plan_version_id"] == old_id and not rows[0]["is_current_plan"]
    assert rows[0]["analysis"]["items"][0]["point_text"] == MESSAGE
    assert new_id != old_id


def test_reopening_understanding_review_preserves_execution_and_history(session, monkeypatch):
    enc, pid = plan(session)
    monkeypatch.setattr(teachback, "get_provider", lambda: MockProvider())
    r = teachback.submit_response(session, enc, for_encounter(session, enc), pid, MESSAGE, "planned", "", "review-cycle-1")
    teachback.review_response(session, enc, r["id"], "staff:nurse", "aligned", "已核对复述表达")
    row = session.get(TeachbackResponse, r["id"])
    assert row.reviewed and row.execution_status == "planned"
    teachback.review_response(session, enc, r["id"], "staff:doctor", "unclear", "发现仍有歧义，继续核实")
    tasks = session.exec(select(Task).where(Task.encounter_id == enc.id, Task.kind == "teachback_review")).all()
    assert any(t.status != TaskStatus.COMPLETED for t in tasks)
    assert any(t.status == TaskStatus.COMPLETED for t in tasks)
    assert not row.reviewed and len(row.review["history"]) == 2


def test_patient_cannot_submit_another_records_plan(session):
    with TestClient(app) as patient:
        eid = patient.post("/api/patient/encounters", json={"eligibility": ELIG}).json()["id"]
        other, pid = plan(session)
        body = {"response_text": "测试复述", "execution_status": "planned", "submission_key": "foreign-plan-1"}
        assert patient.post(f"/api/patient/encounters/{other.id}/plans/{pid}/teachback", json=body).status_code == 404
        assert patient.post(f"/api/patient/encounters/{eid}/plans/{pid}/teachback", json=body).status_code == 400


def test_ollama_receives_teachback_schema_not_extraction_schema(monkeypatch):
    from dataclasses import replace
    from app.llm import provider
    seen = []
    def transport(request):
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, json={"message": {"content": json.dumps({"items": [{"point_id": "p1", "verdict": "contradicts", "plan_quote": MESSAGE, "response_quote": "明天", "issue": "time"}]}, ensure_ascii=False)}})
    monkeypatch.setattr(provider, "settings", replace(provider.settings, ollama_model="test-local"))
    reader = OllamaProvider(transport=httpx.MockTransport(transport))
    monkeypatch.setattr(teachback, "get_provider", lambda: reader)
    result = teachback.compare([{"id": "p1", "text": MESSAGE}], "我明天去复查")
    assert result["source"] == "model"
    assert "items" in seen[0]["format"]["properties"] and "facts" not in seen[0]["format"]["properties"]
    item_schema = seen[0]["format"]["$defs"]["ComparisonItem"]
    assert "response_quote" in item_schema["required"]
    assert item_schema["properties"]["response_quote"]["minLength"] == 1


def test_missing_or_empty_response_quote_cannot_support_a_model_verdict():
    from pydantic import ValidationError
    for verdict in ("consistent", "contradicts", "omitted", "unclear"):
        item = {"point_id": "p1", "verdict": verdict, "plan_quote": MESSAGE, "issue": "none"}
        with pytest.raises(ValidationError):
            teachback.Comparison(items=[item])
        with pytest.raises(ValidationError):
            teachback.Comparison(items=[{**item, "response_quote": ""}])


def test_acknowledgement_quote_can_show_an_omission_without_claiming_understanding(monkeypatch):
    monkeypatch.setattr(teachback, "get_provider", lambda: SemanticReader(quote="我看到了", verdict="omitted"))
    result = teachback.compare([{"id": "p1", "text": MESSAGE}], "我看到了")
    assert result["source"] == "model" and result["requires_human_review"]
    assert result["items"][0]["verdict"] == "omitted"


def test_mismatched_point_id_is_rejected_without_rebinding_by_position(monkeypatch):
    class WrongId:
        name = "test:wrong-point"
        def structured_task(self, kind, system, user, schema):
            return schema(items=[{"point_id": "different-plan-point", "verdict": "consistent",
                "plan_quote": MESSAGE, "response_quote": "一周", "issue": "none"}])
    monkeypatch.setattr(teachback, "get_provider", lambda: WrongId())
    result = teachback.compare([{"id": "p1", "text": MESSAGE}], "我一周后去复查")
    assert result["source"] == "manual_required"
    assert result["diagnostic_code"] == "point_id_mismatch"
