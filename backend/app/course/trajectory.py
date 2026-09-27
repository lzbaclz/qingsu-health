"""恢复轨迹卡（第 1 轮团队评审 · 生物学 / 数学 / 医学）：以首诊为基线，按最小临床重要差异（MCID）判读。

- 结论四选一：有意义改善 / 变化不大 / 明显变差 / 数据不足。两端任一未知时记"数据不足"，不当 0 分。
- 只比较患者自报的数值与医生设定的阈值：不做预测、不输出风险分（docs/06）。
- 提醒规则只生成任务（由人处理），阈值来自协议 course.recovery_rules。
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from ..facts.store import current_facts
from ..models import Encounter, EncounterKind, FactStatus, Task
from ..protocol.schema import OutcomeDef, Protocol, RecoveryRule

VERDICT_LABEL = {
    "improved_meaningful": "有意义改善",
    "no_meaningful_change": "变化不大",
    "worse_meaningful": "明显变差",
    "insufficient": "数据不足",
}
CATEGORY_LABEL = {"improved": "患者自评：变好", "same": "患者自评：差不多", "worse": "患者自评：变差"}


def chain(session: Session, enc: Encounter) -> list[Encounter]:
    """同一疗程的全部记录（首诊在前）：沿 parent 找到首诊，再取它下面的所有签到 / 随访。"""
    root, seen = enc, {enc.id}
    while root.parent_encounter_id:
        parent = session.get(Encounter, root.parent_encounter_id)
        if parent is None or parent.id in seen:
            break
        seen.add(parent.id)
        root = parent
    out, frontier = [root], [root.id]
    ids = {root.id}
    while frontier:
        kids = session.exec(select(Encounter).where(Encounter.parent_encounter_id.in_(frontier))).all()  # type: ignore[attr-defined]
        kids = [k for k in kids if k.id not in ids]
        ids.update(k.id for k in kids)
        out += kids
        frontier = [k.id for k in kids]
    return sorted(out, key=lambda e: e.created_at)


def _num(f) -> float | None:
    if f is None or f.status != FactStatus.PRESENT:
        return None
    try:
        return float(f.value)
    except (TypeError, ValueError):
        return None


def _regions(facts: dict, protocol: Protocol) -> list[str] | None:
    keys = [protocol.body_map.regions_fact_key, protocol.body_map.radiation_fact_key]
    vals: set[str] = set()
    known = False
    for k in keys:
        f = facts.get(k) if k else None
        if f is not None and f.status == FactStatus.PRESENT and isinstance(f.value, list):
            vals.update(f.value)
            known = True
    return sorted(vals) if known else None


def verdict(o: OutcomeDef, base: float | None, cur: float | None) -> dict:
    if base is None or cur is None:
        return {"verdict": "insufficient", "label": VERDICT_LABEL["insufficient"], "delta": None, "pct": None}
    improve = (base - cur) if o.direction == "lower_better" else (cur - base)
    pct = round(improve / base * 100) if base else None
    abs_ok = o.mcid_abs is not None and improve >= o.mcid_abs
    pct_ok = o.mcid_pct is not None and pct is not None and pct >= o.mcid_pct
    if o.mcid_abs is not None and -improve >= o.mcid_abs:
        v = "worse_meaningful"
    elif (abs_ok and pct_ok) if (o.rule == "both" and o.mcid_abs is not None and o.mcid_pct is not None) else (abs_ok or pct_ok):
        v = "improved_meaningful"
    else:
        v = "no_meaningful_change"
    return {"verdict": v, "label": VERDICT_LABEL[v], "delta": round(cur - base, 1), "pct": pct}


def trajectory(session: Session, enc: Encounter, protocol: Protocol) -> dict | None:
    """这位患者这个疗程的恢复轨迹。没有结局定义（例如 v0.1）时返回 None。"""
    outcomes = protocol.course.outcomes
    if not outcomes:
        return None
    encs = [e for e in chain(session, enc) if e.patient_confirmed_at or e.id == enc.id]
    if not encs:
        return None
    root = encs[0]
    visits = []
    for i, e in enumerate(encs):
        facts = current_facts(session, e.id)
        day = max(0, (e.created_at - root.created_at).days)
        row: dict[str, Any] = {"encounter_id": e.id, "day": day, "kind": e.kind, "index": i,
                               "is_current": e.id == enc.id, "values": {}, "regions": _regions(facts, protocol)}
        for o in outcomes:
            f = facts.get(o.key)
            if o.categories:
                val = f.value if f is not None and f.status == FactStatus.PRESENT else None
                row["values"][o.key] = {"value": val, "category": o.categories.get(str(val)) if val is not None else None}
                continue
            v = _num(f)
            sub = None
            if v is None and i == 0:
                for bk in o.baseline_keys:  # 首诊没问到本结局：用替代基线，并注明
                    v = _num(facts.get(bk))
                    if v is not None:
                        sub = bk
                        break
            row["values"][o.key] = {"value": v, "substitute": sub}
        visits.append(row)

    upto = [r for r in visits if r["index"] <= next(r["index"] for r in visits if r["is_current"])]
    cur_row = upto[-1]
    out_rows = []
    for o in outcomes:
        series = [{"day": r["day"], "value": r["values"][o.key]["value"], "encounter_id": r["encounter_id"],
                   "is_current": r["is_current"], **({"category": r["values"][o.key].get("category")} if o.categories else {})}
                  for r in visits]
        if o.categories:
            c = cur_row["values"][o.key].get("category")
            v = {"verdict": c or "insufficient", "label_verdict": CATEGORY_LABEL.get(c or "", VERDICT_LABEL["insufficient"])}
            out_rows.append({"key": o.key, "label": o.label, "categorical": True, "series": series, **v})
            continue
        base = visits[0]["values"][o.key]["value"]
        cur = cur_row["values"][o.key]["value"] if len(upto) > 1 else None
        v = verdict(o, base, cur)
        v["label_verdict"] = v.pop("label")
        out_rows.append({"key": o.key, "label": o.label, "direction": o.direction, "mcid_abs": o.mcid_abs, "mcid_pct": o.mcid_pct,
                         "rule": o.rule, "source": o.source, "baseline": base, "current": cur,
                         "baseline_substitute": visits[0]["values"][o.key].get("substitute"), "series": series, **v})
    base_regions, cur_regions = visits[0]["regions"], cur_row["regions"]
    regions = None
    if base_regions is not None and cur_regions is not None and len(upto) > 1:
        regions = {"baseline": base_regions, "current": cur_regions, "added": sorted(set(cur_regions) - set(base_regions)),
                   "removed": sorted(set(base_regions) - set(cur_regions)), "delta": len(cur_regions) - len(base_regions)}
    return {"baseline_encounter_id": root.id, "day": cur_row["day"], "visit_index": cur_row["index"], "visits": len(visits),
            "outcomes": out_rows, "regions": regions, "reference_curves": protocol.course.reference_curves,
            "simulated": protocol.course.simulated,
            "note": "只比较患者自报的数值与医生设定的阈值，不做预测；人群参考线不是个人预测。"}


def _rule_hit(rule: RecoveryRule, traj: dict) -> dict | None:
    if rule.region_count_increase_gte is not None:
        r = traj.get("regions")
        if r and r["delta"] >= rule.region_count_increase_gte:
            return {"regions_before": len(r["baseline"]), "regions_after": len(r["current"]), "added": r["added"]}
        return None
    row = next((o for o in traj["outcomes"] if o["key"] == rule.outcome), None)
    if not row or row.get("categorical") or row["baseline"] is None or row["current"] is None:
        return None
    base, cur = row["baseline"], row["current"]
    worse = (cur - base) if row["direction"] == "lower_better" else (base - cur)
    if rule.worse_abs is not None and worse >= rule.worse_abs:
        return {"baseline": base, "current": cur, "delta": round(cur - base, 1)}
    if rule.min_day is not None and rule.max_improvement_pct is not None and traj["day"] >= rule.min_day:
        pct = row.get("pct")
        if pct is not None and pct < rule.max_improvement_pct:
            return {"baseline": base, "current": cur, "pct": pct, "day": traj["day"]}
    return None


def evaluate_recovery_rules(session: Session, enc: Encounter, protocol: Protocol) -> list[Task]:
    """签到 / 随访提交时调用：命中医生设定的阈值就建任务（有负责人、有时限），不向患者展示任何判断。"""
    from .tasks import create_routed_task

    if enc.kind != EncounterKind.FOLLOW_UP or not protocol.course.recovery_rules:
        return []
    traj = trajectory(session, enc, protocol)
    if not traj:
        return []
    existing = {(t.detail or {}).get("rule_id") for t in session.exec(select(Task).where(Task.encounter_id == enc.id)).all()}
    made = []
    for rule in protocol.course.recovery_rules:
        if rule.id in existing:
            continue
        hit = _rule_hit(rule, traj)
        if not hit:
            continue
        title = rule.task_title or f"[{rule.severity}] {rule.label}"
        made.append(create_routed_task(session, protocol, enc.id, "recovery_review", title, severity=rule.severity,
                                       route_key="recovery" if rule.severity == "routine" else rule.severity,
                                       assignee_role=rule.assignee_role,
                                       detail={"rule_id": rule.id, "label": rule.label, "slip_line": rule.slip_line,
                                               "day": traj["day"], **hit}))
    return made
