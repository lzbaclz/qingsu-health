#!/usr/bin/env python3
"""可用性测试汇总：读取患者编号以 UT- 开头的记录（UT-P01-A = 参与者 P01、任务卡 A）的埋点与流程数据，
合并主持人手工表（eval/user_test/主持人记录.csv），输出 eval/user_test/汇总_<时间>.md / .json。

用法：cd backend && .venv/bin/python ../eval/user_test/summarize.py [--db sqlite:///路径]
指标与 docs/05 §6 对应：完成率、用时中位数、复述下一步正确率、卡 C 看到并理解紧急提示的比例等。
另统计"植入错抽"（第二轮评审 §3.2 Q3）：卡 A / B 在 TIJI_USER_TEST_PLANT=1 下故意放一条卡片情境里没有的信息，
看真人在一键核对里点"不对"的比例——这个数字回答"真实的人会不会一路点'对'"，评测里的模拟患者回答不了。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import pathlib
import statistics
import sys
import time
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
UT = ROOT / "eval" / "user_test"


def _app(db: str | None):
    if db:
        os.environ["TIJI_DATABASE_URL"] = db
    sys.path.insert(0, str(ROOT / "backend"))
    from sqlmodel import select

    from app import models as M
    from app.db import init_db, session_scope
    init_db()
    return M, session_scope, select


def _read_manual() -> dict[str, dict]:
    path = UT / "主持人记录.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        return {row["code"].strip(): row for row in csv.DictReader(f) if row.get("code")}


def _flag(v: str | None) -> int | None:
    v = (v or "").strip()
    return 1 if v in ("1", "是", "y", "yes", "Y") else 0 if v in ("0", "否", "n", "no", "N") else None


def collect(db: str | None) -> list[dict]:
    M, session_scope, select = _app(db)
    manual = _read_manual()
    rows = []
    with session_scope() as s:
        patients = s.exec(select(M.Patient).where(M.Patient.display_code.like("UT-%"))).all()
        for pat in patients:
            code = pat.display_code
            parts = code.split("-")
            participant, card = (parts[1], parts[2]) if len(parts) >= 3 else (code, "?")
            for enc in s.exec(select(M.Encounter).where(M.Encounter.patient_id == pat.id)).all():
                if enc.kind == "pre_visit" and card == "D" and enc.doctor_confirmed_at is not None:
                    continue  # 卡 D 的"上次就诊"是夹具，不计入
                evs = s.exec(select(M.UsageEvent).where(M.UsageEvent.encounter_id == enc.id)).all()
                asked = s.exec(select(M.AskedQuestion).where(M.AskedQuestion.encounter_id == enc.id)).all()
                alerts = s.exec(select(M.Alert).where(M.Alert.encounter_id == enc.id)).all()
                kinds = Counter(a.kind for a in asked)
                statuses = Counter(a.answer_status for a in asked if a.kind == "protocol")
                ev_by = defaultdict(list)
                for e in evs:
                    ev_by[e.type].append(e.payload)
                verif = ev_by.get("verification", [])
                plant = _plant_outcome(s, M, select, enc)
                start = enc.created_at
                minutes = round((enc.patient_confirmed_at - start).total_seconds() / 60, 2) if enc.patient_confirmed_at else None
                step = {p.get("step"): p for p in ev_by.get("step_submit", [])}
                m = manual.get(code, {})
                rows.append({
                    "code": code, "participant": participant, "card": card, "encounter_id": enc.id, "kind": enc.kind,
                    "completed": enc.patient_confirmed_at is not None, "minutes": minutes,
                    "body_seconds": round(step.get("body", {}).get("ms", 0) / 1000, 1) if "body" in step else None,
                    "describe_wait_seconds": round(step.get("describe", {}).get("wait_ms", 0) / 1000, 1) if "describe" in step else None,
                    "questions": kinds.get("protocol", 0), "clarifications": kinds.get("clarification", 0),
                    "verifications": kinds.get("verification", 0),
                    "unknown_or_skip": statuses.get("unknown", 0) + statuses.get("skipped", 0),
                    "verify_items": sum(int(v.get("items", 0) or 0) for v in verif),
                    "verify_rejects": sum(int(v.get("reject", 0) or 0) for v in verif),
                    "confirm_edits": len(ev_by.get("confirm_edit", [])),
                    "urgent_screen": bool(ev_by.get("urgent_screen")),
                    "urgent_actions": ",".join(str(p.get("action")) for p in ev_by.get("urgent_action", [])),
                    "notice_shown": any(a.notice_entry_id for a in alerts),
                    "retell_ok": _flag(m.get("retell_ok")), "burden": int(m["burden"]) if (m.get("burden") or "").strip().isdigit() else None,
                    "saw_notice": _flag(m.get("saw_notice")), "understood_notice": _flag(m.get("understood_notice")),
                    "notes": (m.get("notes") or "").strip(),
                    **plant,
                })
    return rows


def _plant_outcome(s, M, select, enc) -> dict:
    """这次就诊有没有被植入错抽；植入的那条在一键核对里被点了什么；没点"不对"的话，确认页有没有改掉。"""
    log = s.exec(select(M.AuditLog).where(M.AuditLog.action == "usertest.plant", M.AuditLog.target_id == enc.id)).first()
    if not log:
        return {"planted": False}
    key = log.detail.get("fact_key")
    decision = None
    for e in s.exec(select(M.Entry).where(M.Entry.encounter_id == enc.id, M.Entry.kind == "answer").order_by(M.Entry.seq)).all():
        if e.payload.get("kind") == "verification" and key in (e.payload.get("decisions") or {}):
            decision = e.payload["decisions"][key]
            break
    corrected = any(e.payload.get("fact_key") == key for e in s.exec(
        select(M.Entry).where(M.Entry.encounter_id == enc.id, M.Entry.kind == "correction")).all())
    return {"planted": True, "plant_key": key, "plant_quote": log.detail.get("quote"),
            "plant_type": log.detail.get("plant_type") or ("subtle" if log.detail.get("card") == "B" else "obvious"),
            "plant_decision": decision or "未出现在核对里", "plant_corrected_on_confirm": corrected}


def aggregate(rows: list[dict]) -> dict:
    n = len(rows)
    done = [r for r in rows if r["completed"]]
    mins = [r["minutes"] for r in done if r["minutes"] is not None]
    retell = [r["retell_ok"] for r in rows if r["retell_ok"] is not None]
    c_rows = [r for r in rows if r["card"] == "C"]
    c_ok = [1 if (r["notice_shown"] and r["understood_notice"] == 1) else 0 for r in c_rows if r["understood_notice"] is not None]
    answered = sum(r["questions"] for r in rows)
    return {
        "participants": len({r["participant"] for r in rows}), "sessions": n,
        "completion_rate": round(len(done) / n, 3) if n else None,
        "median_minutes": round(statistics.median(mins), 2) if mins else None,
        "retell_rate": round(sum(retell) / len(retell), 3) if retell else "待主持人填写",
        "card_c_notice_rate": round(sum(c_ok) / len(c_ok), 3) if c_ok else ("待主持人填写" if c_rows else "无卡 C"),
        "mean_questions": round(answered / n, 1) if n else None,
        "unknown_or_skip_rate": round(sum(r["unknown_or_skip"] for r in rows) / answered, 3) if answered else None,
        "verify_reject_rate": round(sum(r["verify_rejects"] for r in rows) / max(1, sum(r["verify_items"] for r in rows)), 3),
        "mean_burden": round(statistics.mean([r["burden"] for r in rows if r["burden"]]), 2) if any(r["burden"] for r in rows) else "待主持人填写",
        **_plant_agg(rows),
    }


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """二项比例的 Wilson 95% 置信区间。样本只有 5–10 例时区间很宽，报告时必须带上。"""
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0.0, centre - half), 2), round(min(1.0, centre + half), 2))


def _rate_text(k: int, n: int) -> str:
    ci = wilson(k, n)
    return f"{k} / {n}" + (f"（95% 区间 {int(ci[0] * 100)}%–{int(ci[1] * 100)}%）" if ci else "")


def _plant_agg(rows: list[dict]) -> dict:
    pl = [r for r in rows if r.get("planted")]
    shown = [r for r in pl if r["plant_decision"] in ("confirm", "reject", "unsure")]
    rej = sum(r["plant_decision"] == "reject" for r in shown)
    uns = sum(r["plant_decision"] == "unsure" for r in shown)
    fixed_later = sum(r["plant_decision"] != "reject" and r["plant_corrected_on_confirm"] for r in pl)
    by_type = {}
    for t in ("obvious", "subtle"):
        st = [r for r in shown if r.get("plant_type") == t]
        k = sum(r["plant_decision"] == "reject" for r in st)
        by_type[t] = {"shown": len(st), "rejected": k, "ci95": wilson(k, len(st)), "text": _rate_text(k, len(st)) if st else "未出现"}
    return {"plant_by_type": by_type,
            "planted_n": len(pl), "planted_shown": len(shown), "planted_rejected": rej, "planted_unsure": uns,
            "planted_confirmed": sum(r["plant_decision"] == "confirm" for r in shown), "planted_fixed_on_confirm": fixed_later,
            "planted_reject_rate": round(rej / len(shown), 3) if shown else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    rows = collect(a.db)
    if not rows:
        print("没有找到患者编号以 UT- 开头的记录：测试还没开始，或编号没按 UT-P01-A 的格式填写。不生成汇总。")
        return 1
    agg = aggregate(rows)
    stamp = time.strftime("%Y%m%d_%H%M")
    by_card = defaultdict(list)
    for r in rows:
        by_card[r["card"]].append(r)
    L = [f"# 模拟交互测试汇总（{time.strftime('%Y-%m-%d %H:%M')}）", "",
         "> 参与者用任务卡上的模拟情境、自己的话作答；不收集真实健康信息。20 人做两张卡仍是 20 名参与者。", "",
         "| 指标 | 值 | 目标（docs/05 §6） |", "|---|---|---|",
         f"| 参与者 / 任务卡 | {agg['participants']} / {agg['sessions']} | 10 / 20（本轮） |",
         f"| 完成率 | {agg['completion_rate']} | ≥ 0.8 |",
         f"| 用时中位数（分钟，开始到确认） | {agg['median_minutes']} | ≤ 4 |",
         f"| 复述下一步正确率 | {agg['retell_rate']} | ≥ 0.9 |",
         f"| 卡 C：看到并理解紧急提示 | {agg['card_c_notice_rate']} | 必须报告 |",
         f"| 平均提问数 | {agg['mean_questions']} | — |",
         f"| 不清楚/跳过占比 | {agg['unknown_or_skip_rate']} | — |",
         f"| 一键核对中选\"不对\"的比例 | {agg['verify_reject_rate']} | — |",
         f"| 主观负担（1–5） | {agg['mean_burden']} | — |",
         f"| 植入错抽被点\"不对\"（卡 A/B） | {agg['planted_rejected']} / {agg['planted_shown']}"
         f"（\"不确定\" {agg['planted_unsure']}，点\"对\" {agg['planted_confirmed']}，确认页才改掉 {agg['planted_fixed_on_confirm']}；"
         f"植入 {agg['planted_n']} 次） | 必须报告；没点\"不对\"的每一例写进备注 |",
         f"| 　其中显眼型（错误值旁边就是反驳它的原话，卡 A） | {agg['plant_by_type']['obvious']['text']} | 只代表上限 |",
         f"| 　其中隐蔽型（引文看起来支持错误值，卡 B） | {agg['plant_by_type']['subtle']['text']} | 更接近真实错抽 |", "",
         "> 样本很小：5 例里点对 4 例，95% 区间约 38%–96%。只能说\"有/没有明显问题\"，不能说成总体比例。", "",
         "## 按任务卡", "", "| 卡 | 次数 | 完成 | 用时中位数 | 紧急终止页 |", "|---|---|---|---|---|"]
    for card, rs in sorted(by_card.items()):
        ms = [r["minutes"] for r in rs if r["minutes"] is not None]
        L.append(f"| {card} | {len(rs)} | {sum(r['completed'] for r in rs)} | {round(statistics.median(ms), 2) if ms else '—'} | "
                 f"{sum(r['urgent_screen'] for r in rs)} |")
    L += ["", "## 逐条", "", "| 编号 | 完成 | 分钟 | 提问 | 核对条目/不对 | 确认页修改 | 紧急页/操作 | 复述 | 负担 | 备注 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: x["code"]):
        L.append(f"| {r['code']} | {'✓' if r['completed'] else '✗'} | {r['minutes'] or '—'} | {r['questions']} | {r['verify_items']}/{r['verify_rejects']} | "
                 f"{r['confirm_edits']} | {'是' if r['urgent_screen'] else '—'} {r['urgent_actions']} | {r['retell_ok'] if r['retell_ok'] is not None else '待填'} | "
                 f"{r['burden'] or '待填'} | {r['notes']} |")
    out_md, out_js = UT / f"汇总_{stamp}.md", UT / f"汇总_{stamp}.json"
    out_md.write_text("\n".join(L), encoding="utf-8")
    out_js.write_text(json.dumps({"aggregate": agg, "rows": rows}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("\n".join(L[:16]))
    print(f"→ {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
