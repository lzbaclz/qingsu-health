"""第 1 轮团队评审：红旗一屏、红旗不对称信任、红旗专查、红旗题上的"不清楚"。"""
from sqlmodel import select

from app.extraction import service as xsvc
from app.llm.provider import CandidateFact, ExtractionOutput
from app.models import Alert, FactStatus
from app.facts.store import current_facts
from app.services import encounter as svc

V1, V2 = "lbp_adult_v0.1", "lbp_adult_v0.2"
ELIG2 = {"adult": True, "not_pregnant": True, "no_major_trauma": True}


class FakeProvider:
    """模拟一个会读错的真实模型：主抽取与红旗专查各返回预设结果。"""
    name = "fake:model"
    last_used = "fake:model"

    def __init__(self, main, rf=None):
        self.main, self.rf = main, rf

    def extract(self, text, protocol):
        return ExtractionOutput(facts=[CandidateFact(**c) for c in self.main])

    def extract_red_flags(self, text, protocol):
        return ExtractionOutput(facts=[CandidateFact(**c) for c in (self.rf or [])])

    def narrative(self, lines, protocol):
        return "（测试叙述）"


def _alerts(session, enc):
    return {a.rule_id for a in session.exec(select(Alert).where(Alert.encounter_id == enc.id)).all()}


def test_unknown_on_red_flag_question_becomes_uncertain_and_alerts(session):
    """P0-2：红旗题点"不清楚"记为"不确定"，rf_uncertain_red_flag 接得住（以前记成"未回答"，既无提示也无任务）。"""
    enc = svc.create_encounter(session, patient_code=None, protocol_id=V1)
    svc.add_text(session, enc, "腰疼三天了。")
    for _ in range(40):
        q = svc.get_next_question(session, enc)
        if q is None or q["question_id"] == "q_bladder_bowel":
            break
        if q["kind"] == "verification":
            svc.answer_question(session, enc, q["question_id"], value={k: "confirm" for k in q["fact_keys"]})
        else:
            svc.answer_question(session, enc, q["question_id"], skipped=True) if q.get("allow_skip") else \
                svc.answer_question(session, enc, q["question_id"], unknown=True)
    assert q and q["question_id"] == "q_bladder_bowel"
    svc.answer_question(session, enc, "q_bladder_bowel", unknown=True)
    f = current_facts(session, enc.id)["bladder_bowel_change"]
    assert f.status == FactStatus.UNCERTAIN and "不清楚" in f.evidence[-1]["quote"]
    assert "rf_uncertain_red_flag" in _alerts(session, enc)


def test_red_flag_grid_is_one_screen_not_counted(session):
    enc = svc.create_encounter(session, patient_code=None, protocol_id=V2, eligibility=ELIG2)
    svc.add_text(session, enc, "腰疼一周，坐久了更疼。")
    q = svc.get_next_question(session, enc)
    while q and q["kind"] == "verification":
        svc.answer_question(session, enc, q["question_id"], value={k: "confirm" for k in q["fact_keys"]})
        q = svc.get_next_question(session, enc)
    assert q["kind"] == "red_flag_grid" and q["type"] == "grid"
    ids = [i["question_id"] for i in q["items"]]
    assert "q_bladder_bowel" in ids and "q_saddle" in ids and len(ids) >= 5
    before = enc.question_count
    svc.answer_question(session, enc, q["question_id"], value={i: "no" for i in ids})
    assert enc.question_count == before  # 不计题数
    facts = current_facts(session, enc.id)
    assert all(facts[i["fact_key"]].status == FactStatus.DENIED for i in q["items"])
    nq = svc.get_next_question(session, enc)
    assert nq is None or nq["kind"] != "red_flag_grid" or not set(i["question_id"] for i in nq["items"]) & set(ids)


def test_grid_yes_on_bladder_triggers_urgent_stop(session):
    enc = svc.create_encounter(session, patient_code=None, protocol_id=V2, eligibility=ELIG2)
    svc.add_text(session, enc, "腰疼一周。")
    q = svc.get_next_question(session, enc)
    while q and q["kind"] != "red_flag_grid":
        svc.answer_question(session, enc, q["question_id"], value={k: "confirm" for k in q.get("fact_keys", [])})
        q = svc.get_next_question(session, enc)
    vals = {i["question_id"]: ("yes" if i["question_id"] == "q_bladder_bowel" else "no") for i in q["items"]}
    res = svc.answer_question(session, enc, q["question_id"], value=vals)
    assert any(a["rule_id"] == "rf_bladder_bowel" for a in res["new_alerts"])
    assert svc.get_next_question(session, enc) is None  # 紧急：终止问询（直接回答无需再核对）


