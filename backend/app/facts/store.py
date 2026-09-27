"""事实状态库：所有"患者说了什么"的唯一真相来源。

关键规则：
- 六种状态，见 models.FactStatus；"没问"永远不会变成"没有"。
- 每次变化都是新版本（旧版本 superseded_by 指向新版本），历史可查。
- 已明确的事实遇到不一致的新证据时，不是覆盖，而是进入 conflicting，等待澄清。
- 只有带 is_correction=True 的写入（患者澄清/确认页修改/医生修正）才能覆盖已明确的值。
"""
from __future__ import annotations

from typing import Any, Iterable

from sqlmodel import Session, select

from ..models import Encounter, Fact, FactSource, FactStatus
from ..protocol.schema import FactDef, Protocol


def init_facts(session: Session, encounter: Encounter, protocol: Protocol) -> None:
    for f in protocol.facts:
        session.add(Fact(encounter_id=encounter.id, key=f.key, status=FactStatus.NOT_ASKED,
                         source=FactSource.DERIVED))
    session.commit()


def current_facts(session: Session, encounter_id: str) -> dict[str, Fact]:
    rows = session.exec(select(Fact).where(Fact.encounter_id == encounter_id, Fact.superseded_by.is_(None))).all()
    return {f.key: f for f in rows}


def fact_history(session: Session, encounter_id: str, key: str) -> list[Fact]:
    rows = session.exec(select(Fact).where(Fact.encounter_id == encounter_id, Fact.key == key)
                        .order_by(Fact.version)).all()
    return list(rows)


def as_expr_map(facts: dict[str, Fact]) -> dict[str, tuple[str, Any]]:
    return {k: (f.status, f.value) for k, f in facts.items()}


def _normalize(fdef: FactDef, value: Any) -> Any:
    if value is None:
        return None
    if fdef.type in ("multi_enum", "body_regions"):
        if isinstance(value, str):
            value = [value]
        return sorted(set(str(v) for v in value))
    if fdef.type in ("number", "scale"):
        try:
            v = float(value)
            return int(v) if v.is_integer() else v
        except (TypeError, ValueError):
            return value
    if fdef.type == "bool":
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "是", "有")
        return bool(value)
    return value


def _values_conflict(fdef: FactDef, cur: Fact, new_status: str, new_value: Any) -> bool:
    """判断新证据是否与当前已明确的事实矛盾。"""
    if cur.status in (FactStatus.PRESENT, FactStatus.DENIED) and new_status in (FactStatus.PRESENT, FactStatus.DENIED) \
            and cur.status != new_status:
        return True
    if new_status == FactStatus.UNCERTAIN and cur.status == FactStatus.DENIED:
        return True  # 之前明确否认，现在又"好像有"
    if new_value is None or cur.value is None:
        return False
    if fdef.type in ("multi_enum", "body_regions", "text"):
        return False  # 多选/文本视为补充，不算矛盾（左右侧由 side 事实单独判断）
    return cur.value != new_value


def set_fact(session: Session, encounter: Encounter, protocol: Protocol, key: str, *, status: str,
             value: Any = None, evidence: Iterable[dict] = (), source: str, is_correction: bool = False) -> Fact:
    """写入一条事实证据，返回当前生效的 Fact。"""
    assert status in FactStatus.ALL, status
    fdef = protocol.fact(key)
    value = _normalize(fdef, value)
    evidence = list(evidence)
    facts = current_facts(session, encounter.id)
    cur = facts[key]

    if is_correction or cur.status in (FactStatus.NOT_ASKED, FactStatus.ASKED_UNANSWERED) \
            or (cur.status == FactStatus.UNCERTAIN and status in FactStatus.RESOLVED):
        new = Fact(encounter_id=encounter.id, key=key, status=status, value=value,
                   evidence=(cur.evidence if is_correction and cur.status != FactStatus.CONFLICTING else []) + evidence,
                   source=source, version=cur.version + 1)
        if is_correction and cur.status == FactStatus.CONFLICTING:
            new.evidence = evidence  # 澄清后只保留澄清证据 + 下面附上被采纳候选的证据
            for cand in (cur.value or {}).get("candidates", []):
                if cand.get("value") == value and cand.get("status") == status:
                    new.evidence = cand.get("evidence", []) + evidence
        return _supersede(session, cur, new)

    if cur.status == FactStatus.CONFLICTING:
        cands = list((cur.value or {}).get("candidates", []))
        cands.append({"status": status, "value": value, "evidence": evidence, "source": source})
        new = Fact(encounter_id=encounter.id, key=key, status=FactStatus.CONFLICTING,
                   value={"candidates": cands}, evidence=cur.evidence + evidence, source=source,
                   version=cur.version + 1)
        return _supersede(session, cur, new)

    if cur.status == FactStatus.UNCERTAIN and status == FactStatus.UNCERTAIN:
        new = Fact(encounter_id=encounter.id, key=key, status=status, value=value if value is not None else cur.value,
                   evidence=cur.evidence + evidence, source=source, version=cur.version + 1)
        return _supersede(session, cur, new)

    # cur 已明确（present/denied）
    if _values_conflict(fdef, cur, status, value):
        cands = [
            {"status": cur.status, "value": cur.value, "evidence": cur.evidence, "source": cur.source},
            {"status": status, "value": value, "evidence": evidence, "source": source},
        ]
        new = Fact(encounter_id=encounter.id, key=key, status=FactStatus.CONFLICTING,
                   value={"candidates": cands}, evidence=cur.evidence + evidence, source=source,
                   version=cur.version + 1)
        return _supersede(session, cur, new)

    # 不矛盾：合并证据；多选值取并集
    merged_value = cur.value
    if fdef.type in ("multi_enum", "body_regions") and isinstance(value, list):
        merged_value = sorted(set(cur.value or []) | set(value))
    elif fdef.type == "text" and value and value != cur.value:
        merged_value = f"{cur.value}；{value}" if cur.value else value
    if status == FactStatus.UNCERTAIN:
        status = cur.status  # 已明确的不因模糊补充而降级
    new = Fact(encounter_id=encounter.id, key=key, status=status, value=merged_value,
               evidence=cur.evidence + evidence, source=source, version=cur.version + 1)
    return _supersede(session, cur, new)


