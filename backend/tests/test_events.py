from dataclasses import replace

import pytest
from sqlmodel import select

from app.extraction import service as extraction
from app.llm.provider import CandidateFact, ExtractionOutput
from app.events.service import (decision_trace, doctor_review, events_for, infer_context,
                                 next_context_question, patient_correct_event)
from app.facts.store import current_facts, has_direct_answer
from app.models import AskedQuestion, FactStatus, Task, TaskStatus
from app.protocol import get_protocol
from app.protocol.loader import for_encounter
from app.services import encounter as svc

PID = "lbp_adult_v0.2"


class Reader:
    name = last_used = "test:structured_context"

    def __init__(self, facts):
        self.facts = facts

    def extract(self, text, protocol):
        return ExtractionOutput(facts=[CandidateFact(**v) for v in self.facts])


def start(session, monkeypatch, text="我腿有点麻。", key="leg_numbness", **context):
    monkeypatch.setattr(extraction, "get_provider", lambda: Reader([
        {"key": key, "status": "present", "value": True, "quote": text, **context}]))
    enc = svc.create_encounter(session, patient_code=None, protocol_id=PID)
    svc.add_text(session, enc, text)
    return enc


def reach_context(session, enc):
    for _ in range(40):
        q = svc.get_next_question(session, enc)
        if not q or q["kind"] == "event_context":
            return q
        if q["kind"] == "red_flag_grid":
            svc.answer_question(session, enc, q["question_id"], value={x["question_id"]: "no" for x in q["items"]})
        elif q["kind"] == "verification":
            svc.answer_question(session, enc, q["question_id"], value={k: "confirm" for k in q["fact_keys"]})
        else:
            svc.answer_question(session, enc, q["question_id"], unknown=True)
    raise AssertionError("问询未收敛")


@pytest.mark.parametrize("text,subject,relation", [
    ("我妈腿麻", "other", "unknown"),
    ("我今天才开始腿麻", "patient", "new"),
    ("以前腿麻，现在没有了", "patient", "past"),
    ("去年腿就麻，现在还这样", "patient", "ongoing"),
    ("今天才提起去年腿麻的事", "patient", "historical"),
    ("我腿麻", "patient", "unknown"),
    ("我妈说我腿麻", "patient", "unknown"),
])
def test_literal_context_baseline(text, subject, relation):
    result = infer_context(text, text)
    assert result["subject"] == subject
    assert result["time_relation"] == relation
    assert result["quote"] in text
    assert not result["time_text"] or result["time_text"] in text


def test_other_subject_never_becomes_patient_denial_or_presence(session, monkeypatch):
    enc = start(session, monkeypatch, "我妈腿麻。")
    assert current_facts(session, enc.id)["leg_numbness"].status == FactStatus.NOT_ASKED
    event = events_for(session, enc.id)[0]
    assert event.subject == "other"
    assert event.reported_at and event.time_relation == "unknown"


def test_past_resolved_stays_in_event_history_not_current_symptoms(session, monkeypatch):
    enc = start(session, monkeypatch, "以前腿麻，现在没有了。")
    assert events_for(session, enc.id)[0].time_relation == "past"
    assert current_facts(session, enc.id)["leg_numbness"].status == FactStatus.NOT_ASKED


def test_model_cannot_turn_report_time_into_onset(session, monkeypatch):
    text = "今天才提起去年腿麻的事。"
    enc = start(session, monkeypatch, text, subject="patient", time_relation="new", time_text="今天", context_quote=text)
    event = events_for(session, enc.id)[0]
    assert event.time_relation == "historical" and event.time_text == "去年"
    assert "报告时间" in "".join(event.inference_issues)
    assert current_facts(session, enc.id)["leg_numbness"].status == FactStatus.UNCERTAIN


def test_past_onset_does_not_mean_symptom_has_resolved(session, monkeypatch):
    text = "去年腿就麻，现在还这样。"
    enc = start(session, monkeypatch, text, subject="patient", time_relation="past", time_text="去年", context_quote=text)
    event = events_for(session, enc.id)[0]
    assert event.time_relation == "ongoing"
    assert current_facts(session, enc.id)["leg_numbness"].status == FactStatus.PRESENT


def test_unfounded_other_subject_is_kept_uncertain(session, monkeypatch):
    text = "我妈说我腿麻。"
    enc = start(session, monkeypatch, text, subject="other", context_quote=text)
    event = events_for(session, enc.id)[0]
    assert event.subject == "unclear"
    assert current_facts(session, enc.id)["leg_numbness"].status == FactStatus.UNCERTAIN


def test_actual_protocol_branches_determine_question_and_restore(session, monkeypatch):
    enc = start(session, monkeypatch)
    q = reach_context(session, enc)
    assert q and q["kind"] == "event_context"
    assert q["decision_trace"]["distinct_action_sets"] >= 2
    variants = q["decision_trace"]["variants"]
    assert any(any(a["id"] == "event:changed_limb_symptom" for a in v["actions"]) for v in variants if v["time_relation"] == "new")
    assert all(all(a["id"] != "event:changed_limb_symptom" for a in v["actions"]) for v in variants if v["time_relation"] == "ongoing")
    assert svc.get_next_question(session, enc) == q  # 刷新不丢失核实理由、选项或证据
    svc.answer_question(session, enc, q["question_id"], value="new")
    event = events_for(session, enc.id)[0]
    assert event.time_relation == "new" and event.verification_state == "patient_confirmed"
    assert event.history[0]["before"]["time_relation"] == "unknown"
    assert event.confirmed_entry_id
    task = session.exec(select(Task).where(Task.encounter_id == enc.id, Task.kind == "event_review")).one()
    assert task.status != TaskStatus.COMPLETED


