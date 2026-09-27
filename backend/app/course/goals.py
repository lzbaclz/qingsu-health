"""患者自报生活目标。描述固定，观察追加；非标准化量表，不自动判断临床恢复。"""
from __future__ import annotations

from datetime import date
import math
from sqlmodel import Session, select
from ..models import Encounter, FunctionalGoal, FunctionalObservation, AuditLog
from ..protocol.loader import for_encounter
from ..util import iso


def _error(message):
    from ..services.encounter import FlowError
    raise FlowError(message)


def root_id(session: Session, enc: Encounter) -> str:
    seen = set()
    while enc.parent_encounter_id:
        if enc.id in seen:
            _error("疗程关系异常，请联系门诊")
        seen.add(enc.id)
        parent = session.get(Encounter, enc.parent_encounter_id)
        if not parent or parent.patient_id != enc.patient_id or parent.clinic_id != enc.clinic_id:
            _error("疗程关系不完整")
        enc = parent
    return enc.id


def _enabled(session, enc):
    if not for_encounter(session, enc).course.functional_goals_enabled:
        _error("此记录的协议未启用生活目标")


def create_goal(session, enc, description, unit, conditions, confirmed):
    _enabled(session, enc)
    if not confirmed or not description.strip() or not conditions.strip() or unit not in {"minutes", "metres", "count"}:
        _error("请确认自己的目标、单位及观察条件")
    root = root_id(session, enc)
    existing = session.exec(select(FunctionalGoal).where(FunctionalGoal.root_encounter_id == root)).all()
    if len(existing) >= 5:
        _error("本疗程最多记录五个目标，请先与门诊核对")
    goal = FunctionalGoal(patient_id=enc.patient_id, clinic_id=enc.clinic_id, root_encounter_id=root,
                          description=description.strip(), unit=unit, conditions=conditions.strip())
    session.add(goal)
    session.add(AuditLog(actor=f"patient:{enc.patient_id}", action="functional_goal.confirmed",
                         target_type="functional_goal", target_id=goal.id, detail={"encounter_id": enc.id}))
    session.commit()
    return view(session, enc)


def add_observation(session, enc, goal_id, data):
    from .hours import local_now
    _enabled(session, enc)
    goal = session.get(FunctionalGoal, goal_id)
    if not goal or goal.patient_id != enc.patient_id or goal.clinic_id != enc.clinic_id or goal.root_encounter_id != root_id(session, enc):
        _error("生活目标不属于本疗程")
    values = dict(data)
    values["conditions"] = values["conditions"].strip()
    if values["state"] == "measured":
        value = values["value"]
        if value is None or not math.isfinite(value) or value < 0 or value > 100000:
            _error("请填写有效的观察值；不知道时请选择未测量")
    elif values["value"] is not None:
        _error("未观察或不清楚的记录不能带数值")
    if values["observed_date"]:
        try:
            if date.fromisoformat(values["observed_date"]) > local_now().date():
                _error("观察日期不能在未来")
        except ValueError:
            _error("观察日期无效")
    if values["condition_match"] == "same" and values["conditions"] != goal.conditions:
        _error("条件有变化，请选择条件不同")
    if not values["conditions"]:
        _error("请说明观察条件，或填写不清楚")
    old = session.exec(select(FunctionalObservation).where(FunctionalObservation.goal_id == goal.id,
                           FunctionalObservation.submission_key == values["submission_key"])).first()
    if old:
        if old.encounter_id != enc.id or any(getattr(old, k) != v for k, v in values.items()):
            _error("提交标识已用于另一份记录，请刷新")
        return view(session, enc)
    obs = FunctionalObservation(goal_id=goal.id, encounter_id=enc.id, **values)
    session.add(obs)
    session.add(AuditLog(actor=f"patient:{enc.patient_id}", action="functional_observation.recorded",
                         target_type="functional_observation", target_id=obs.id, detail={"encounter_id": enc.id}))
    session.commit()
    return view(session, enc)


def view(session, enc):
    root = root_id(session, enc)
    goals = session.exec(select(FunctionalGoal).where(FunctionalGoal.root_encounter_id == root,
                  FunctionalGoal.patient_id == enc.patient_id, FunctionalGoal.clinic_id == enc.clinic_id)).all()
    result = []
    for goal in goals:
        observations = session.exec(select(FunctionalObservation).where(FunctionalObservation.goal_id == goal.id)
                                    .order_by(FunctionalObservation.created_at)).all()
        comparison = {"comparable": False, "delta": None, "reason": "至少需要两次有日期、同条件的实际观察"}
        if len(observations) >= 2:
            a, b = observations[-2:]
            if a.state != "measured" or b.state != "measured":
                comparison["reason"] = "最近两次含未测量或不清楚，未按零计算"
            elif a.condition_match != "same" or b.condition_match != "same":
                comparison["reason"] = "观察条件不同或未知，数值不直接比较"
            elif not a.observed_date or not b.observed_date or b.observed_date <= a.observed_date:
                comparison["reason"] = "观察日期缺失、相同或倒序，不能当作后续变化"
            else:
                comparison = {"comparable": True, "delta": round(b.value - a.value, 3),
                              "reason": "同目标同条件的自报数值差；不代表疗效或医学判断"}
        result.append({"id": goal.id, "description": goal.description, "unit": goal.unit, "conditions": goal.conditions,
                       "confirmed_at": iso(goal.confirmed_at), "comparison": comparison,
                       "observations": [{**o.model_dump(), "created_at": iso(o.created_at)} for o in observations]})
    return result
