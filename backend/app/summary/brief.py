"""接诊速览、紧急程度分级、病历初稿：让医生不用把所有东西都看一遍。

全部是**确定性整理**，不调用模型、不做诊断：
- 紧急程度：只看已触发的红旗规则（协议定义）；患者核对时否认的紧急红旗降为"当天电话确认"。
- 面诊要当面确认的事：从矛盾、表达不确定、关键事实未明确里按固定优先级挑前几条。
- 病历初稿：只用患者确认过的事实拼成主诉 / 现病史 / 阴性 / 未明确；用药等患者原话放进「」并注明未经核实。
AI 在这里的角色仍是上游那一步——把患者口语抽成事实；这里只是把事实排好、写成医生能直接用的格式。
"""
from __future__ import annotations

from typing import Optional

from ..facts.store import display_value
from ..models import Alert, Encounter, Fact, FactStatus, Task, TaskStatus
from ..protocol.schema import FactDef, Protocol
from ..verification.scope import is_patient_words, text_flags

TRIAGE = {
    "urgent": (0, "紧急：请立即电话联系患者"),
    "same_day": (1, "当天联系"),
    "routine": (2, "常规复核"),
    None: (3, "未触发红旗"),
}
SEV_LABEL = {"urgent": "紧急", "same_day": "当天联系", "routine": "常规复核"}
_SEV_ORDER = ["urgent", "same_day", "routine"]


def triage_of(alerts: list[Alert]) -> Optional[str]:
    """已触发红旗的最高级别。患者核对时否认的红旗仍按原级别计：原话说有、后来说没有，是需要人核实的矛盾；
    误报的代价是一个电话，漏报的代价可能是永久损伤（第三轮评审 T3：旧版把它降成"当天联系"）。"""
    levels = {a.severity for a in alerts}
    for s in _SEV_ORDER:
        if s in levels:
            return s
    return None


def triage_disputed_only(alerts: list[Alert]) -> bool:
    """最高级别的红旗是否全部是"患者核对时否认"的——列表与速览据此提示"请电话核实"。"""
    level = triage_of(alerts)
    top = [a for a in alerts if a.severity == level]
    return bool(level) and bool(top) and all(a.patient_disputed for a in top)


def triage_label(alerts: list[Alert]) -> str:
    level = triage_of(alerts)
    if triage_disputed_only(alerts):
        return f"{SEV_LABEL[level]}：患者核对时否认，请尽快电话核实"
    return TRIAGE[level][1]


_NOW_TEXT = {
    FactStatus.DENIED: "直接问时回答“没有”",
    FactStatus.NOT_ASKED: "之后没有再问到",
    FactStatus.ASKED_UNANSWERED: "直接问时回答“不清楚”或跳过",
    FactStatus.UNCERTAIN: "直接问时表示不确定",
}


def disputed_red_flags(protocol: Protocol, facts: dict[str, Fact], alerts: list[Alert]) -> list[dict]:
    """患者否认过的红旗：原话里抽到了"有"、患者在一键核对里说"不对"，之后没有被直接回答再次确认（再次确认时红旗会重新生效）。
    这是最危险的一类矛盾，系统不替患者取其一：分级按原级别、速览置顶、摘要单列"待核实"、病历初稿不写"否认"。"""
    rules = {r.id: r for r in protocol.red_flags}
    out, seen = [], set()
    for a in alerts:
        if not a.patient_disputed:
            continue
        rule = rules.get(a.rule_id)
        keys = set(rule.fact_keys) if rule else set()
        for ev in a.evidence or []:
            k = ev.get("fact_key")
            if k in seen or k not in facts or k not in protocol.fact_index or (keys and k not in keys):
                continue
            text_ev = [e2 for e2 in ev.get("evidence") or [] if e2.get("kind") == "free_text" and e2.get("quote")]
            if not text_ev:
                continue
            seen.add(k)
            f, d = facts[k], protocol.fact(k)
            out.append({"key": k, "label": d.label, "record_label": rlab(d), "rule_id": a.rule_id, "rule_label": a.label,
                        "severity": a.severity, "status": f.status, "now": _NOW_TEXT.get(f.status, display_value(d, f.status, f.value)),
                        "quotes": list(dict.fromkeys(e2["quote"] for e2 in text_ev)), "evidence": text_ev})
    return out


def rlab(d: FactDef) -> str:
    return d.record_label or d.label


def _relevant(enc: Encounter, d: FactDef) -> bool:
    return enc.kind == "follow_up" or d.category != "followup"


def _ordered_keys(protocol: Protocol, facts: dict[str, Fact]) -> list[str]:
    first = [k for k in protocol.summary.key_facts_order if k in facts]
    return first + [k for k in facts if k not in first]


