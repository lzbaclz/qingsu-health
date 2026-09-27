#!/usr/bin/env python3
"""医生审核决定 → 协议 v0.2 候选。

在医生做出第一批决定之前，生成的 v0.2 只是 AI 草案换了个文件名：标题会写明"医生已决定 0 条"，
任何对外材料（BP、视频、演示）都不出现 v0.2，演示继续用 v0.1 并标"工程占位"（第二轮评审 §3.2 Q1）。

  python protocols/review/build_v02.py --init   # 从 AI 草案生成决定文件骨架 protocols/review/decisions.yaml（已存在则不覆盖）
  python protocols/review/build_v02.py          # 读 decisions.yaml，生成 protocols/lbp_adult_v0.2.yaml 与审核报告

决定取值：pending（未审，保留 AI 草案并标记待审）| adopt（采纳，标记已审）| modify（按 overrides 修改后标记已审）| drop（删除）。
删除事实时，引用它的问题会一并删除；引用它的红旗规则必须先由医生决定（否则报错，不静默删除安全规则）。
所有人都填好、没有 pending 时，协议状态为 clinically_reviewed；否则仍为 draft。approved 需第二位复核者签字后手工改。
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
DRAFT = ROOT / "protocols" / "lbp_adult_v0.2_ai_draft.yaml"
DECISIONS = ROOT / "protocols" / "review" / "decisions.yaml"
OUT = ROOT / "protocols" / "lbp_adult_v0.2.yaml"
REPORT = ROOT / "protocols" / "review" / "v0.2_审核报告.md"
# 疗程安全网的临床内容（第 1 轮团队评审）：由模拟临床负责人写，合并进 v0.2 的 course / screening / 签到题
COURSE = ROOT / "protocols" / "review" / "course_safety_net_sim.yaml"
COURSE_KEYS = ("time_budget", "service_windows", "red_flag_routes", "urgent_page", "reassurance", "callback_task", "outcomes",
               "reference_curves", "recovery_rules", "schedule_days", "no_response", "task_routing", "closure", "safety_card",
               "respondent")

# AI 模拟填写版里标 ⚠ 的条目（对比表对应行），生成骨架时加注释提醒优先审
FLAGGED = {
    "facts": {"age_band": "T1-3/T2-1", "pregnancy_status": "T1-4/T2-2", "bowel_change": "T2-3", "sexual_function_change": "T2-4",
              "infection_risk": "T2-8", "severity_worst_24h": "T2-13", "morning_stiffness_30min": "T2-10", "low_mood": "T2-14",
              "fear_of_movement": "T2-14", "catastrophizing": "T2-14", "work_type": "T2-14"},
    "red_flags": {"rf_bladder_bowel": "T4-1/T4-2", "rf_saddle": "T4-1", "rf_ces_sexual": "T4-1", "rf_bilateral_only": "T4-3",
                  "rf_progressive_weakness": "T4-4", "rf_weight_loss_or_cancer": "T4-10", "rf_out_of_scope": "T4-12"},
}


def _load(p: pathlib.Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def init() -> None:
    if DECISIONS.exists():
        print(f"{DECISIONS} 已存在，不覆盖")
        return
    d = _load(DRAFT)
    L = ["# 医生审核决定（交付物 #1 适用范围、#3 事实清单、#4 红旗与处理流程）",
         "# 取值：pending（未审）| adopt（采纳）| modify（按 overrides 修改）| drop（删除）。note 写理由——分歧理由是评审最想看的。",
         "# 标 ⚠ 的是 AI 自认没把握的条目（对应 protocols/review/对比表_AI版_vs_医生版.md 的行号），请优先审。",
         "# 改完运行：make protocol-v02   → 生成 protocols/lbp_adult_v0.2.yaml 与 protocols/review/v0.2_审核报告.md", "",
         "meta:",
         "  reviewed_on: null            # 审核日期，如 2026-09-26",
         "  clinical_lead:               # 临床产品负责人（BP 团队页会用到）",
         "    name: null",
         "    title: null                # 职称",
         "    department: null",
         "    institution: null",
         "    hours_per_week: null",
         "  clinical_reviewer:           # 第二位独立复核者",
         "    name: null",
         "    title: null",
         "  sources_confirmed: []        # 医生确认采用的资料（可从 AI 版 15 条里挑，也可补充科室流程文件）", "",
         "settings:",
         f"  max_questions: {d['max_questions']}            # ⚠ T3-2：AI 建议 20，且必问题（tier 1）不受上限", "",
         "scope:                         # 交付物 #1",
         "  decision: pending",
         "  overrides: {}                # 例：{contact_phone: \"0755-xxxxxxx\", service_hours: \"...\", emergency_notice: \"...\"}",
         "  note: \"\"", "",
         "facts:                         # 交付物 #3"]
    for f in d["facts"]:
        flag = FLAGGED["facts"].get(f["key"])
        L.append(f"  {f['key']}: {{decision: pending, note: \"\"}}    # {f['label']}{'  ⚠ ' + flag if flag else ''}")
    L += ["", "questions:                     # 问法与顺序（交付物 #2，可后审）"]
    for q in d["questions"] + d["followup"]["questions"]:
        L.append(f"  {q['id']}: {{decision: pending}}    # {q['text'][:30]}")
    L += ["", "red_flags:                     # 交付物 #4：条件、级别、给患者的原话、是否终止问询"]
    for r in d["red_flags"]:
        flag = FLAGGED["red_flags"].get(r["id"])
        L.append(f"  {r['id']}: {{decision: pending, overrides: {{}}, note: \"\"}}    # [{r['severity']}] {r['label']}{'  ⚠ ' + flag if flag else ''}")
    DECISIONS.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"→ {DECISIONS}")


def _deep_merge(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def build() -> int:
    if not DECISIONS.exists():
        print("缺少 decisions.yaml，先运行 --init", file=sys.stderr)
        return 2
    p, dec = _load(DRAFT), _load(DECISIONS) or {}
    meta, errors = dec.get("meta") or {}, []
    simulated = bool(meta.get("simulated"))
    counts = {"adopt": 0, "modify": 0, "drop": 0, "pending": 0}
    pending_items: list[str] = []

    def decide(section: str, item: dict, key: str) -> dict | None:
        d = ((dec.get(section) or {}).get(key)) or {"decision": "pending"}
        kind = d.get("decision", "pending")
        if kind not in counts:
            errors.append(f"{section}.{key}: 未知决定 {kind}")
            kind = "pending"
        counts[kind] += 1
        if kind == "drop":
            return None
        item = _deep_merge(item, d.get("overrides") or {}) if kind == "modify" else item
        if "clinical_review_required" in item or section in ("facts", "red_flags"):
            # 模拟临床负责人的决定不算临床审核：仍标"需要临床审核"
            item["clinical_review_required"] = kind == "pending" or simulated
        if kind == "pending":
            pending_items.append(f"{section}.{key}")
        if d.get("note"):
            item.setdefault("notes" if section == "facts" else "review_note", d["note"])
        return item

    facts = [x for x in (decide("facts", f, f["key"]) for f in p["facts"]) if x]
    kept = {f["key"] for f in facts}
    dropped = {f["key"] for f in p["facts"]} - kept
    qs = [x for x in (decide("questions", q, q["id"]) for q in p["questions"] if q["fact_key"] in kept) if x]
    fqs = [x for x in (decide("questions", q, q["id"]) for q in p["followup"]["questions"] if q["fact_key"] in kept) if x]
    rfs = []
    for r in p["red_flags"]:
        x = decide("red_flags", r, r["id"])
        when = (x or r)["when"]
        refs = {w.split(".")[1] for w in when.replace("(", " ").replace(")", " ").split() if w.startswith("facts.")}
        if x is not None and refs & dropped:
            errors.append(f"红旗 {r['id']} 引用了被删除的事实 {sorted(refs & dropped)}：请医生对这条红旗明确 drop 或 modify 其 when")
        if x:
            rfs.append(x)
    sc = dec.get("scope") or {}
    if sc.get("decision") in ("adopt", "modify"):
        p["scope"] = _deep_merge(p["scope"], sc.get("overrides") or {})
    elif sc.get("decision", "pending") == "pending":
        pending_items.append("scope")
    p.update(facts=facts, questions=qs, red_flags=rfs)
    p["followup"]["questions"] = fqs
    p["followup"]["change_facts"] = [k for k in p["followup"]["change_facts"] if k in kept]
    p["summary"]["key_facts_order"] = [k for k in p["summary"]["key_facts_order"] if k in kept]
    p["evaluation"]["critical_facts"] = [k for k in p["evaluation"]["critical_facts"] if k in kept]
    p["max_questions"] = (dec.get("settings") or {}).get("max_questions", p["max_questions"])
    # 术语对照表（P4）：以 v0.1 已有的 12 条为底，按 policies.plain_language 逐条采纳 / 改写 / 删除（第 1 轮团队评审 P0-3）
    pl = (dec.get("policies") or {}).get("plain_language") or {}
    if pl.get("decision") in ("adopt", "modify"):
        base = (yaml.safe_load((ROOT / "protocols" / "lbp_adult_v0.1.yaml").read_text(encoding="utf-8")).get("followup") or {}).get("plain_language") or []
        ov = pl.get("overrides") or {}
        terms = []
        for t in base:
            o = ov.get(t["term"], "采纳")
            if o in ("删除", "drop", None):
                continue
            terms.append({"term": t["term"], "plain": t["plain"] if o in ("采纳", "adopt") else str(o), "clinical_review_required": True})
        p["followup"]["plain_language"] = terms
    lead = meta.get("clinical_lead") or {}
    rev = meta.get("clinical_reviewer") or {}
    p["protocol_id"], p["version"] = "lbp_adult_v0.2", "0.2.6"
    n_decided = counts["adopt"] + counts["modify"] + counts["drop"]
    n_total = n_decided + counts["pending"]
    course_note = _merge_course(p, facts, kept, qs, fqs, rfs, errors)
    event_file = ROOT / "protocols" / "review" / "event_verification_sim.yaml"
    if event_file.exists():
        p["event_verification"] = _load(event_file)
        p["course"]["functional_goals_enabled"] = True
        p["followup"]["teachback_enabled"] = True
        p["followup"]["teachback_clinical_review_required"] = True
        for rule in p["red_flags"]:
            if rule["severity"] in {"urgent", "same_day"}:
                rule["escalate_on_conflict"] = True
                rule["conflict_patient_message"] = ("你前后提供的情况不一致，目前尚未确认。若你现在出现本页列出的紧急情况，"
                    "请不要等待线上回复，按紧急提示就医。门诊会看到需要核实的双方说法。（模拟临床稿）")
    # 模拟临床负责人（AI 医学视角）填的决定：标题、状态、报告都不得写成"医生已决定"（第 1 轮团队评审 P0-1）
    who = "模拟临床负责人" if simulated else "医生"
    p["title"] = ("成年腰背痛 · 就诊前采集与诊后随访（v0.2 候选：AI 草案，医生尚未决定）" if n_decided == 0 else
                  f"成年腰背痛 · 就诊前采集与疗程随访（v0.2 候选：{who}已决定 {n_decided}/{n_total}"
                  + ("，待真实医生复核）" if simulated else "）"))
    lead_parts = [lead.get("name")] if simulated else [lead.get("name"), lead.get("title"), lead.get("department"), lead.get("institution")]
    p["owners"] = {"clinical_lead": " ".join(str(x) for x in lead_parts if x) or "待填写",
                   "clinical_reviewer": " ".join(str(x) for x in [rev.get("name"), rev.get("title")] if x) or "待填写",
                   "engineering": p["owners"].get("engineering", "")}
    p["review"] = {"last_reviewed": str(meta.get("reviewed_on")) if meta.get("reviewed_on") else None,
                   "next_review": None, "sources": meta.get("sources_confirmed") or p["review"].get("sources", []),
                   "decided_by": "simulated_clinical_lead" if simulated else ("clinical_lead" if n_decided else None),
                   "real_doctor_decided": 0 if simulated else n_decided, "simulated_decided": n_decided if simulated else 0,
                   "total_items": n_total}
    # 模拟决定永远不能让协议变成"已临床审核"
    p["status"] = "clinically_reviewed" if (lead.get("name") and not simulated and not pending_items and not errors) else "draft"
    if errors:
        for e in errors:
            print("✗", e, file=sys.stderr)
        return 1
    sys.path.insert(0, str(ROOT / "backend"))
    from app.protocol.schema import Protocol
    Protocol.model_validate(p)  # 不合法会直接报错
    OUT.write_text("# 由 protocols/review/build_v02.py 根据 decisions.yaml 生成；不要手改，改 decisions.yaml 后重新生成。\n"
                   + yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    R = [f"# 协议 v0.2 审核报告（{dt.datetime.now():%Y-%m-%d %H:%M}）", "",
         f"- 临床负责人：{p['owners']['clinical_lead']}；第二复核者：{p['owners']['clinical_reviewer']}；审核日期：{p['review']['last_reviewed'] or '未填'}",
         f"- 协议状态：**{p['status']}**（全部条目决定完毕且负责人实名后才会变为 clinically_reviewed）",
         f"- 对外口径：{_stance(n_decided, simulated)}",
         f"- 决定统计：采纳 {counts['adopt']} · 修改 {counts['modify']} · 删除 {counts['drop']} · 未审 {counts['pending']}",
         f"- 生成结果：事实 {len(facts)} · 问题 {len(qs)}（随访 {len(fqs)}）· 红旗 {len(rfs)}",
         f"- 疗程安全网：{course_note}", "",
         "## 仍未审的条目", ""] + [f"- {x}" for x in pending_items[:200]] + ["", "下一步：改完 decisions.yaml 重新运行；评测场景需要按 v0.2 改写后重跑（见 eval/README.md）。"]
    REPORT.write_text("\n".join(R), encoding="utf-8")
    print("\n".join(R[:6]))
    print(f"→ {OUT}\n→ {REPORT}")
    return 0


def _merge_course(p: dict, facts: list, kept: set, qs: list, fqs: list, rfs: list, errors: list) -> str:
    """把 course_safety_net_sim.yaml 合并进协议：服务时段、红旗去向、紧急页文案、结局与提醒规则、任务派发、结案、签到题。
    内容全部来自模拟临床负责人（AI 医学视角），协议里 course.simulated = true，界面与 BP 必须标"模拟"。"""
    if not COURSE.exists():
        return "未合并（没有 course_safety_net_sim.yaml）"
    c = _load(COURSE) or {}
    course = {k: c[k] for k in COURSE_KEYS if c.get(k) is not None}
    course["simulated"] = bool((c.get("meta") or {}).get("simulated", True))
    rule_ids = {r["id"] for r in rfs}
    routes = course.get("red_flag_routes") or {}
    missing = sorted(rule_ids - set(routes))
    if missing:
        errors.append("course.red_flag_routes 缺少规则：" + "、".join(missing))
    course["red_flag_routes"] = {k: v for k, v in routes.items() if k in rule_ids}
    p["course"] = course
    ci = c.get("checkin") or {}
    for f in ci.get("new_facts") or []:
        if f["key"] not in kept:
            facts.append({**f, "clinical_review_required": True})
            kept.add(f["key"])
    drop_ids = set(ci.get("drop_from_followup") or [])
    fqs[:] = [q for q in fqs if q["id"] not in drop_ids]
    by_id = {q["id"]: i for i, q in enumerate(fqs)}
    pre_ids = {q["id"] for q in qs}
    for baseline in c.get("pre_visit_baseline_questions") or []:
        if baseline["fact_key"] not in kept:
            errors.append(f"首诊基线问题缺少事实定义：{baseline['fact_key']}")
            continue
        if baseline["id"] in pre_ids:
            errors.append(f"首诊基线问题 id 重复：{baseline['id']}")
            continue
        qs.append({**baseline, "stage": "pre_visit"})
        pre_ids.add(baseline["id"])
    for q in ci.get("questions") or []:
        q = {**q, "stage": "follow_up"}
        if q["id"] in pre_ids:
            errors.append(f"签到题 id 与首诊题重复：{q['id']}")
            continue
        if q["id"] in by_id:
            fqs[by_id[q["id"]]] = {**fqs[by_id[q["id"]]], **q}
        else:
            fqs.append(q)
            by_id[q["id"]] = len(fqs) - 1
    anchors = c.get("scale_anchors") or {}
    for q in qs + fqs:
        if q.get("type") == "scale" and q["fact_key"] in anchors:
            q["anchors"] = {int(k): v for k, v in anchors[q["fact_key"]].items()}
    p["screening"] = {"grid_enabled": True, "grid_preface": c.get("private_preface"),
                      "pre_visit_grid_title": c.get("pre_visit_grid_title"),
                      "pre_visit_grid": list(c.get("pre_visit_red_flag_grid") or []), "checkin_grid": list(ci.get("red_flag_grid") or [])}
    for o in course.get("outcomes") or []:
        if o["key"] not in p["followup"]["change_facts"] and o["key"] in kept:
            p["followup"]["change_facts"].append(o["key"])
    return (f"已合并（模拟临床稿）：服务时段 {len(course.get('service_windows') or [])} 段 · 红旗去向 {len(course['red_flag_routes'])} 条 · "
            f"结局 {len(course.get('outcomes') or [])} 个 · 提醒规则 {len(course.get('recovery_rules') or [])} 条 · "
            f"签到题 {len(ci.get('questions') or [])} 道（红旗一屏 {len(ci.get('red_flag_grid') or [])} 行）")


def _stance(n_decided: int, simulated: bool) -> str:
    if n_decided == 0:
        return "医生尚未做出任何决定，这份 v0.2 只是 AI 草案，不得在 BP、视频或演示里称为正式版；演示继续用 v0.1 并标工程占位。"
    if simulated:
        return (f"这 {n_decided} 条决定来自模拟临床负责人（AI 以医学视角模拟，不是执业医师）：真实医生已决定 0 条。"
                "BP、视频、演示里只能写'模拟临床负责人决定，待真实医生复核'，不得写'医生已决定'或'临床审核'；协议状态保持 draft。")
    return f"只能称为 v0.2 候选（医生已决定 {n_decided} 条），全部决定并有第二复核者签字前不称正式版。"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    a = ap.parse_args()
    if a.init:
        init()
        sys.exit(0)
    sys.exit(build())