def test_equal_actions_skips_context_but_all_strategy_does_not(session, monkeypatch):
    enc = start(session, monkeypatch, "我得过癌症。", key="cancer_history")
    p = for_encounter(session, enc)
    event = events_for(session, enc.id)[0]
    trace = decision_trace(session, enc, p, event)
    assert trace["distinct_action_sets"] == 1 and not trace["should_ask"]
    exhaustive = p.model_copy(deep=True)
    exhaustive.event_verification.strategy = "all"
    assert decision_trace(session, enc, exhaustive, event)["should_ask"]
    assert next_context_question(session, enc, p) is None
    assert current_facts(session, enc.id)["cancer_history"].status == FactStatus.PRESENT


def test_unclear_time_is_not_confirmed_value(session, monkeypatch):
    enc = start(session, monkeypatch)
    q = reach_context(session, enc)
    svc.answer_question(session, enc, q["question_id"], value="unsure")
    event = events_for(session, enc.id)[0]
    assert event.verification_state == "review_required" and event.time_relation == "unknown"
    assert not has_direct_answer(current_facts(session, enc.id)["leg_numbness"])
    assert session.exec(select(Task).where(Task.encounter_id == enc.id, Task.kind == "event_review")).first()


def test_old_event_answer_cannot_hide_newer_report(session, monkeypatch):
    enc = start(session, monkeypatch)
    q = reach_context(session, enc)
    newer = "今天又开始腿麻。"
    monkeypatch.setattr(extraction, "get_provider", lambda: Reader([
        {"key": "leg_numbness", "status": "present", "value": True, "quote": newer}]))
    svc.add_text(session, enc, newer)
    svc.answer_question(session, enc, q["question_id"], value="past")
    fact = current_facts(session, enc.id)["leg_numbness"]
    assert fact.status == FactStatus.PRESENT
    assert any(x["quote"] == newer for x in fact.evidence)


def test_new_urgent_report_interrupts_pending_context(session, monkeypatch):
    enc = start(session, monkeypatch)
    q = reach_context(session, enc)
    urgent = "这两天小便憋不住。"
    monkeypatch.setattr(extraction, "get_provider", lambda: Reader([
        {"key": "bladder_bowel_change", "status": "present", "value": True, "quote": urgent}]))
    svc.add_text(session, enc, urgent)
    next_q = svc.get_next_question(session, enc)
    assert next_q is None or (next_q["kind"] == "verification" and next_q["scope"] == "urgent")
    old = session.exec(select(AskedQuestion).where(AskedQuestion.encounter_id == enc.id, AskedQuestion.question_id == q["question_id"])).one()
    assert old.answer_status == "superseded"


def test_patient_correction_and_doctor_review_keep_history(session, monkeypatch):
    enc = start(session, monkeypatch)
    q = reach_context(session, enc)
    svc.answer_question(session, enc, q["question_id"], value="unsure")
    event = events_for(session, enc.id)[0]
    p = for_encounter(session, enc)
    patient_correct_event(session, enc, p, event.id, "other")
    assert event.subject == "other" and len(event.history) == 2
    result = doctor_review(session, enc, p, event.id, subject="other", time_relation="unknown", note="核实为家属的情况，患者本人另行问询", actor="staff:test")
    assert result["verification_state"] == "doctor_confirmed"
    task = session.exec(select(Task).where(Task.encounter_id == enc.id, Task.kind == "event_review")).one()
    assert task.status == TaskStatus.COMPLETED


def test_old_protocol_does_not_enable_new_workflow():
    p = get_protocol("lbp_adult_v0.1")
    assert not p.event_verification.enabled


def test_grid_counts_each_decision_not_one_screen(session, monkeypatch):
    enc = start(session, monkeypatch)
    q = svc.get_next_question(session, enc)
    assert q["kind"] == "red_flag_grid"
    metric = svc.question_metrics(session, enc.id)
    assert metric["items_shown"] == len(q["items"]) and metric["screens_shown"] == 1


@pytest.mark.parametrize("text,subject,relation", [
    ("我妈腿麻。", "other", "unknown"),
    ("去年腿就麻，现在还这样。", "patient", "ongoing"),
    ("以前腿麻，这次更明显了。", "patient", "worsening"),
])
def test_narrow_model_context_cannot_remove_sentence_relations(session, monkeypatch, text, subject, relation):
    quote = "腿就麻" if "腿就麻" in text else "腿麻"
    monkeypatch.setattr(extraction, "get_provider", lambda: Reader([
        {"key": "leg_numbness", "status": "present", "value": True, "quote": quote,
         "subject": "patient", "time_relation": "unknown", "context_quote": quote}]))
    enc = svc.create_encounter(session, patient_code=None, protocol_id=PID)
    svc.add_text(session, enc, text)
    ev = events_for(session, enc.id)[0]
    assert ev.subject == subject and ev.time_relation == relation
    if subject == "other":
        assert current_facts(session, enc.id)["leg_numbness"].status == FactStatus.NOT_ASKED


def test_conditional_instruction_is_not_a_current_symptom(session, monkeypatch):
    enc = start(session, monkeypatch, "医生说如果腿麻就联系门诊。", subject="patient", context_quote="腿麻")
    ev = events_for(session, enc.id)[0]
    assert ev.assertion_type == "hypothetical"
    assert current_facts(session, enc.id)["leg_numbness"].status == FactStatus.NOT_ASKED
    assert not decision_trace(session, enc, for_encounter(session, enc), ev)["should_ask"]