def confirm_items(protocol: Protocol, enc: Encounter, facts: dict[str, Fact], disputed: Optional[list[dict]] = None) -> list[dict]:
    """面诊时要当面确认的事，按优先级：患者否认过的红旗 > 矛盾 > 关键事实表达不确定 > 关键事实未明确 > 必填未明确 > 其它不确定。"""
    fi = protocol.fact_index
    ranked: list[tuple[int, dict]] = []
    done = set()
    for x in disputed or []:
        done.add(x["key"])
        ranked.append((-1, {"key": x["key"], "label": x["record_label"], "kind": "disputed",
                            "detail": f"原话提到「{x['quotes'][0]}」，核对时说不对，{x['now']}；请电话核实"}))
    for k in _ordered_keys(protocol, facts):
        f, d = facts[k], fi[k]
        if not _relevant(enc, d) or k in done:
            continue
        base = {"key": k, "label": rlab(d)}
        if f.status == FactStatus.CONFLICTING:
            ranked.append((0, {**base, "kind": "conflict", "detail": "前后说法不一致：" + display_value(d, f.status, f.value)}))
        elif f.status == FactStatus.UNCERTAIN and (d.critical or d.category == "red_flag"):
            ranked.append((1, {**base, "kind": "uncertain", "detail": "患者表达不确定"}))
        elif f.status in FactStatus.UNKNOWN and d.critical:
            ranked.append((2, {**base, "kind": "gap", "detail": "未询问" if f.status == FactStatus.NOT_ASKED else "问了没答"}))
        elif f.status in FactStatus.UNKNOWN and d.required:
            ranked.append((3, {**base, "kind": "gap", "detail": "未询问" if f.status == FactStatus.NOT_ASKED else "问了没答"}))
        elif f.status == FactStatus.UNCERTAIN:
            ranked.append((4, {**base, "kind": "uncertain", "detail": "患者表达不确定"}))
    ranked.sort(key=lambda x: x[0])  # 同一优先级内保持协议顺序
    return [i for _, i in ranked]


def visit_brief(protocol: Protocol, enc: Encounter, facts: dict[str, Fact], alerts: list[Alert], tasks: list[Task],
                summary_out: Optional[dict], top_n: int = 3) -> dict:
    level = triage_of(alerts)
    rank = TRIAGE[level][0]
    label = triage_label(alerts)
    items = confirm_items(protocol, enc, facts, disputed_red_flags(protocol, facts, alerts))
    if summary_out:
        headline = summary_out["content"].get("headline", "")
        note = "患者尚未确认，以下为临时整理" if summary_out.get("provisional") else ""
    else:
        headline = f"{protocol.summary.chief_complaint_label}：患者尚未完成填写"
        note = "患者还在填写，摘要在患者确认后生成"
    red_flags = [{"label": a.label, "severity": a.severity, "severity_label": SEV_LABEL.get(a.severity, a.severity),
                  "disputed": bool(a.patient_disputed), "notice_shown": bool(a.notice_entry_id)}
                 for a in sorted(alerts, key=lambda a: _SEV_ORDER.index(a.severity) if a.severity in _SEV_ORDER else 9)]
    return {"triage": level, "triage_rank": rank, "triage_label": label, "triage_disputed": triage_disputed_only(alerts),
            "headline": headline, "note": note,
            "red_flags": red_flags, "confirm_items": items[:top_n], "confirm_more": max(0, len(items) - top_n),
            "open_tasks": sum(1 for t in tasks if t.status != TaskStatus.COMPLETED)}


def _side_prefix(protocol: Protocol, facts: dict[str, Fact]) -> str:
    k = protocol.body_map.side_fact_key
    f = facts.get(k)
    if not f or f.status != FactStatus.PRESENT:
        return ""
    v = display_value(protocol.fact(k), f.status, f.value)
    return {"左侧": "左侧", "右侧": "右侧", "两侧": "双侧"}.get(v, "")