def test_reloading_pending_grid_preserves_every_unanswered_safety_item(session):
    enc = svc.create_encounter(session, patient_code=None, protocol_id=V2, eligibility=ELIG2)
    svc.add_text(session, enc, "腰疼一周。")
    q = svc.get_next_question(session, enc)
    while q and q["kind"] == "verification":
        svc.answer_question(session, enc, q["question_id"], value={k: "confirm" for k in q["fact_keys"]})
        q = svc.get_next_question(session, enc)
    assert q["kind"] == "red_flag_grid"
    restored = svc.get_next_question(session, enc)
    assert restored["question_id"] == q["question_id"]
    assert restored["items"] == q["items"]
    assert restored["kind"] == "red_flag_grid"


def test_direct_confirm_cannot_skip_pending_safety_screen(session):
    import pytest
    enc = svc.create_encounter(session, patient_code=None, protocol_id=V2, eligibility=ELIG2)
    svc.add_text(session, enc, "腰疼一周。")
    with pytest.raises(svc.FlowError, match="待回答"):
        svc.patient_confirm(session, enc)
    assert enc.patient_confirmed_at is None


def test_misread_red_flag_denial_is_still_asked_directly(session, monkeypatch):
    """新策略先直接问安全题；模型错读的阴性不能替代患者回答，也不需要重复确认同一阴性。"""
    text = "腰疼一周，屁股中间那块木木的，没什么感觉。"
    monkeypatch.setattr(xsvc, "get_provider", lambda: FakeProvider(
        [{"key": "saddle_numbness", "status": "denied", "value": None, "quote": "没什么感觉"}]))
    enc = svc.create_encounter(session, patient_code=None, protocol_id=V2, eligibility=ELIG2)
    svc.add_text(session, enc, text)
    q = svc.get_next_question(session, enc)
    assert q["kind"] == "red_flag_grid" and "q_saddle" in [i["question_id"] for i in q["items"]]
    vals = {i["question_id"]: ("yes" if i["question_id"] == "q_saddle" else "no") for i in q["items"]}
    svc.answer_question(session, enc, q["question_id"], value=vals)
    f = current_facts(session, enc.id)["saddle_numbness"]
    assert f.status == FactStatus.PRESENT  # 直接回答为准，不进澄清
    assert "rf_saddle" in _alerts(session, enc)


def test_red_flag_pass_adds_and_raises(session, monkeypatch):
    """红旗专查补漏；新版保留两遍相反证据为矛盾，不自动消除否认。"""
    text = "腰杆痛了个把月了，这两天解手都解不干净，也没发烧。"
    monkeypatch.setattr(xsvc, "get_provider", lambda: FakeProvider(
        main=[{"key": "fever", "status": "denied", "value": None, "quote": "也没发烧"},
              {"key": "saddle_numbness", "status": "denied", "value": None, "quote": "解手都解不干净"}],
        rf=[{"key": "bladder_bowel_change", "status": "present", "value": True, "quote": "解手都解不干净"},
            {"key": "saddle_numbness", "status": "uncertain", "value": None, "quote": "解手都解不干净"},
            {"key": "onset_timing", "status": "present", "value": "weeks_2_to_6", "quote": "个把月"}]))
    enc = svc.create_encounter(session, patient_code=None, protocol_id=V2, eligibility=ELIG2)
    res = svc.add_text(session, enc, text)
    ex = res["extraction"]
    assert ex["red_flag_pass"]["ran"] is True
    assert "bladder_bowel_change" in ex["red_flag_pass"]["added"] and "saddle_numbness" in ex["red_flag_pass"]["raised"]
    facts = current_facts(session, enc.id)
    assert facts["bladder_bowel_change"].status == FactStatus.PRESENT
    assert facts["saddle_numbness"].status == FactStatus.CONFLICTING
    assert {c["status"] for c in facts["saddle_numbness"].value["candidates"]} == {"denied", "uncertain"}
    assert facts["onset_timing"].status == FactStatus.NOT_ASKED  # 专查只认红旗事实
    assert "rf_bladder_bowel" in _alerts(session, enc)
