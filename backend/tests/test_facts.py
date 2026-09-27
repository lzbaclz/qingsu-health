"""事实状态库语义：未问≠没有；矛盾不覆盖；修正留版本。"""
from app.facts.store import current_facts, fact_history, set_fact
from app.models import FactSource, FactStatus
from app.protocol import get_protocol
from app.services import encounter as svc

PID = "lbp_adult_v0.1"


def _enc(session):
    return svc.create_encounter(session, patient_code=None, protocol_id=PID)


def test_all_facts_start_not_asked(session):
    enc = _enc(session)
    facts = current_facts(session, enc.id)
    proto = get_protocol(PID)
    assert set(facts) == {f.key for f in proto.facts}
    assert all(f.status == FactStatus.NOT_ASKED and f.value is None for f in facts.values())


def test_no_radiation_marks_does_not_mean_denied(session):
    enc = _enc(session)
    svc.add_body_map(session, enc, [{"region_id": "lower_back_left", "kind": "primary"}])
    facts = current_facts(session, enc.id)
    assert facts["pain_regions"].status == FactStatus.PRESENT
    assert facts["pain_side"].value == "left"
    assert facts["radiation_present"].status == FactStatus.NOT_ASKED  # 关键：没标不等于否认


def test_conflict_is_not_overwritten(session):
    enc = _enc(session)
    proto = get_protocol(PID)
    e = svc.add_entry(session, enc, "free_text", {"text": "左边"})
    set_fact(session, enc, proto, "pain_side", status="present", value="left",
             evidence=[{"entry_id": e.id, "quote": "左边", "kind": "free_text"}], source=FactSource.EXTRACTION)
    e2 = svc.add_entry(session, enc, "free_text", {"text": "右边"})
    f = set_fact(session, enc, proto, "pain_side", status="present", value="right",
                 evidence=[{"entry_id": e2.id, "quote": "右边", "kind": "free_text"}], source=FactSource.EXTRACTION)
    assert f.status == FactStatus.CONFLICTING
    assert [c["value"] for c in f.value["candidates"]] == ["left", "right"]
    # 澄清（修正）才能覆盖，且历史保留
    e3 = svc.add_entry(session, enc, "answer", {"text": "both"})
    f2 = set_fact(session, enc, proto, "pain_side", status="present", value="both",
                  evidence=[{"entry_id": e3.id, "quote": "两侧", "kind": "answer"}], source=FactSource.CORRECTION, is_correction=True)
    assert f2.status == FactStatus.PRESENT and f2.value == "both"
    hist = fact_history(session, enc.id, "pain_side")
    assert [h.version for h in hist] == [1, 2, 3, 4]
    assert sum(1 for h in hist if h.superseded_by is None) == 1


def test_uncertain_then_direct_answer_resolves(session):
    enc = _enc(session)
    svc.add_text(session, enc, "腿好像有点麻。")
    assert current_facts(session, enc.id)["leg_numbness"].status == FactStatus.UNCERTAIN
    # 第一题是一键核对（关键事实只来自文字抽取）；选"不确定"后仍保持 uncertain，协议问题会再直接问
    q = svc.get_next_question(session, enc)
    assert q["kind"] == "verification" and "leg_numbness" in q["fact_keys"]
    svc.answer_question(session, enc, q["question_id"], value={k: "unsure" for k in q["fact_keys"]})
    assert current_facts(session, enc.id)["leg_numbness"].status == FactStatus.UNCERTAIN
    for _ in range(30):
        q = svc.get_next_question(session, enc)
        assert q is not None
        if q["fact_key"] == "leg_numbness" and q["kind"] == "protocol":
            break
        svc.answer_question(session, enc, q["question_id"], unknown=True)
    svc.answer_question(session, enc, q["question_id"], value="no")
    assert current_facts(session, enc.id)["leg_numbness"].status == FactStatus.DENIED


def test_skip_records_asked_unanswered_not_denied(session):
    enc = _enc(session)
    svc.add_body_map(session, enc, [{"region_id": "lower_back_center", "kind": "primary"}])
    q = svc.get_next_question(session, enc)
    assert q["question_id"] == "q_bladder_bowel"
    svc.answer_question(session, enc, q["question_id"], skipped=True)
    f = current_facts(session, enc.id)["bladder_bowel_change"]
    assert f.status == FactStatus.ASKED_UNANSWERED and f.value is None