def record_draft(protocol: Protocol, enc: Encounter, facts: dict[str, Fact], alerts: list[Alert],
                 eligibility: Optional[dict], confirmed: bool, when: str) -> dict:
    """门诊病历初稿（主诉 + 现病史 + 阴性 + 未明确 + 自述用药 + 红旗）。只用事实库里的内容，不做诊断。"""
    fi = protocol.fact_index
    bm = protocol.body_map
    used_in_cc = {bm.side_fact_key, "onset_timing", "radiation_present", bm.radiation_fact_key}

    def val(k: str) -> str:
        return display_value(fi[k], facts[k].status, facts[k].value)

    # 主诉：侧别 + 主诉名称 + 放射 + 病程
    cc = _side_prefix(protocol, facts) + protocol.summary.chief_complaint_label
    rk = bm.radiation_fact_key
    if rk and rk in facts and facts[rk].status == FactStatus.PRESENT:
        cc += f"，伴放射至{val(rk)}"
    elif "radiation_present" in facts and facts["radiation_present"].status == FactStatus.PRESENT:
        cc += "，伴放射痛"
    if "onset_timing" in facts and facts["onset_timing"].status == FactStatus.PRESENT:
        cc += f"，病程 {val('onset_timing')}"
    cc += "。"

    disputed = disputed_red_flags(protocol, facts, alerts)
    dkeys = {x["key"] for x in disputed}
    rf_keys = {k for r in protocol.red_flags for k in r.fact_keys} | {k for k, d in fi.items() if d.category == "red_flag"}
    present, negatives, uncertain, unknown, patient_words = [], [], [], [], []
    rf_negatives = []
    for k in _ordered_keys(protocol, facts):
        f, d = facts[k], fi[k]
        if not _relevant(enc, d) or k in dkeys:  # 患者否认过的红旗单独写进"需核实"，不写"否认"
            continue
        if f.status == FactStatus.PRESENT:
            if is_patient_words(d):
                flags = [fl["label"].removeprefix("患者原话，") for t in ([f.value] if isinstance(f.value, str) else [])
                         for fl in text_flags(t, protocol)]
                patient_words.append(f"{rlab(d)}：「{f.value}」（患者原话，未经核实{'；' + '；'.join(flags) if flags else ''}）")
            elif k in used_in_cc:
                continue
            elif d.type == "bool":
                present.append(f"有{rlab(d)}")
            else:
                present.append(f"{rlab(d)}：{val(k)}")
        elif f.status == FactStatus.DENIED:
            negatives.append(rlab(d))
            if k in rf_keys:
                rf_negatives.append(rlab(d))
        elif f.status == FactStatus.UNCERTAIN:
            uncertain.append(rlab(d) if f.value is None or d.type == "bool" else f"{rlab(d)}（{val(k)}）")
        elif f.status == FactStatus.CONFLICTING:
            uncertain.append(f"{rlab(d)}（前后说法不一致：{val(k)}）")
        elif d.required or d.critical:
            unknown.append(rlab(d))

    hpi = "患者就诊前自述并确认：" + ("；".join(present) if present else "（无更多已明确的信息）") + "。"
    sections = [{"title": "主诉", "text": cc}, {"title": "现病史", "text": hpi}]
    if disputed:
        sections.append({"title": "需核实（红旗）", "text": "；".join(
            f"{x['record_label']}：原话提到「{'」「'.join(x['quotes'])}」，核对时患者表示不对，{x['now']}；面诊请当面复核"
            for x in disputed) + "。"})
    if negatives:
        # 出处写在段内：医生复制时常删掉页脚，"否认"必须能看出来自患者问卷，而不是医生问诊的结论
        text = "患者就诊前问卷中否认：" + "、".join(negatives) + "。"
        if rf_negatives:
            text += "其中" + "、".join(rf_negatives) + "与红旗相关，面诊请当面复核。"
        sections.append({"title": "阴性（患者问卷）", "text": text})
    if uncertain:
        sections.append({"title": "表达不确定", "text": "、".join(uncertain) + "。"})
    if unknown:
        sections.append({"title": "未明确（面诊补问）", "text": "、".join(unknown) + "。"})
    if patient_words:
        sections.append({"title": "患者原话", "text": "；".join(patient_words) + "。"})
    if alerts:
        rf = "；".join(f"{a.label}（{SEV_LABEL.get(a.severity, a.severity)}{'，患者核对时否认，需电话确认' if a.patient_disputed else ''}）"
                       for a in alerts)
        sections.append({"title": "红旗", "text": rf + "。"})
    else:
        sections.append({"title": "红旗", "text": "未触发协议红旗规则。"})
    if eligibility and eligibility.get("attested"):
        sections.append({"title": "适用范围", "text": "患者在开始页确认：" + "；".join(i["text"] for i in eligibility.get("items", [])) + "。"})
    footer = (f"以上根据患者就诊前自述与确认整理（{when}{'，患者尚未确认，为临时整理' if not confirmed else ''}），"
              "不含诊断与处理意见；查体、诊断与处理请医生补充后使用。")
    text = "\n".join(f"【{s['title']}】{s['text']}" for s in sections) + "\n" + footer
    return {"sections": sections, "footer": footer, "text": text, "provisional": not confirmed}
