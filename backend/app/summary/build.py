"""摘要构建：**只**根据事实库生成，每条事实都能点回原始记录。

模型（可选）只参与最后一段叙述，且输入仅为已整理的事实行；
叙述随后接受越界检查（verification.scope_guard）。
"""
from __future__ import annotations

from sqlmodel import Session, select

from ..facts.store import current_facts, display_value, fact_to_dict
from ..llm import get_provider
from ..models import Alert, Encounter, Entry, EntryKind, FactStatus, Summary
from ..protocol.loader import region_index
from ..protocol.schema import Protocol
from ..util import iso
from ..verification.scope import annotate_fact_item, text_flags
from .brief import disputed_red_flags


def region_labels(ids: list | None) -> list[dict]:
    idx = region_index()
    return [{"id": r, "label": idx.get(r, {}).get("label", r)} for r in (ids or [])]


def build_summary_content(session: Session, encounter: Encounter, protocol: Protocol) -> dict:
    facts = current_facts(session, encounter.id)
    fi = protocol.fact_index
    def relevant(k: str) -> bool:  # 随访专用事实只在随访中出现
        return encounter.kind == "follow_up" or fi[k].category != "followup"

    ordered_keys = [k for k in protocol.summary.key_facts_order if k in facts and relevant(k)]
    ordered_keys += [k for k in facts if k not in ordered_keys and relevant(k)]

    alerts = session.exec(select(Alert).where(Alert.encounter_id == encounter.id)).all()
    # 患者否认过的红旗（原话说有、核对时说不对）：单列"待核实"，不进"明确否认"（第三轮评审 T3）
    dmap = {x["key"]: x for x in disputed_red_flags(protocol, facts, alerts)}

    key_facts, denied, unknown, uncertain, conflicts, gaps, disputed = [], [], [], [], [], [], []
    fact_lines = []
    free_text_recorded: list[str] = []
    for k in ordered_keys:
        f, d = facts[k], fi[k]
        item = annotate_fact_item(fact_to_dict(f, d), d, protocol)  # 患者原话里的药名/剂量/疑似指令加标记
        if k in dmap:
            x = dmap[k]
            disputed.append({**item, "quotes": x["quotes"], "now": x["now"], "rule_label": x["rule_label"],
                             "severity": x["severity"], "evidence": x["evidence"] + list(item.get("evidence") or [])})
            fact_lines.append(f"{d.label}：原话曾提到，患者核对时表示不对，{x['now']}（待核实）")
            if f.status in FactStatus.UNKNOWN:
                unknown.append(item)
                if d.required:
                    gaps.append(item)
            continue
        if f.status == FactStatus.PRESENT:
            key_facts.append(item)
            if d.category == "medication" or d.type == "text":
                # 叙述是"系统生成文字"，不携带患者自由文本/药名（避免被当作建议，也让越界检查保持严格）；
                # 原文在事实表中带出处展示。
                free_text_recorded.append(d.label)
            else:
                fact_lines.append(f"{d.label}：{item['value_label']}")
        elif f.status == FactStatus.DENIED:
            denied.append(item)
            fact_lines.append(f"{d.label}：明确否认")
        elif f.status == FactStatus.UNCERTAIN:
            uncertain.append(item)
            fact_lines.append(f"{d.label}：{item['value_label']}")
        elif f.status == FactStatus.CONFLICTING:
            conflicts.append(item)
        else:
            unknown.append(item)
            if d.required:
                gaps.append(item)
                fact_lines.append(f"{d.label}：未明确（{item['value_label']}）")

    bm = protocol.body_map
    body_map = {
        "primary": region_labels(facts[bm.regions_fact_key].value if facts[bm.regions_fact_key].status == FactStatus.PRESENT else []),
        "radiation": region_labels(facts[bm.radiation_fact_key].value if bm.radiation_fact_key and facts[bm.radiation_fact_key].status == FactStatus.PRESENT else []),
        "side": display_value(fi[bm.side_fact_key], facts[bm.side_fact_key].status, facts[bm.side_fact_key].value),
    }

    def v(key: str) -> str:
        return display_value(fi[key], facts[key].status, facts[key].value) if key in facts else "—"

    def known(key: str) -> bool:
        return key in facts and facts[key].status in (FactStatus.PRESENT, FactStatus.UNCERTAIN)

    # 一句话主诉只写已知项，未知的只报个数（第三轮评审：旧版在未知项多时满屏"已询问，未回答"）
    if encounter.kind == "follow_up":
        spec = [("fu_change_overall", lambda: f"整体 {v('fu_change_overall')}"),
                ("severity_now", lambda: f"当前疼痛 {v('severity_now')}/10"),
                ("fu_new_symptom", lambda: "有新情况" if facts["fu_new_symptom"].status == FactStatus.PRESENT else f"新情况 {v('fu_new_symptom')}")]
        head = "随访"
    else:
        spec = [("onset_timing", lambda: f"开始 {v('onset_timing')}"), ("onset_mode", lambda: v("onset_mode")),
                ("trigger", lambda: f"诱因 {v('trigger')}"), ("severity_now", lambda: f"目前程度 {v('severity_now')}/10"),
                ("course", lambda: f"趋势 {v('course')}")]
        side_known = facts[bm.side_fact_key].status in (FactStatus.PRESENT, FactStatus.UNCERTAIN)
        head = protocol.summary.chief_complaint_label + (f"（{body_map['side']}）" if side_known else "")
    parts, missing = [], 0
    for key, fmt in spec:
        if key not in facts:
            continue
        if known(key) or (key == "fu_new_symptom" and facts[key].status == FactStatus.DENIED):
            parts.append("无新情况" if facts[key].status == FactStatus.DENIED else fmt())
        else:
            missing += 1
    headline = head + ("：" if encounter.kind == "follow_up" else "；") + "，".join(parts) if parts else head
    if missing:
        headline += f"；另有 {missing} 项未明确"
    quotes = [{"entry_id": e.id, "text": e.payload.get("text", ""), "at": iso(e.created_at),
               **({"flags": fl} if (fl := text_flags(e.payload.get("text", ""), protocol)) else {})}
              for e in session.exec(select(Entry).where(Entry.encounter_id == encounter.id,
                                                        Entry.kind == EntryKind.FREE_TEXT).order_by(Entry.seq)).all()]

    if free_text_recorded:
        fact_lines.append("另有患者自述记录：" + "、".join(free_text_recorded) + "（见事实表原文；系统不解读、不建议）")
    provider = get_provider()
    narrative = provider.narrative(fact_lines, protocol) if protocol.summary.narrative_enabled else ""

    return {
        "headline": headline,
        "body_map": body_map,
        "key_facts": key_facts,
        "denied": denied,
        "uncertain": uncertain,
        "unknown": unknown,
        "gaps": gaps,
        "conflicts": conflicts,
        "disputed": disputed,
        "alerts": [{"id": a.id, "rule_id": a.rule_id, "severity": a.severity, "label": a.label, "evidence": a.evidence}
                   for a in alerts],
        "quotes": quotes,
        "narrative": narrative,
        "narrative_provider": getattr(provider, "last_used", provider.name),
        "based_on_fact_ids": [facts[k].id for k in ordered_keys],
        "doctor_edits": {},
    }


def create_summary_version(session: Session, encounter: Encounter, content: dict, author: str, note: str | None = None) -> Summary:
    last = session.exec(select(Summary).where(Summary.encounter_id == encounter.id).order_by(Summary.version.desc())).first()
    s = Summary(encounter_id=encounter.id, version=(last.version + 1) if last else 1, author=author, content=content, note=note)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def latest_summary(session: Session, encounter_id: str) -> Summary | None:
    return session.exec(select(Summary).where(Summary.encounter_id == encounter_id).order_by(Summary.version.desc())).first()
