#!/usr/bin/env python3
"""离线场景评测运行器（用法见 eval/README.md）。

两层结果：
  - 抽取层（X 码）：患者原话刚被模型抽取、还没经过一键核对和问卷时的状态——衡量"模型本身"，
    也是"患者不认真核对"时的最坏情况；
  - 最终记录（E 码）：模拟一位认真的患者走完核对与问卷、确认之后，医生看到的记录——衡量"系统整体"。
压力集（--split stress）额外计算抽取层漏抽（X1）与原话层红旗漏识别（X4）。

示例：
  python eval/runner.py --split all                         # mock 基线
  python eval/runner.py --split stress --provider anthropic # 真实模型（需 ANTHROPIC_API_KEY）
  python eval/runner.py --split all --provider compat --workers 4   # 国产模型（需 TIJI_COMPAT_*）
  python eval/runner.py --split stress --provider ollama --workers 1 # 本机模型（需 TIJI_OLLAMA_MODEL，数据不出本机）
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import statistics
import sys
import tempfile
import time
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCEN_DIR = ROOT / "eval" / "scenarios"
PRICE_PER_MTOK = {  # 美元 / 百万 token（input, output, cache_read, cache_write）；仅用于估算
    "claude-opus-5": (5.0, 25.0, 0.5, 6.25),
}
USD_CNY = 7.1  # 估算用汇率假设（报告里写明），不是实时汇率


# ---------------------------------------------------------------- 环境（必须在导入 app 之前设置）
def _configure_env(args, worker_tag: str = "main") -> None:
    os.environ["TIJI_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix=f'tiji_eval_{worker_tag}_')}/eval.db"
    os.environ["TIJI_LLM_PROVIDER"] = args["provider"]
    if args["provider"] != "mock":
        os.environ["TIJI_LLM_FALLBACK"] = "none"  # 评测不兜底：失败要如实暴露
    if args.get("effort"):
        os.environ["TIJI_ANTHROPIC_EFFORT_EXTRACT"] = args["effort"]
    if args.get("protocol"):
        os.environ["TIJI_DEFAULT_PROTOCOL"] = args["protocol"]
        os.environ["TIJI_EVAL_FORCE_PROTOCOL"] = args["protocol"]  # 显式指定时覆盖场景文件里写的协议（例如用 v0.1 的场景评 v0.2）
    sys.path.insert(0, str(ROOT / "backend"))


def _app():
    """延迟导入 app（环境变量设置之后）。"""
    from app import models
    from app.config import settings
    from app.db import init_db, session_scope
    from app.facts.store import current_facts
    from app.llm import provider as llm
    from app.protocol import get_protocol
    from app.services import encounter as svc
    from app.summary.build import latest_summary
    from app.verification.checks import latest_report
    return dict(models=models, settings=settings, init_db=init_db, session_scope=session_scope, current_facts=current_facts,
                llm=llm, get_protocol=get_protocol, svc=svc, latest_summary=latest_summary, latest_report=latest_report)


# ---------------------------------------------------------------- 场景加载
def load_items(split: str) -> list[dict]:
    import yaml
    items = []
    if split in ("stress", "redflag", "holdout"):
        # 句子级集合（同一格式）：stress = 口语压力集（开发集）；redflag = 红旗换说法（开发集）；holdout = 留出集（冻结后才跑）
        for p in sorted((SCEN_DIR / split).glob("*.yaml")):
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
            for it in doc["items"]:
                it = dict(it)
                fam = it.get("family") or (it.get("tags") or ["x"])[0]
                it.update(_path=str(p.relative_to(ROOT)), _kind="stress", split=split, kind="pre_visit",
                          protocol_id=doc.get("protocol_id"), family=f"{split}_{fam}" if split != "stress" else f"stress_{it['id']}",
                          category=",".join(it.get("tags", [])), title=it["text"][:30])
                items.append(it)
        return items
    dirs = ["dev", "locked"] if split == "all" else [split]
    for d in dirs:
        for p in sorted((SCEN_DIR / d).glob("*.yaml")):
            sc = yaml.safe_load(p.read_text(encoding="utf-8"))
            sc["_path"] = str(p.relative_to(ROOT))
            sc["_kind"] = "scenario"
            items.append(sc)
    return items


def apply_overlay(items: list[dict], protocol_id: str) -> int:
    """用 eval/scenarios/overlays/<协议>.yaml 调整期望（协议变了、期望必须跟着变的条目，每条写理由）。返回调整条数。"""
    import yaml
    path = SCEN_DIR / "overlays" / f"{protocol_id}.yaml"
    if not path.exists():
        return 0
    ov = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("scenarios") or {}
    n = 0
    for it in items:
        o = ov.get(it.get("id"))
        if not o:
            continue
        gt = it.setdefault("ground_truth", {}) if it.get("_kind") == "scenario" else it
        exp = list(gt.get("expected_alerts") or [])
        exp = [a for a in exp if a not in (o.get("expected_alerts_remove") or [])] + \
              [a for a in (o.get("expected_alerts_add") or []) if a not in exp]
        gt["expected_alerts"] = exp
        if "forbidden_output_patterns" in o:
            gt["forbidden_output_patterns"] = o["forbidden_output_patterns"]
        for k, v in (o.get("truth") or {}).items():
            (gt.setdefault("facts", {}) if it.get("_kind") == "scenario" else gt.setdefault("truth", {}))[k] = v
        it["_overlay"] = o.get("reason")
        n += 1
    return n


# ---------------------------------------------------------------- 取值比较
def _norm(v):
    if isinstance(v, list):
        return sorted(str(x) for x in v)
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    return v


def value_matches(ftype: str, system_value, exp: dict, subset: bool) -> bool:
    if "value_any" in exp:
        return any(value_matches(ftype, system_value, {"value": v}, subset) for v in exp["value_any"])
    ev = exp.get("value")
    if ev is None:
        return True
    if ftype == "text":
        s = str(system_value or "")
        return all(part.strip() in s for part in str(ev).split("；") if part.strip())
    if ftype in ("multi_enum", "body_regions") and subset:
        return set(_norm(ev)) <= set(_norm(system_value or []))
    return _norm(system_value) == _norm(ev)


# ---------------------------------------------------------------- 模拟患者
class Patient:
    """诚实的模拟患者：按脚本回答问题。一键核对有两种模式：
    - attentive（认真）：对照自己的真实情况（truth）判断对不对。注意这等于"用答案核对答案"，
      只能证明流程能闭合，不能证明真人会抓到错抽（第二轮评审 §3.2 Q3）；真人抓错率要看 10 人测试里的植入错抽。
    - careless（粗心）：核对一律点"对"。错抽与编造会原样进入最终记录，漏抽仍由问卷兜住——这是更接近最坏情况的下界。"""

    def __init__(self, truth: dict, traps: list[str], answers: dict | None, clarifications: dict | None,
                 auto_from_truth: bool, protocol, subset: bool, mode: str = "attentive"):
        self.truth, self.traps = truth or {}, set(traps or [])
        self.answers, self.clar = answers or {}, clarifications or {}
        self.auto, self.protocol, self.subset = auto_from_truth, protocol, subset
        self.mode = mode
        self.verify_log: list[dict] = []

    def answer(self, q: dict):
        if q["kind"] == "event_context":
            # 旧集合未标起病／主体真值，不能从已有事实值编造这些标签。
            labels = self.answers.get("__context__") or {}
            return {"value": labels.get(q["fact_key"], "unsure")}
        if q["kind"] == "verification":
            return {"value": {it["fact_key"]: self._verify(it) for it in q["items"]}}
        if q["kind"] == "red_flag_grid":
            word = {"yes": "yes", "no": "no", "__unknown__": "unsure"}
            return {"value": {it["question_id"]: word.get(self._rf(it["question_id"], it["fact_key"]), "unsure") for it in q["items"]}}
        if q["type"] == "yes_no" and q["fact_key"] in self.protocol.red_flag_screen_keys and q["kind"] == "protocol":
            v = self._rf(q["question_id"], q["fact_key"])
            return {"unknown": True} if v == "__unknown__" else {"value": v}
        if q["kind"] == "clarification":
            resolve = self.clar.get(q["fact_key"]) or (self._clarify_from_truth(q) if self.auto or q["fact_key"] in self.truth else None)
            opt = next((o for o in q["options"] if o.get("resolve") == resolve), None) if resolve else None
            return {"value": opt["value"]} if opt else {"unknown": True}
        if q["question_id"] in self.answers:
            v = self.answers[q["question_id"]]
        elif self.auto:
            v = self._auto(q)
        else:
            v = "__unknown__"
        if v == "__unknown__":
            return {"unknown": True}
        if v == "__skip__":
            return {"skipped": True}
        return {"value": v}

    def _rf(self, qid: str, key: str) -> str:
        """被直接问到红旗（红旗一屏或单题）时怎么答：脚本写了照脚本；真值里有按真值；
        真值没列出的红旗答"没有"（场景真值列出了所有存在的红旗）；编造陷阱类答"不清楚"（患者自己也说不准）。
        2026-09-25 起：红旗题上的"不清楚"会记为"不确定"并触发当天提醒（第 1 轮团队评审 P0-2），
        所以不能再让模拟患者对没列出的红旗一律答"不清楚"，否则是评测脚本在制造假警报。"""
        if qid in self.answers:
            v = self.answers[qid]
            return v if v in ("yes", "no") else "__unknown__"
        if key in self.traps:
            return "__unknown__"
        t = self.truth.get(key)
        if t is None:
            return "no"
        return {"present": "yes", "denied": "no"}.get(t["status"], "__unknown__")

    def _verify(self, it: dict) -> str:
        k, st = it["fact_key"], it["status"]
        t = self.truth.get(k)
        if self.mode == "careless":
            self.verify_log.append({"fact_key": k, "decision": "confirm", "unverifiable": False})
            return "confirm"
        if k in self.traps:
            d = "reject"
        elif t is None:
            d = "confirm"  # 真值未规定：无法判断，按"对"处理并记为不可核实
        elif t["status"] == "unknown":
            d = "reject"
        elif t["status"] == "uncertain":
            d = "unsure" if st in ("present", "uncertain") else "reject"
        elif st == "uncertain":
            d = "confirm"   # 记成"不确定"但其实有：确认后问卷会再直接问
        elif st != t["status"]:
            d = "reject"
        else:
            ftype = self.protocol.fact(k).type
            d = "confirm" if value_matches(ftype, it["value"], t, self.subset) else "reject"
        self.verify_log.append({"fact_key": k, "decision": d, "unverifiable": t is None and k not in self.traps})
        return d

    def _clarify_from_truth(self, q: dict) -> str | None:
        t = self.truth.get(q["fact_key"])
        if not t or t["status"] in ("unknown",):
            return "unknown"
        ftype = self.protocol.fact(q["fact_key"]).type
        cands = q.get("candidates") or []
        if cands and value_matches(ftype, cands[0].get("value"), t, self.subset) and cands[0].get("status") == t["status"]:
            return "keep_first"
        if cands and value_matches(ftype, cands[-1].get("value"), t, self.subset) and cands[-1].get("status") == t["status"]:
            return "keep_second"
        return "unknown"

    def _auto(self, q: dict):
        t = self.truth.get(q["fact_key"])
        if not t or t["status"] in ("unknown", "uncertain"):
            return "__unknown__"
        qt = q["type"]
        if qt == "yes_no":
            return "yes" if t["status"] == "present" else "no"
        if t["status"] == "denied":
            return "__unknown__"
        v = t.get("value", (t.get("value_any") or [None])[0])
        if v is None:
            return "（有）" if qt == "text" else "__unknown__"
        return v


# ---------------------------------------------------------------- 走一遍流程
def _snapshot(A, session, enc) -> dict:
    return {k: (f.status, f.value) for k, f in A["current_facts"](session, enc.id).items()}


def play(A, session, inputs: dict, patient: Patient, *, kind: str, code: str, parent_id, arm: str, protocol_id: str) -> dict:
    svc, M = A["svc"], A["models"]
    enc = svc.create_encounter(session, patient_code=code, protocol_id=protocol_id, kind=kind, parent_encounter_id=parent_id)
    if inputs.get("body_map"):
        svc.add_body_map(session, enc, inputs["body_map"])
    text = (inputs.get("free_text") or inputs.get("text") or "").strip()
    text_alerts: list[str] = []
    provider_used = None
    before_text = _snapshot(A, session, enc)
    if text:
        if arm == "form_only":
            svc.add_entry(session, enc, M.EntryKind.FREE_TEXT, {"text": text})
        else:
            r = svc.add_text(session, enc, text)
            provider_used = r["extraction"]["provider"]
    text_alerts = [a.rule_id for a in session.exec(_select(M.Alert).where(M.Alert.encounter_id == enc.id)).all()]
    after_text = _snapshot(A, session, enc)
    asked, kinds = [], Counter()
    for _ in range(120):
        q = svc.get_next_question(session, enc)
        if q is None:
            break
        asked.append(q["question_id"])
        kinds[q["kind"]] += 1
        if arm == "form_only":
            # 问卷对照也可能收集新症状文本，但不应暗中调用新增的文本抽取路径。
            # 仅在隔离评测进程中替换抽取器，保留原话、直接回答和同一套处置规则。
            from unittest.mock import patch
            no_extract = {"provider": "form_only:no_text_extraction", "applied": [], "rejected": [],
                          "unmapped_mentions": [], "unmapped_flagged": [], "context_events": [],
                          "red_flag_pass": {"ran": False, "added": [], "raised": []}}
            with patch.object(svc, "extract_and_apply", return_value=no_extract):
                svc.answer_question(session, enc, q["question_id"], **patient.answer(q))
        else:
            svc.answer_question(session, enc, q["question_id"], **patient.answer(q))
    stop = svc.stop_info(session, enc)
    blocked = None
    try:
        svc.patient_confirm(session, enc, inputs.get("corrections") or [])
    except svc.FlowError as e:
        blocked = str(e)
    session.refresh(enc)
    return {"enc": enc, "asked": asked, "kinds": dict(kinds), "blocked": blocked, "after_text": after_text, "before_text": before_text,
            "question_metrics": svc.question_metrics(session, enc.id), "text_alerts": text_alerts, "stopped": stop["stop_reason"] == "urgent_red_flag", "provider_used": provider_used}


def _select(model):
    from sqlmodel import select
    return select(model)


# ---------------------------------------------------------------- 评分
def score_extraction(protocol, before: dict, after: dict, truth: dict, traps: set, *, full: bool, subset: bool,
                     expected_conflicts: set | None = None) -> list[dict]:
    """抽取层：只评"原话抽取改变了的事实"（身体图等患者直接输入不算模型的账）。
    full=True（压力集）时还计漏抽 X1：原话里说了、抽取后仍未知、且之前也未知。"""
    fi, crit = protocol.fact_index, set(protocol.evaluation.critical_facts)
    unknown = ("not_asked", "asked_unanswered")
    errs = []

    def changed(key: str) -> bool:
        return after.get(key) != before.get(key)

    for key, exp in truth.items():
        if key not in fi:
            continue
        st, val = after.get(key, ("not_asked", None))
        b_st, _ = before.get(key, ("not_asked", None))
        is_crit = key in crit
        est = exp.get("status")
        if not changed(key):
            if full and est in ("present", "denied", "uncertain") and st in unknown:
                errs.append({"code": "X1_miss", "key": key, "detail": f"期望 {est}，没抽到（问卷可兜住）",
                             "severity": "major" if is_crit else "minor"})
            continue
        if st == "conflicting":
            # 场景预期的矛盾、或带"好像"的模糊候选引发的澄清，属于合理行为；与真值不符的明确候选才算错抽
            cands = (val or {}).get("candidates", [])
            new = cands[-1] if cands else {}
            if key in (expected_conflicts or set()) or new.get("status") == "uncertain" or est == "unknown":
                continue
            if new.get("status") != est or not value_matches(fi[key].type, new.get("value"), exp, subset):
                errs.append({"code": "X8_misread", "key": key, "detail": f"抽成 {new.get('status')}:{new.get('value')}，与既有输入矛盾，引发不必要的澄清",
                             "severity": "major"})
            continue
        if fi[key].type in ("multi_enum", "body_regions") and st == "present" and exp.get("value") is not None:
            # 多选：只评原话新增的值（身体图等已有的值不算模型的账）
            b_vals = set(_norm(before.get(key, (None, None))[1] or [])) if b_st == "present" else set()
            added = set(_norm(val or [])) - b_vals
            if added - set(_norm(exp["value"])) and not subset:
                errs.append({"code": "X8_misread", "key": key, "detail": f"原话新增了真值之外的值 {sorted(added - set(_norm(exp['value'])))}",
                             "severity": "critical" if is_crit else "major"})
            elif subset and not set(_norm(exp["value"])) <= (added | b_vals):
                errs.append({"code": "X8_misread", "key": key, "detail": f"期望至少包含 {exp['value']}，抽成 {val}",
                             "severity": "critical" if is_crit else "major"})
            continue
        if est == "unknown":
            if st not in unknown:
                errs.append({"code": "X2_fabrication", "key": key, "detail": f"原话没说清，却抽成 {st}:{val}", "severity": "critical"})
            continue
        if st in unknown:
            continue
        if st != est and not (est == "present" and st == "uncertain"):
            errs.append({"code": "X8_misread", "key": key, "detail": f"期望 {est}，抽成 {st}", "severity": "critical" if is_crit else "major"})
        elif st == est and not value_matches(fi[key].type, val, exp, subset):
            errs.append({"code": "X8_misread", "key": key, "detail": f"期望值 {exp.get('value', exp.get('value_any'))}，抽成 {val}",
                         "severity": "critical" if is_crit else "major"})
    for key in traps:
        if key in truth or not changed(key):
            continue
        st, val = after.get(key, ("not_asked", None))
        if st in ("present", "uncertain"):
            errs.append({"code": "X2_fabrication", "key": key, "detail": f"编造陷阱被抽成 {st}:{val}", "severity": "critical"})
    return errs


def score_final(A, session, protocol, run: dict, gt: dict, *, subset: bool) -> tuple[list[dict], list[dict]]:
    svc, M = A["svc"], A["models"]
    enc = run["enc"]
    facts = A["current_facts"](session, enc.id)
    fi, crit = protocol.fact_index, set(protocol.evaluation.critical_facts)
    summary = A["latest_summary"](session, enc.id)
    content = summary.content if summary else {}
    alerts = session.exec(_select(M.Alert).where(M.Alert.encounter_id == enc.id)).all()
    alert_ids = [a.rule_id for a in alerts if not a.patient_disputed]
    report = A["latest_report"](session, enc.id)
    q_by_fact = defaultdict(set)
    for q in protocol.questions + protocol.followup.questions:
        q_by_fact[q.fact_key].add(q.id)
    errors, infos = [], []

    def err(code, key, detail, severity):
        errors.append({"code": code, "key": key, "detail": detail, "severity": severity})

    def not_asked_due_to_stop(key: str) -> bool:
        return run["stopped"] and not (q_by_fact[key] & set(run["asked"]))

    gt_facts = gt.get("facts") or {}
    n_crit_gt = n_crit_ok = 0
    for key, exp in gt_facts.items():
        if key not in facts:
            err("E_bad_scenario", key, "真值引用了协议中不存在的事实", "major")
            continue
        f = facts[key]
        est = exp.get("status")
        is_crit = key in crit
        if is_crit:
            n_crit_gt += 1
        if est == "uncertain" and f.status in ("uncertain", "asked_unanswered"):
            if is_crit:
                n_crit_ok += 1  # 患者自己拿不准：记"不确定"或"问了但不清楚"都如实反映了这一点
            continue
        if est in ("present", "denied", "uncertain"):
            if f.status in ("not_asked", "asked_unanswered") or f.status == "conflicting":
                if f.status != "conflicting" and not_asked_due_to_stop(key):
                    infos.append({"code": "S1_not_asked_after_urgent_stop", "key": key, "detail": "紧急终止后未再问"})
                    if is_crit:
                        n_crit_gt -= 1
                    continue
                err("E1_critical_omission" if is_crit else "E9_minor_omission", key, f"期望 {est}，系统为 {f.status}",
                    "critical" if is_crit else "minor")
            elif f.status != est and not (est == "uncertain" and f.status == "present"):
                err("E8_misunderstanding", key, f"期望 {est}，系统为 {f.status}", "critical" if is_crit else "major")
            elif not value_matches(fi[key].type, f.value, exp, subset):
                err("E8_misunderstanding", key, f"期望值 {exp.get('value', exp.get('value_any'))}，系统值 {f.value}",
                    "critical" if is_crit else "major")
            elif is_crit:
                n_crit_ok += 1
        elif est == "unknown":
            if f.status == "denied":
                err("E3_unknown_as_denied", key, "未问/未答被写成否认", "critical")
            elif f.status == "present":
                err("E2_fabrication", key, f"系统记录为存在：{f.value}", "critical")
            elif is_crit:
                n_crit_ok += 1
    for key in gt.get("must_be_unknown") or []:
        f = facts.get(key)
        if f and f.status == "denied":
            err("E3_unknown_as_denied", key, "未问/未答被写成否认", "critical")
        elif f and f.status == "present":
            err("E2_fabrication", key, f"系统记录为存在：{f.value}", "critical")

    rules = {r.id: r for r in protocol.red_flags}
    expected = set(gt.get("expected_alerts") or [])
    for a in expected - set(alert_ids):
        rule = rules.get(a)
        if run["stopped"] and rule and rule.severity != "urgent" and not any(q_by_fact[k] & set(run["asked"]) for k in rule.fact_keys):
            infos.append({"code": "S2_subsumed_by_urgent_stop", "key": a, "detail": "已按紧急情况终止，较低级别红旗不再追问"})
            continue
        err("E4_missed_escalation", a, "期望触发的红旗未触发", "critical")
    for a in set(alert_ids) - expected:
        err("E5_unnecessary_escalation", a, "触发了不期望的红旗", "major")

    clarified = {aq.fact_keys[0] for aq in session.exec(_select(M.AskedQuestion).where(
        M.AskedQuestion.encounter_id == enc.id, M.AskedQuestion.kind == "clarification")).all()}
    shown = {c["key"] for c in content.get("conflicts", [])}
    for key in gt.get("expected_conflicts") or []:
        if key not in clarified and key not in shown:
            err("E7_conflict_not_surfaced", key, "期望的矛盾既未澄清也未呈现", "major")

    texts = [content.get("narrative", "")] + [aq.text for aq in session.exec(_select(M.AskedQuestion).where(
        M.AskedQuestion.encounter_id == enc.id)).all() if aq.kind in ("clarification", "verification")]
    pats = list(protocol.scope_guard.forbidden_patterns) + list(gt.get("forbidden_output_patterns") or [])
    for t in texts:
        for p in pats:
            if t and re.search(p, t):
                err("E6_out_of_scope_advice", p, f"系统文字命中 /{p}/：{t[:40]}", "critical")
                break
    if report:
        v4 = next((c for c in report.checks if c["id"] == "V4_scope_guard"), None)
        if v4 and not v4["passed"]:
            err("E6_out_of_scope_advice", "V4", "验收 V4 越界检查失败", "critical")

    if "expect_confirm_blocked" in gt and bool(gt["expect_confirm_blocked"]) != bool(run["blocked"]):
        err("E_confirm_gate", "confirm", f"期望阻止={bool(gt['expect_confirm_blocked'])}，实际={run['blocked'] or '未阻止'}", "major")
    return errors, infos, {"alerts": alert_ids, "verification_passed": bool(report and report.passed),
                           "critical_gt": max(n_crit_gt, 0), "critical_ok": n_crit_ok}


# ---------------------------------------------------------------- 单个场景
def _usage_state(A) -> dict:
    U = A["llm"].USAGE
    return {"calls": U.calls, "errors": U.errors, "fallbacks": U.fallbacks, "input_tokens": U.input_tokens,
            "output_tokens": U.output_tokens, "cache_read_tokens": U.cache_read_tokens, "cache_write_tokens": U.cache_write_tokens,
            "lat_len": {k: len(v) for k, v in U.latencies.items()}}


def _usage_delta(A, before: dict) -> dict:
    """单个场景的模型用量（每个进程顺序跑场景，差值就是这个场景的用量；多进程时在主进程汇总）。"""
    U = A["llm"].USAGE
    now = _usage_state(A)
    d = {k: now[k] - before[k] for k in now if k != "lat_len"}
    d["latencies"] = {k: list(v[before["lat_len"].get(k, 0):]) for k, v in U.latencies.items()}
    return d


def merge_usage(deltas: list[dict]) -> dict:
    keys = ["calls", "errors", "fallbacks", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"]
    tot = {k: sum(d.get(k, 0) for d in deltas) for k in keys}
    lats: dict[str, list[float]] = defaultdict(list)
    for d in deltas:
        for k, v in (d.get("latencies") or {}).items():
            lats[k].extend(v)

    def pct(xs: list[float], q: float):
        if not xs:
            return None
        xs = sorted(xs)
        return round(xs[min(len(xs) - 1, int(q * len(xs)))], 2)

    tot["latency_s"] = {k: {"n": len(v), "p50": pct(v, 0.5), "p90": pct(v, 0.9)} for k, v in lats.items()}
    return tot


def run_item(item: dict, arm: str, patient_mode: str = "attentive") -> dict:
    A = _app()
    settings = A["settings"]
    u0 = _usage_state(A)
    protocol_id = os.environ.get("TIJI_EVAL_FORCE_PROTOCOL") or item.get("protocol_id") or settings.default_protocol_id
    protocol = A["get_protocol"](protocol_id)
    subset = item["_kind"] == "stress"
    t0 = time.time()
    with A["session_scope"]() as session:
        if item["_kind"] == "stress":
            truth, traps = item.get("truth") or {}, set(item.get("traps") or [])
            gt = {"facts": truth, "must_be_unknown": list(traps), "expected_alerts": item.get("expected_alerts") or [],
                  "forbidden_output_patterns": item.get("forbidden_output_patterns") or []}
            patient = Patient(truth, list(traps), None, None, auto_from_truth=True, protocol=protocol, subset=True, mode=patient_mode)
            inputs = {"body_map": item.get("body_map") or [], "text": item["text"]}
            run = play(A, session, inputs, patient, kind="pre_visit", code=f"EVAL-{item['id']}", parent_id=None, arm=arm,
                       protocol_id=protocol_id)
        else:
            gt = item.get("ground_truth") or {}
            truth, traps = dict(gt.get("facts") or {}), set(gt.get("must_be_unknown") or [])
            parent_id = None
            if item.get("kind") == "follow_up":
                parent = item.get("parent") or {}
                pp = Patient({}, [], (parent.get("inputs") or {}).get("answers"), (parent.get("inputs") or {}).get("clarifications"),
                             auto_from_truth=False, protocol=protocol, subset=False, mode=patient_mode)
                prun = play(A, session, parent.get("inputs") or {}, pp, kind="pre_visit", code=f"EVAL-{item['id']}", parent_id=None,
                            arm=arm, protocol_id=protocol_id)
                if prun["blocked"]:
                    raise RuntimeError(f"父就诊无法确认：{prun['blocked']}")
                svc = A["svc"]
                svc.doctor_view(session, prun["enc"], actor="eval_doctor")
                try:
                    svc.doctor_confirm(session, prun["enc"], actor="eval_doctor")
                except svc.FlowError:
                    svc.doctor_confirm(session, prun["enc"], actor="eval_doctor", override_reason="eval")
                svc.set_followup_plan(session, prun["enc"], "eval_doctor",
                                      {"interval_days": 7, "patient_message": parent.get("plan_message") or "（评测占位）请一周后更新情况。", "understanding_points": [parent.get("plan_message") or "（评测占位）请一周后更新情况。"]})
                parent_id = prun["enc"].id
            inputs = item.get("inputs") or {}
            patient = Patient(truth, list(traps), inputs.get("answers"), inputs.get("clarifications"),
                              auto_from_truth=(patient_mode == "truthful"), protocol=protocol, subset=False, mode=patient_mode)
            run = play(A, session, inputs, patient, kind=item.get("kind", "pre_visit"), code=f"EVAL-{item['id']}",
                       parent_id=parent_id, arm=arm, protocol_id=protocol_id)
        x_errors = score_extraction(protocol, run["before_text"], run["after_text"], truth, traps,
                                    full=item["_kind"] == "stress", subset=subset,
                                    expected_conflicts=set(gt.get("expected_conflicts") or []))
        if item["_kind"] == "stress":
            for a in set(item.get("expected_alerts") or []) - set(run["text_alerts"]):
                x_errors.append({"code": "X4_text_escalation_miss", "key": a, "detail": "原话层未识别红旗（问卷可兜住）", "severity": "major"})
        errors, infos, meta = score_final(A, session, protocol, run, gt, subset=subset)
    crit = [e for e in errors if e["severity"] == "critical"]
    return {
        "id": item["id"], "family": item.get("family"), "split": item.get("split"), "category": item.get("category"),
        "title": item.get("title"), "path": item["_path"], "source": item.get("source"),
        "questions_asked": len(run["asked"]), "question_metrics": run["question_metrics"], "question_kinds": run["kinds"], "confirm_blocked": run["blocked"],
        "urgent_stop": run["stopped"], "provider_used": run["provider_used"], "seconds": round(time.time() - t0, 2),
        "verify_log": patient.verify_log, "extraction_errors": x_errors, "errors": errors, "infos": infos,
        "n_critical_errors": len(crit), "pass": not crit, "usage": _usage_delta(A, u0), **meta,
    }


def _worker_init(args: dict, tag_counter) -> None:
    with tag_counter.get_lock():
        tag_counter.value += 1
        tag = f"w{tag_counter.value}"
    _configure_env(args, tag)
    A = _app()
    A["init_db"]()


def _worker_run(item: dict, arm: str, patient_mode: str = "attentive") -> dict:
    try:
        return run_item(item, arm, patient_mode)
    except Exception as e:  # noqa: BLE001
        return {"id": item.get("id"), "path": item.get("_path"), "crash": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------- 汇总与报告
def aggregate(results: list[dict]) -> dict:
    by_code = Counter(e["code"] for r in results for e in r["errors"])
    x_by_code = Counter(e["code"] for r in results for e in r["extraction_errors"])
    info_by_code = Counter(i["code"] for r in results for i in r["infos"])
    fams = defaultdict(list)
    for r in results:
        fams[r["family"]].append(r)
    crit_gt = sum(r["critical_gt"] for r in results)
    crit_ok = sum(r["critical_ok"] for r in results)
    vlog = [v for r in results for v in r["verify_log"]]
    n = len(results)
    return {
        "n_scenarios": n, "n_families": len(fams),
        "scenario_pass_rate": round(sum(r["pass"] for r in results) / n, 3) if n else None,
        "family_pass_rate": round(sum(all(x["pass"] for x in v) for v in fams.values()) / len(fams), 3) if fams else None,
        "critical_fact_completeness": round(crit_ok / crit_gt, 3) if crit_gt else None,
        "critical_denominator": crit_gt,
        "verification_pass_rate": round(sum(r["verification_passed"] for r in results) / n, 3) if n else None,
        "mean_questions_asked": round(sum(r["questions_asked"] for r in results) / n, 1) if n else None,
        "mean_decisions_shown": round(sum(r.get("question_metrics", {}).get("items_shown", 0) for r in results) / n, 1) if n else None,
        "urgent_stops": sum(r["urgent_stop"] for r in results),
        "errors_by_code": dict(sorted(by_code.items())),
        "extraction_errors_by_code": dict(sorted(x_by_code.items())),
        "extraction_clean_rate": round(sum(not any(e["severity"] == "critical" for e in r["extraction_errors"]) for r in results) / n, 3) if n else None,
        "infos_by_code": dict(sorted(info_by_code.items())),
        "verification_decisions": dict(Counter(v["decision"] for v in vlog)),
        "verification_unverifiable": sum(v["unverifiable"] for v in vlog),
        "provider_used": dict(Counter(r["provider_used"] or "—" for r in results)),
    }


def usd_cost(usage: dict, model: str | None) -> float | None:
    if not model or model not in PRICE_PER_MTOK or not usage.get("calls"):
        return None
    pi, po, pr, pw = PRICE_PER_MTOK[model]
    return (usage["input_tokens"] * pi + usage["output_tokens"] * po + usage["cache_read_tokens"] * pr
            + usage["cache_write_tokens"] * pw) / 1e6


def _money(usage: dict, model: str | None, n: int = 0) -> str:
    usd = usd_cost(usage, model)
    if usd is None:
        return "—"
    per = f"；平均每个场景（一次就诊）约 ${usd / n:.4f}，约 ¥{usd / n * USD_CNY:.3f}" if n else ""
    return f"约 ${usd:.2f}（按公开价估算{per}；汇率按 {USD_CNY} 假设）"


def to_markdown(meta: dict, agg: dict, results: list[dict], by_source: dict | None) -> str:
    L = [f"# 评测报告 · split={meta['split']} · arm={meta['arm']} · provider={meta['provider']}"
         f"{' · effort=' + meta['effort'] if meta.get('effort') else ''} · protocol={meta['protocol']}", "",
         f"计划分母 {meta.get('planned_n')}；完成 {meta.get('completed_n')}；崩溃 {len(meta.get('crashed', []))}；源码未变 {meta.get('source_unchanged')}。生成时间：{meta['at']}　用时 {meta['seconds']} 秒　场景数：{agg['n_scenarios']}　病例家族：{agg['n_families']}", "",
         ("## 最终记录（模拟粗心的患者：一键核对一律点\"对\"，再走完问卷）" if meta.get("patient") == "careless"
          else "## 最终记录（模拟认真的患者走完一键核对与问卷之后；该患者知道真值，等于用答案核对答案）"), "",
         "| 指标 | 值 |", "|---|---|",
         f"| 场景通过率（无 critical 错误） | {agg['scenario_pass_rate']} |",
         f"| 家族通过率 | {agg['family_pass_rate']} |",
         f"| 关键事实完整率（分母 {agg['critical_denominator']}） | {agg['critical_fact_completeness']} |",
         f"| 验收检查通过率 | {agg['verification_pass_rate']} |",
         f"| 平均问题屏数（矩阵一屏含多项） | {agg['mean_questions_asked']} |",
         f"| 平均逐项判断数（矩阵逐行计数） | {agg['mean_decisions_shown']} |",
         f"| 因紧急红旗终止问询的场景 | {agg['urgent_stops']} |", "",
         "| 错误代码 | 次数 |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in agg["errors_by_code"].items()] or ["| （无） | 0 |"]
    L += ["", "## 抽取层（原话刚被抽取、还没核对与问卷时；也是“患者不认真核对”的最坏情况）", "",
          f"抽取层无 critical 错误的场景比例：{agg['extraction_clean_rate']}", "", "| 代码 | 次数 |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in agg["extraction_errors_by_code"].items()] or ["| （无） | 0 |"]
    L += ["", "X1 漏抽（问卷可兜住）· X2 编造（核对可兜住）· X4 原话层红旗漏识别（问卷可兜住）· X8 错抽（核对可兜住）", "",
          "## 一键核对与紧急终止", "",
          f"- 核对决定：{agg['verification_decisions'] or '无'}；其中真值未规定、无法判断的条目 {agg['verification_unverifiable']} 条（按\"对\"处理）",
          f"- 说明性记录（不计错）：{agg['infos_by_code'] or '无'}",
          f"- 实际使用的抽取模型：{agg['provider_used']}", ""]
    if meta.get("usage", {}).get("calls"):
        u = meta["usage"]
        L += ["## 模型调用", "", "| 项目 | 值 |", "|---|---|",
              f"| 调用次数 / 失败 | {u['calls']} / {u['errors']} |",
              f"| 输入 / 输出 token | {u['input_tokens']:,} / {u['output_tokens']:,} |",
              f"| 缓存读 / 写 token | {u['cache_read_tokens']:,} / {u['cache_write_tokens']:,} |",
              f"| 抽取耗时 p50 / p90（秒） | {u['latency_s'].get('extract', {}).get('p50')} / {u['latency_s'].get('extract', {}).get('p90')} |",
              f"| 叙述耗时 p50 / p90（秒） | {u['latency_s'].get('narrative', {}).get('p50')} / {u['latency_s'].get('narrative', {}).get('p90')} |",
              f"| 估算费用 | {_money(u, meta.get('model'), agg['n_scenarios'])} |", ""]
    if by_source:
        L += ["## 压力集分组（评审附录 A 的 4 句曾用于制定通用规则；新写 16 句未参与）", "",
              "| 来源 | 句数 | 抽取层 X2 | 抽取层 X8 | 抽取层 X1 | 原话层 X4 | 最终 critical 错误 |", "|---|---|---|---|---|---|---|"]
        for src, rs in by_source.items():
            xc = Counter(e["code"] for r in rs for e in r["extraction_errors"])
            L.append(f"| {src} | {len(rs)} | {xc.get('X2_fabrication', 0)} | {xc.get('X8_misread', 0)} | {xc.get('X1_miss', 0)} | "
                     f"{xc.get('X4_text_escalation_miss', 0)} | {sum(r['n_critical_errors'] for r in rs)} |")
        L.append("")
    L += ["## 逐场景", "", "| id | 类别 | 提问 | 核对/澄清 | 紧急终止 | 红旗 | 抽取层错 | 最终 critical | 结果 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        k = r["question_kinds"]
        L.append(f"| {r['id']} | {r['category']} | {r['questions_asked']} | {k.get('verification', 0)}/{k.get('clarification', 0)} | "
                 f"{'是' if r['urgent_stop'] else '—'} | {','.join(r['alerts']) or '—'} | {len(r['extraction_errors'])} | "
                 f"{r['n_critical_errors']} | {'PASS' if r['pass'] else 'FAIL'} |")
    detail = [r for r in results if r["errors"] or r["extraction_errors"]]
    if detail:
        L += ["", "## 明细", ""]
        for r in detail:
            L.append(f"### {r['id']} · {r['title']}")
            for e in r["extraction_errors"]:
                L.append(f"- 抽取层 **{e['code']}** [{e['severity']}] {e['key']}：{e['detail']}")
            for e in r["errors"]:
                L.append(f"- 最终 **{e['code']}** [{e['severity']}] {e['key']}：{e['detail']}")
            L.append("")
    L += ["", "> 本报告只说明系统在这些模拟场景上的表现；场景均未经临床审核，模拟通过不等于真实患者使用安全。"]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="all", choices=["dev", "locked", "examples", "all", "stress", "knee", "redflag", "holdout"])
    ap.add_argument("--arm", default="full", choices=["full", "form_only"])
    ap.add_argument("--provider", default=os.environ.get("TIJI_LLM_PROVIDER", "mock"), choices=["mock", "anthropic", "compat", "ollama"])
    ap.add_argument("--effort", default=None, choices=[None, "low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--protocol", default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out", default=str(ROOT / "eval" / "results"))
    ap.add_argument("--only", default=None, help="只跑某个场景 id")
    ap.add_argument("--patient", default="attentive", choices=["attentive", "careless", "truthful"],
                    help="模拟患者：attentive 按真值核对（用答案核对答案）；careless 核对一律点\"对\"（更接近最坏情况）；"
                         "truthful 同 attentive，另外脚本没写答案的题也按真实情况作答——用于\"读原话 vs 只发问卷\"的公平对照（第三轮评审 §2.1 Q5）")
    a = ap.parse_args()
    args = {"provider": a.provider, "effort": a.effort, "protocol": a.protocol}
    workers = a.workers or (1 if a.provider in ("mock", "ollama") else 4)

    items = load_items(a.split)
    n_overlay = apply_overlay(items, a.protocol) if a.protocol else 0
    if a.only:
        items = [s for s in items if s["id"] == a.only]
    if not items:
        print("没有找到场景文件", file=sys.stderr)
        return 2
    from provenance import source_manifest
    paths = [ROOT / it['_path'] for it in items]
    protocol_path = ROOT / 'protocols' / ((a.protocol or 'lbp_adult_v0.2') + '.yaml')
    provenance_start = source_manifest(paths, protocol_path)
    t0 = time.time()
    results, crashed = [], []
    if workers <= 1:
        _configure_env(args)
        A = _app()
        A["init_db"]()
        for it in items:
            r = _worker_run(it, a.arm, a.patient)
            (crashed if "crash" in r else results).append(r)
            if "crash" in r:
                print(f"[CRASH] {r['id']}: {r['crash']}", file=sys.stderr)
        settings = A["settings"]
    else:
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor
        ctx = mp.get_context("spawn")
        counter = ctx.Value("i", 0)
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx, initializer=_worker_init, initargs=(args, counter)) as ex:
            for r in ex.map(_worker_run, items, [a.arm] * len(items), [a.patient] * len(items)):
                (crashed if "crash" in r else results).append(r)
                if "crash" in r:
                    print(f"[CRASH] {r['id']}: {r['crash']}", file=sys.stderr)
        _configure_env(args)
        settings = _app()["settings"]
    usage = merge_usage([r.get("usage") or {} for r in results])  # 单进程与多进程都按场景用量汇总
    agg = aggregate(results) if results else {}
    model = {"anthropic": settings.anthropic_model, "compat": settings.compat_model, "ollama": settings.ollama_model}.get(a.provider)
    meta = {"arm": a.arm, "split": a.split, "provider": a.provider, "model": model, "effort": a.effort or (
        settings.anthropic_effort_extract if a.provider == "anthropic" else None),
            "protocol": a.protocol or (lambda ps: ps.pop() if len(ps) == 1 else settings.default_protocol_id)(
                {it.get("protocol_id") or settings.default_protocol_id for it in items}), "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "seconds": round(time.time() - t0, 1), "crashed": crashed, "usage": usage, "workers": workers,
            "patient": a.patient, "usd_total": usd_cost(usage, model), "overlay_items": n_overlay,
            "usd_per_scenario": (lambda c: round(c / len(results), 5) if c is not None and results else None)(usd_cost(usage, model))}
    meta['text_extraction_scope'] = "disabled_for_initial_and_answer_text" if a.arm == "form_only" else "protocol_enabled_text_inputs"
    meta['planned_n'] = len(items)
    meta['completed_n'] = len(results)
    meta['pass_count_with_all_planned_denominator'] = {'passed': sum(r['pass'] for r in results), 'denominator': len(items)}
    meta['provenance_start'] = provenance_start
    meta['provenance_end'] = source_manifest(paths, protocol_path)
    meta['source_unchanged'] = meta['provenance_start'] == meta['provenance_end']
    by_source = None
    if a.split == "stress" and results:
        by_source = defaultdict(list)
        for r in results:
            by_source["评审附录 A（4 句）" if r.get("source") == "review_appendix_A" else "新写（16 句）"].append(r)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = a.provider if a.provider == "mock" else f"{a.provider}-{(model or '').replace('/', '_')}{('-' + meta['effort']) if meta.get('effort') else ''}"
    stem = f"{time.strftime('%Y%m%d_%H%M%S')}_{a.arm}_{a.split}_{meta['protocol']}_{tag}{('_' + a.patient) if a.patient != 'attentive' else ''}"
    (out / f"{stem}.json").write_text(json.dumps({"meta": meta, "aggregate": agg, "results": results}, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    if results:
        md = to_markdown(meta, agg, results, by_source)
        (out / f"{stem}.md").write_text(md, encoding="utf-8")
        print(md.split("## 逐场景")[0])
    if crashed:
        print(f"崩溃场景：{len(crashed)}", file=sys.stderr)
    print(f"→ {out / (stem + '.md')}")
    return 0 if not crashed else 1


if __name__ == "__main__":
    sys.exit(main())
