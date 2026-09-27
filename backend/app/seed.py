"""演示数据：四条路径（正常 / 矛盾澄清 / 红旗 / 随访）。全部为**模拟**，非真实患者。"""
from __future__ import annotations

from sqlmodel import Session, select

from .config import settings
from .models import Encounter, Patient
from .services import encounter as svc


def _drain_questions(session: Session, enc: Encounter, answers: dict[str, object], default_unknown: bool = True) -> None:
    """按脚本回答；脚本没写的题按 default 处理（不清楚），保证'未问≠没有'被真实记录。"""
    for _ in range(60):
        q = svc.get_next_question(session, enc)
        if q is None:
            return
        qid = q["question_id"]
        if q["kind"] == "event_context":
            # 只使用事先写好的模拟情境标签；没有标签时如实回答不确定。
            svc.answer_question(session, enc, qid, value=(answers.get("__context__") or {}).get(q["fact_key"], "unsure"))
            continue
        if q["kind"] == "red_flag_grid":
            # 本演示脚本中的未列出红旗预先定义为阴性；不应用于真实患者。
            vals = {i["question_id"]: answers.get(i["question_id"], "no") for i in q["items"]}
            svc.answer_question(session, enc, qid, value=vals)
            continue
        if q["kind"] == "verification":
            decisions = answers.get("__verify__", {})
            svc.answer_question(session, enc, qid, value={k: decisions.get(k, "confirm") for k in q["fact_keys"]})
            continue
        if q["kind"] == "clarification":
            resolve = answers.get("__clarify__", {}).get(q["fact_key"])
            opt = next((o for o in q["options"] if o.get("resolve") == resolve), None)
            svc.answer_question(session, enc, qid, value=opt["value"] if opt else q["options"][-1]["value"])
            continue
        if qid in answers:
            svc.answer_question(session, enc, qid, value=answers[qid])
        else:
            svc.answer_question(session, enc, qid, unknown=default_unknown, skipped=not default_unknown)


_ELIG = {"adult": True, "not_pregnant": True, "no_major_trauma": True}  # 演示数据按"开始页已确认适用范围"创建