def mark_asked_unanswered(session: Session, encounter: Encounter, key: str, evidence: dict, source: str = FactSource.ANSWER) -> Fact:
    facts = current_facts(session, encounter.id)
    cur = facts[key]
    if cur.status != FactStatus.NOT_ASKED:
        return cur  # 已有信息的不降级
    new = Fact(encounter_id=encounter.id, key=key, status=FactStatus.ASKED_UNANSWERED, value=None,
               evidence=[evidence], source=source, version=cur.version + 1)
    return _supersede(session, cur, new)


def is_extraction_only(f: Fact) -> bool:
    """事实目前只来自自由文本抽取（没有身体图、直接回答、修改等其它证据）。"""
    return bool(f.evidence) and all(ev.get("kind") == "free_text" for ev in f.evidence)


def has_direct_answer(f: Fact) -> bool:
    """患者直接回答过这件事（问题回答、红旗一屏）。一键核对里点"对"不算：那是在确认模型的整理，不是直接回答。"""
    return any(ev.get("kind") == "answer" and not str(ev.get("quote", "")).startswith("患者核对") for ev in f.evidence)


def attach_evidence(session: Session, encounter: Encounter, key: str, evidence: dict, source: str | None = None) -> Fact:
    """不改变状态与值，只追加一条证据（例如患者在一键核对中确认了这条整理）。"""
    cur = current_facts(session, encounter.id)[key]
    new = Fact(encounter_id=encounter.id, key=key, status=cur.status, value=cur.value,
               evidence=list(cur.evidence) + [evidence], source=source or cur.source, version=cur.version + 1)
    return _supersede(session, cur, new)


def reject_extracted_fact(session: Session, encounter: Encounter, key: str, evidence: dict) -> Fact:
    """患者在一键核对中说"这条整理不对"：回到"未询问"，让协议问题重新直接问一次。
    旧版本（含被否定的抽取证据）保留在版本链里，供医生追溯；新版本不携带被否定的证据。"""
    cur = current_facts(session, encounter.id)[key]
    new = Fact(encounter_id=encounter.id, key=key, status=FactStatus.NOT_ASKED, value=None,
               evidence=[evidence], source=FactSource.CORRECTION, version=cur.version + 1)
    return _supersede(session, cur, new)


def mark_patient_confirmed(session: Session, encounter_id: str) -> None:
    for f in current_facts(session, encounter_id).values():
        if f.status in (FactStatus.PRESENT, FactStatus.DENIED, FactStatus.UNCERTAIN):
            f.patient_confirmed = True
            session.add(f)
    session.commit()


def _supersede(session: Session, old: Fact, new: Fact) -> Fact:
    session.add(new)
    session.flush()
    old.superseded_by = new.id
    session.add(old)
    session.commit()
    session.refresh(new)
    return new


def fact_to_dict(f: Fact, fdef: FactDef | None = None) -> dict:
    d = {
        "id": f.id, "key": f.key, "status": f.status, "value": f.value, "evidence": f.evidence,
        "source": f.source, "version": f.version, "patient_confirmed": f.patient_confirmed,
    }
    if fdef:
        d["label"] = fdef.label
        d["type"] = fdef.type
        d["category"] = fdef.category
        d["required"] = fdef.required
        d["critical"] = fdef.critical
        d["value_label"] = display_value(fdef, f.status, f.value)
    return d


def display_value(fdef: FactDef, status: str, value: Any) -> str:
    if status == FactStatus.CONFLICTING:
        cands = (value or {}).get("candidates", [])
        return " ↔ ".join(display_value(fdef, c.get("status", "present"), c.get("value")) for c in cands)
    if status == FactStatus.DENIED:
        return "明确否认"
    if status == FactStatus.NOT_ASKED:
        return "未询问"
    if status == FactStatus.ASKED_UNANSWERED:
        return "已询问，未回答"
    if value is None:
        return "有（未给出细节）" if status == FactStatus.PRESENT else "不确定"
    labels = {o.value: o.label for o in fdef.options}
    if isinstance(value, list):
        text = "、".join(labels.get(v, v) for v in value)
    elif isinstance(value, bool):
        text = "是" if value else "否"
    else:
        text = labels.get(str(value), str(value))
    return f"{text}（患者表达不确定）" if status == FactStatus.UNCERTAIN else text
