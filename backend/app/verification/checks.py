"""验收模块：检查系统状态与承诺是否一致。

它证明的是"指定约束得到满足"，不是"医学判断正确"。
每项检查：id、label、severity、passed、details。总体 passed = 没有 critical 失败。
"""
from __future__ import annotations

import re

from sqlmodel import Session, select

from ..facts.store import current_facts, fact_history
from ..models import (Alert, AskedQuestion, Encounter, Entry, EntryKind, FactStatus, Notification, NotificationStatus,
                      Summary, Task, TaskStatus, VerificationReport)
from ..protocol.schema import Protocol
from ..summary.build import latest_summary
from .scope import _texts, is_patient_words, text_flags


def _check(id_: str, label: str, severity: str, failures: list[str]) -> dict:
    return {"id": id_, "label": label, "severity": severity, "passed": not failures, "details": failures}


def run_checks(session: Session, encounter: Encounter, protocol: Protocol, persist: bool = True) -> VerificationReport:
    """persist=False：只计算不落库（医生端浏览时用），避免每次刷新都新增一份报告、让"最新报告"语义漂移。"""
    facts = current_facts(session, encounter.id)
    fi = protocol.fact_index
    entries = {e.id: e for e in session.exec(select(Entry).where(Entry.encounter_id == encounter.id)).all()}
    summary = latest_summary(session, encounter.id)
    content = summary.content if summary else {}
    checks: list[dict] = []

    # V1 出处：每个 present/denied/uncertain 事实都有证据，且证据指向存在的原始记录
    fails = []
    for k, f in facts.items():
        if f.status in (FactStatus.PRESENT, FactStatus.DENIED, FactStatus.UNCERTAIN, FactStatus.CONFLICTING):
            if not f.evidence:
                fails.append(f"{fi[k].label}({k}) 没有证据")
            for ev in f.evidence:
                if ev.get("entry_id") not in entries:
                    fails.append(f"{fi[k].label}({k}) 引用了不存在的记录 {ev.get('entry_id')}")
    checks.append(_check("V1_provenance", "每条事实都有可回溯的原始记录", "critical", fails))

    # V2 不自动补全：未问/未答的事实没有值；摘要"明确否认"只包含 denied
    fails = []
    for k, f in facts.items():
        if f.status in FactStatus.UNKNOWN and f.value is not None:
            fails.append(f"{fi[k].label}({k}) 状态为{f.status}却带有值")
    for item in content.get("denied", []):
        if facts.get(item["key"]) and facts[item["key"]].status != FactStatus.DENIED:
            fails.append(f"摘要把 {item['label']} 列为明确否认，但事实状态是 {facts[item['key']].status}")
    for k, f in facts.items():
        if encounter.kind != "follow_up" and fi[k].category == "followup":
            continue
        if fi[k].required and f.status in FactStatus.UNKNOWN and not any(g["key"] == k for g in content.get("gaps", [])) and content:
            fails.append(f"关键事实 {fi[k].label} 未明确，但摘要没有列入缺口")
    checks.append(_check("V2_no_autocomplete", "未问不等于没有：未知事实不被补全", "critical", fails))

    # V3 引文完整：文字证据的 quote 必须逐字出现在原始记录中
    fails = []
    for k, f in facts.items():
        for ev in f.evidence:
            e = entries.get(ev.get("entry_id"))
            if e and e.kind == EntryKind.FREE_TEXT and ev.get("quote") and ev["quote"] not in e.payload.get("text", ""):
                fails.append(f"{fi[k].label}({k}) 的引文不在原文中：{ev['quote'][:30]}")
    checks.append(_check("V3_quote_integrity", "引文逐字来自患者原话", "critical", fails))

    # V4 越界：系统生成的面向患者/医生的文字不含诊断/用药内容
    fails = []
    patterns = [re.compile(p) for p in protocol.scope_guard.forbidden_patterns]
    texts = [("摘要叙述", content.get("narrative", ""))]
    for aq in session.exec(select(AskedQuestion).where(AskedQuestion.encounter_id == encounter.id)).all():
        if aq.kind in ("clarification", "verification"):
            texts.append((f"{'澄清' if aq.kind == 'clarification' else '核对'}问题 {aq.question_id}", aq.text))
    for n in session.exec(select(Notification).where(Notification.encounter_id == encounter.id)).all():
        if not (n.history and n.history[0].get("by", "").startswith("doctor")):
            texts.append((f"通知 {n.id}", n.content))
    for name, t in texts:
        for p in patterns:
            if t and p.search(t):
                fails.append(f"{name} 命中越界规则 /{p.pattern}/")
    # 由"改写"起草、医生发送的说明（第三轮评审 T5）：医生自己写的话不查，但改写带进来的、医生要点里没有的医学内容
    # 必须已被删掉或有医生写的理由；模型改写过的必须带 AI 标注
    plan = encounter.followup_plan or {}
    if plan.get("draft_id"):
        from ..models import AuditLog
        from ..services.encounter import remaining_new_terms
        from .rewrite_guard import AI_LABEL, describe
        log = session.get(AuditLog, plan["draft_id"])
        notes = (log.detail or {}).get("notes", "") if log else ""
        msg = plan.get("patient_message", "")
        rest = remaining_new_terms(protocol, notes, msg, plan.get("interval_days"))
        if rest and not (plan.get("override_reason") or "").strip():
            fails.append(f"改写起草的说明含医生要点以外的内容且没有医生理由：{describe(rest)}")
        if plan.get("ai_assisted") and AI_LABEL not in msg:
            fails.append("模型改写过的说明缺少 AI 标注")
    # 患者原话（text 类 / 用药类事实的值）不算系统生成文字、不阻断，但命中越界词或疑似指令时，摘要里必须带"患者原话"标记，
    # 否则医生可能把"建议布洛芬400mg每日3次"读成系统结论（第二轮评审 T1）
    for bucket in ("key_facts", "uncertain", "conflicts"):
        for item in content.get(bucket, []):
            fdef = fi.get(item.get("key"))
            if not fdef or not is_patient_words(fdef):
                continue
            expected = {f["code"] for t in _texts(item.get("value")) for f in text_flags(t, protocol)}
            got = {f.get("code") for f in item.get("flags", [])}
            if expected - got:
                fails.append(f"摘要中 {item.get('label')} 的患者原话含药名/剂量/诊断性表述或疑似指令，但未标注为患者原话")
    checks.append(_check("V4_scope_guard", "系统生成文字不含诊断/处方/剂量；患者原话中的此类内容已标注", "critical", fails))

    # V5 矛盾呈现：所有 conflicting 事实必须出现在摘要 conflicts 中；患者否认过的红旗（原话说有、核对时说不对）
    # 必须出现在摘要"待核实"里，且不能被列为"明确否认"（第三轮评审 T3）
    fails = []
    if content:
        shown = {c["key"] for c in content.get("conflicts", [])}
        for k, f in facts.items():
            if f.status == FactStatus.CONFLICTING and k not in shown:
                fails.append(f"{fi[k].label}({k}) 存在矛盾但摘要未呈现")
        from ..summary.brief import disputed_red_flags
        alerts_now = session.exec(select(Alert).where(Alert.encounter_id == encounter.id)).all()
        disputed_shown = {x.get("key") for x in content.get("disputed", [])}
        denied_shown = {x.get("key") for x in content.get("denied", [])}
        for x in disputed_red_flags(protocol, facts, alerts_now):
            if x["key"] not in disputed_shown:
                fails.append(f"{x['label']}({x['key']}) 原话提到、患者核对时否认，但摘要没有列为待核实")
            if x["key"] in denied_shown:
                fails.append(f"{x['label']}({x['key']}) 原话提到、患者核对时否认，摘要却列为明确否认")
    checks.append(_check("V5_conflict_surfaced", "矛盾与患者否认过的红旗必须呈现给医生，不能自动取其一", "major", fails))

    # V6 红旗处理：每条触发的红旗都有任务；需要提示的已向患者展示；任务不能被系统标记完成
    fails = []
    alerts = session.exec(select(Alert).where(Alert.encounter_id == encounter.id)).all()
    tasks = session.exec(select(Task).where(Task.encounter_id == encounter.id)).all()
    for a in alerts:
        rule = next((r for r in protocol.red_flags if r.id == a.rule_id), None)
        if not any(t.alert_id == a.id for t in tasks):
            fails.append(f"红旗 {a.label} 没有对应任务")
        if rule and rule.action == "immediate_notice_and_task" and not a.notice_entry_id:
            fails.append(f"红旗 {a.label} 未向患者展示提示")
    for t in tasks:
        for h in t.history:
            if h.get("to") == TaskStatus.COMPLETED and (not h.get("by") or h["by"] == "system"):
                fails.append(f"任务 {t.title} 被非人工标记为完成")
    checks.append(_check("V6_red_flag_handling", "红旗有提示、有任务、完成需人工", "critical", fails))

    # V7 通知状态：已发送≠已看到≠已确认；状态流转合法
    fails = []
    for n in session.exec(select(Notification).where(Notification.encounter_id == encounter.id)).all():
        prev = NotificationStatus.QUEUED
        for h in n.history:
            if h.get("to") not in NotificationStatus.TRANSITIONS.get(prev, set()) | {prev}:
                fails.append(f"通知 {n.id} 非法流转 {prev}→{h.get('to')}")
            prev = h.get("to", prev)
        if n.status in (NotificationStatus.SEEN, NotificationStatus.ACKNOWLEDGED) and not any(
                h.get("to") == n.status and h.get("by", "").startswith("patient") for h in n.history):
            fails.append(f"通知 {n.id} 的 {n.status} 不是由患者端记录的")
    checks.append(_check("V7_notification_state", "发送、看到、理解、执行分开记录", "major", fails))

    # V8 版本完整：摘要版本单调、系统版保留；事实历史链完整
    fails = []
    sums = session.exec(select(Summary).where(Summary.encounter_id == encounter.id).order_by(Summary.version)).all()
    if sums:
        if [s.version for s in sums] != list(range(1, len(sums) + 1)):
            fails.append("摘要版本号不连续")
        if sums[0].author != "system":
            fails.append("最早的摘要版本不是系统版本（原始摘要被覆盖）")
    for k in facts:
        hist = fact_history(session, encounter.id, k)
        if [h.version for h in hist] != list(range(1, len(hist) + 1)):
            fails.append(f"{fi[k].label}({k}) 版本链断裂")
        if sum(1 for h in hist if h.superseded_by is None) != 1:
            fails.append(f"{fi[k].label}({k}) 生效版本不唯一")
    checks.append(_check("V8_version_integrity", "修改产生新版本，旧版本保留", "major", fails))

    # V9 确认门槛：医生确认前必须有患者确认；确认后不应仍有未澄清矛盾
    fails = []
    if encounter.doctor_confirmed_at and not encounter.patient_confirmed_at:
        fails.append("医生已确认但患者从未确认自己的表达")
    if encounter.doctor_confirmed_at and any(f.status == FactStatus.CONFLICTING for f in facts.values()):
        fails.append("医生确认时仍有未澄清的矛盾事实")
    checks.append(_check("V9_confirmation_gate", "确认顺序：患者确认事实 → 医生核对", "critical", fails))

    passed = all(c["passed"] for c in checks if c["severity"] == "critical")
    report = VerificationReport(encounter_id=encounter.id, passed=passed, checks=checks)
    if persist:
        session.add(report)
        session.commit()
        session.refresh(report)
    return report


def latest_report(session: Session, encounter_id: str) -> VerificationReport | None:
    return session.exec(select(VerificationReport).where(VerificationReport.encounter_id == encounter_id)
                        .order_by(VerificationReport.created_at.desc())).first()