def seed_demo(session: Session) -> dict:
    if session.exec(select(Patient)).first():
        return {"seeded": False, "reason": "已有数据，原样保留；需要全新演示时选择另一个空数据库"}
    pid = settings.default_protocol_id
    created = {}

    # 1) 正常路径：左腰酸，坐久加重，无红旗，患者确认 → 待医生核对
    e1 = svc.create_encounter(session, patient_code="P-0001", protocol_id=pid, eligibility=_ELIG)
    svc.add_body_map(session, e1, [{"region_id": "lower_back_left", "kind": "primary"}])
    svc.add_text(session, e1, "前两天搬东西后左边腰酸，坐久了更明显，躺着好一些，腿不麻。")
    _drain_questions(session, e1, {
        "q_bladder_bowel": "no", "q_saddle": "no", "q_leg_weakness": "no", "q_fever": "no", "q_trauma": "no",
        "q_pv_pain_avg_7d": 4, "q_pv_interference_7d": 3, "q_age_band": "18_49",
        "q_onset_mode": "sudden", "q_radiation_present": "no", "q_severity_now": 4, "q_function_impact": "mild",
        "q_sleep_affected": "no", "q_night_pain": "no", "q_weight_loss": "no", "q_cancer_history": "no",
        "q_prior_episodes": "no", "q_current_medication": "没有用药", "q_patient_concern": "想知道要不要拍片",
    })
    svc.patient_confirm(session, e1)
    created["normal"] = e1.id

    # 2) 矛盾路径：身体图标左侧，文字说右侧 → 澄清问题挂起（演示"不自动取其一"）
    e2 = svc.create_encounter(session, patient_code="P-0002", protocol_id=pid, eligibility=_ELIG)
    svc.add_body_map(session, e2, [{"region_id": "lower_back_left", "kind": "primary"}])
    svc.add_text(session, e2, "腰一个多月了，右边更明显，走路久了腿有点麻。")
    svc.get_next_question(session, e2)  # 生成澄清问题并挂起
    created["conflict_pending"] = e2.id

    # 3) 红旗路径：文字提到憋不住尿 → 立即提示 + 紧急任务 → 一键核对确认 → 终止问询（不再让患者答题）→ 提交已填内容
    e3 = svc.create_encounter(session, patient_code="P-0003", protocol_id=pid, eligibility=_ELIG)
    svc.add_body_map(session, e3, [{"region_id": "lower_back_center", "kind": "primary"},
                                   {"region_id": "thigh_left_back", "kind": "radiation"}, {"region_id": "calf_left", "kind": "radiation"}])
    svc.add_text(session, e3, "腰痛三个月了，最近越来越痛，左腿麻，这两天小便憋不住。")
    _drain_questions(session, e3, {
        "q_bladder_bowel": "yes", "q_saddle": "no", "q_leg_weakness": "yes", "q_weakness_progressive": "yes", "q_fever": "no",
        "q_trauma": "no", "q_onset_mode": "gradual", "q_trigger": "none_known", "q_severity_now": 8,
        "q_function_impact": "moderate", "q_sleep_affected": "yes",
    })
    svc.patient_confirm(session, e3)
    created["red_flag"] = e3.id

    # 4) 随访路径：上次已由医生确认并设置计划；本次随访加重 + 新情况
    e4 = svc.create_encounter(session, patient_code="P-0004", protocol_id=pid, eligibility=_ELIG)
    svc.add_body_map(session, e4, [{"region_id": "lower_back_right", "kind": "primary"}])
    svc.add_text(session, e4, "右腰酸痛一周，弯腰更明显，没有腿麻。")
    _drain_questions(session, e4, {
        "q_bladder_bowel": "no", "q_saddle": "no", "q_leg_weakness": "no", "q_fever": "no", "q_trauma": "no",
        "q_pv_pain_avg_7d": 6, "q_pv_interference_7d": 4, "q_age_band": "18_49",
        "q_onset_mode": "gradual", "q_trigger": "prolonged_sitting", "q_radiation_present": "no", "q_severity_now": 5,
        "q_course": "stable", "q_function_impact": "mild", "q_sleep_affected": "no",
    })
    svc.patient_confirm(session, e4)
    svc.doctor_view(session, e4, actor="dr_demo")
    svc.doctor_confirm(session, e4, actor="dr_demo")
    svc.set_followup_plan(session, e4, "dr_demo", {
        "interval_days": 7, "understanding_points": ["请一周后在这里更新情况"], "patient_message": "（医生撰写示例）请一周后在这里更新情况；如出现大小便控制变化或腿突然无力，立即联系门诊。"})
    e4b = svc.create_encounter(session, patient_code="P-0004", protocol_id=pid, eligibility=_ELIG, kind="follow_up", parent_encounter_id=e4.id)
    svc.add_body_map(session, e4b, [{"region_id": "lower_back_right", "kind": "primary"}, {"region_id": "buttock_right", "kind": "radiation"}])
    svc.add_text(session, e4b, "比上次更疼了，串到右边屁股，右腿有点麻。")
    _drain_questions(session, e4b, {
        "q_ci_pgic": "worse", "q_ci_pain_avg_7d": 8, "q_ci_interference_7d": 6,
        "q_fu_overall": "worse", "q_fu_severity": 7, "q_fu_new": "yes", "q_fu_new_desc": "右腿开始发麻",
        "q_fu_bladder": "no", "q_fu_saddle": "no", "q_fu_weakness": "no", "q_fu_course": "worsening",
        "q_fu_function": "moderate", "q_fu_sleep": "yes", "q_fu_understood": "no", "q_fu_adherence": "partial",
        "__context__": {"leg_numbness": "new"},
    })
    svc.patient_confirm(session, e4b)
    created["followup_parent"] = e4.id
    created["followup_child"] = e4b.id
    return {"seeded": True, "encounters": created}



def make_followup_parent(session: Session, patient_code: str) -> str:
    """可用性测试卡 D 用：为指定患者编号造一次"医生已确认并已发随访说明"的就诊，返回其编号。全部为模拟内容。"""
    pid = settings.default_protocol_id
    e = svc.create_encounter(session, patient_code=patient_code, protocol_id=pid, eligibility=_ELIG)
    svc.add_body_map(session, e, [{"region_id": "lower_back_right", "kind": "primary"}])
    svc.add_text(session, e, "右腰酸痛一周，弯腰更明显，没有腿麻。")
    _drain_questions(session, e, {
        "q_bladder_bowel": "no", "q_saddle": "no", "q_leg_weakness": "no", "q_fever": "no", "q_trauma": "no",
        "q_pv_pain_avg_7d": 6, "q_pv_interference_7d": 4, "q_age_band": "18_49",
        "q_onset_mode": "gradual", "q_trigger": "prolonged_sitting", "q_radiation_present": "no", "q_severity_now": 5,
        "q_course": "stable", "q_function_impact": "mild", "q_sleep_affected": "no",
    })
    svc.patient_confirm(session, e)
    svc.doctor_view(session, e, actor="dr_demo")
    svc.doctor_confirm(session, e, actor="dr_demo")
    svc.set_followup_plan(session, e, "dr_demo", {
        "interval_days": 7, "understanding_points": ["请一周后在这里更新情况"], "patient_message": "（医生撰写示例）请一周后在这里更新情况；如出现大小便控制变化或腿突然无力，立即联系门诊。"})
    return e.id
