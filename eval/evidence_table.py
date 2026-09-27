#!/usr/bin/env python3
"""生成 BP 第 5 页「证据表」：收集 eval/results、eval/user_test、protocols/review 与访谈记录的最新状态，
写到 eval/results/证据表.md。

每一行都标注证据类型：已完成（真实发生、可复现）/ 模拟（模拟数据或模拟人）/ 待临床（需临床审核后才算数）/ 待合作（需门诊）。
没有跑过的行写"未运行"，没做的事写"未进行"，不编数字。

三层结果并列（第二轮评审 §3.2 Q3）：
- 模型刚读完原话：还没核对与问卷时的抽取结果；
- 粗心患者：一键核对一律点"对"，再走完问卷——错抽与编造会原样留下，漏抽仍由问卷兜住；
- 认真患者：模拟患者知道真值、据此核对——等于用答案核对答案，只证明流程能闭合，不证明真人会抓到错抽。
真人会不会抓到错抽，看"模拟交互测试"一行的植入错抽比例。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROTOCOL = os.environ.get("TIJI_DEFAULT_PROTOCOL", "lbp_adult_v0.1")  # 证据表只取主协议的结果
RES = ROOT / "eval" / "results"
UT = ROOT / "eval" / "user_test"
USD_CNY = 7.1  # 与 runner.py 一致的估算汇率假设


def latest(split: str, provider_prefix: str, effort: str | None = None, patient: str = "attentive", arm: str = "full",
           model: str | None = None) -> dict | None:
    best = None
    for p in RES.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        m = d.get("meta") or {}
        if m.get("split") != split or m.get("arm", "full") != arm or not str(m.get("provider", "")).startswith(provider_prefix):
            continue
        if m.get("protocol") != PROTOCOL or m.get("patient", "attentive") != patient:
            continue
        if effort and m.get("effort") != effort:
            continue
        if model and m.get("model") != model:
            continue
        if "extraction_errors_by_code" not in (d.get("aggregate") or {}):
            continue  # 旧版运行器的报告，不含抽取层指标
        if best is None or m.get("at", "") > best["meta"].get("at", ""):
            best = d | {"_file": p.name}
    return best


def cell_extract(d: dict | None) -> str:
    if not d:
        return "未运行"
    x = d["aggregate"].get("extraction_errors_by_code", {})
    return (f"编造 {x.get('X2_fabrication', 0)} · 错抽 {x.get('X8_misread', 0)} · 漏抽 {x.get('X1_miss', 0)} · "
            f"红旗漏识别 {x.get('X4_text_escalation_miss', 0)}")


def cell_final(d: dict | None) -> str:
    if not d:
        return "未运行"
    a = d["aggregate"]
    e = a.get("errors_by_code", {})
    n = a.get("n_scenarios") or 0
    ok = round((a.get("scenario_pass_rate") or 0) * n)
    return (f"{ok}/{n} 无关键错误；编造 {e.get('E2_fabrication', 0)} · 漏升级 {e.get('E4_missed_escalation', 0)} · "
            f"理解错 {e.get('E8_misunderstanding', 0)} · 越界 {e.get('E6_out_of_scope_advice', 0)}")


def cell_compare(d: dict | None) -> str:
    if not d:
        return "未运行"
    a = d["aggregate"]
    e = a.get("errors_by_code", {})
    n = a.get("n_scenarios") or 0
    ok = round((a.get("scenario_pass_rate") or 0) * n)
    urgent_missed = sum(1 for r in d.get("results", []) for x in r.get("errors", [])
                        if x.get("code") == "E4_missed_escalation" and x.get("key") in ("rf_bladder_bowel", "rf_saddle", "rf_ces_bilateral",
                                                                                         "rf_ces_sexual", "rf_progressive_weakness"))
    return (f"{ok}/{n} 无关键错误；漏升级 {e.get('E4_missed_escalation', 0)}（其中紧急 {urgent_missed}）· "
            f"矛盾未发现 {e.get('E7_conflict_not_surfaced', 0)} · 理解错 {e.get('E8_misunderstanding', 0)} · "
            f"非关键遗漏 {e.get('E9_minor_omission', 0)}；平均 {a.get('mean_questions_asked')} 题")


def cell_cost(d: dict | None) -> str:
    if not d:
        return "—"
    m = d.get("meta") or {}
    u = m.get("usage") or {}
    if not u.get("calls"):
        return "不调用模型"
    lat = (u.get("latency_s") or {}).get("extract") or {}
    per = m.get("usd_per_scenario")
    money = f"每次就诊约 ${per:.4f}（约 ¥{per * USD_CNY:.3f}）；" if per is not None else ""
    return f"{money}抽取耗时 p50 {lat.get('p50')} 秒 / p90 {lat.get('p90')} 秒"


def review_status() -> str:
    """医生审核进度：直接数 decisions.yaml，不靠手填。"""
    try:
        import yaml
        d = yaml.safe_load((ROOT / "protocols" / "review" / "decisions.yaml").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return "未找到 decisions.yaml"
    total = decided = rf_total = rf_decided = 0
    for sec in ("facts", "questions", "red_flags"):
        for v in (d.get(sec) or {}).values():
            if isinstance(v, dict) and "decision" in v:
                total += 1
                done = v.get("decision") not in (None, "pending")
                decided += done
                if sec == "red_flags":
                    rf_total += 1
                    rf_decided += done
    scope_done = (d.get("scope") or {}).get("decision") not in (None, "pending")
    lead = ((d.get("meta") or {}).get("clinical_lead") or {}).get("name")
    pol = [v for v in (d.get("policies") or {}).values() if isinstance(v, dict)]
    pol_done = sum(v.get("decision") not in (None, "pending") for v in pol)
    detail = (f"红旗 {rf_decided} / {rf_total}；适用范围{'已定' if scope_done else '未定'}；处理方式 {pol_done} / {len(pol)}")
    if (d.get("meta") or {}).get("simulated"):
        # 模拟临床负责人填的决定分栏显示，永远不计入"医生已决定"（第 1 轮团队评审 P0-1）
        return (f"真实医生已决定 0 / {total} 条｜模拟临床负责人已决定 {decided} / {total} 条（{detail}；"
                f"AI 医学视角模拟，待真实医生复核）")
    return f"医生已决定 {decided} / {total} 条（{detail}）；临床负责人{'：' + lead if lead else '未署名'}"


def interview_status() -> str:
    path = ROOT / "docs" / "访谈记录_脱敏.md"
    if not path.exists():
        return "未进行"
    rows = [ln for ln in path.read_text(encoding="utf-8").splitlines() if re.match(r"^\|\s*门诊[A-Z]", ln)]
    done = [r for r in rows if "尚未进行" not in r]
    return f"完成 {len(done)} / {len(rows)} 家" + ("" if done else "（未进行）")


def main() -> None:
    rows = []
    for label, split, prov, eff, kind, model in [
        ("离线词表基线 · 80 个模拟场景", "all", "mock", None, "模拟 · 待临床", None),
        ("离线词表基线 · 20 句口语压力集", "stress", "mock", None, "模拟 · 待临床（词表曾按此集调过）", None),
        ("本机模型 qwen3:4b（数据不出本机）· 口语压力集（20）", "stress", "ollama", None, "模拟 · 待临床", "qwen3:4b"),
        ("本机模型 qwen3:4b · 80 个模拟场景", "all", "ollama", None, "模拟 · 待临床", "qwen3:4b"),
        ("本机模型 gpt-oss:20b（数据不出本机）· 口语压力集（20）", "stress", "ollama", None, "模拟 · 待临床", "gpt-oss:20b"),
        ("真实模型 Claude · 口语压力集（20）", "stress", "anthropic", "medium", "模拟 · 待临床", None),
        ("真实模型 Claude · 锁定集（40）", "locked", "anthropic", None, "模拟 · 待临床", None),
        ("国产模型（兼容接口）· 口语压力集（20）", "stress", "compat", None, "模拟 · 待临床", None),
        ("国产模型（兼容接口）· 锁定集（40）", "locked", "compat", None, "模拟 · 待临床", None),
    ]:
        d = latest(split, prov, eff, model=model)
        dc = latest(split, prov, eff, patient="careless", model=model)
        rows.append((label, cell_extract(d or dc), cell_final(dc), cell_final(d), cell_cost(d or dc), kind,
                     " / ".join(x["_file"] for x in (d, dc) if x) or "—"))
    # 公平对照（第三轮评审 §2.1 Q5）：两组用同一位"如实作答"的模拟患者——脚本没写答案的题也按真实情况回答。
    # 旧的问卷对照让模拟患者对原话里说过的红旗题一律答"不清楚"，漏报是脚本造出来的，已从证据表撤下（结果文件保留）。
    ft = latest("all", "mock", patient="truthful")
    fo = latest("all", "mock", patient="truthful", arm="form_only")
    rows.append(("对照 A · 读原话 + 问卷（同一位如实作答的模拟患者，80 场景）", "—", "—", cell_compare(ft), "不调用模型",
                 "模拟 · 待临床", ft["_file"] if ft else "—"))
    rows.append(("对照 B · 只发固定问卷、不读原话（同一位患者）", "不适用", "—", cell_compare(fo), "不调用模型",
                 "模拟 · 待临床", fo["_file"] if fo else "—"))

    ut = sorted(UT.glob("汇总_*.json"))
    if ut:
        s = json.loads(ut[-1].read_text(encoding="utf-8"))
        a = s.get("aggregate", {})
        bt = a.get("plant_by_type") or {}
        plant = (f"植入错抽被点\"不对\"：显眼型 {bt.get('obvious', {}).get('text', '—')}；隐蔽型 {bt.get('subtle', {}).get('text', '—')}"
                 if a.get("planted_shown") else "植入错抽：未进行")
        rows.append((f"模拟交互测试（{a.get('participants', 0)} 人 / {a.get('sessions', 0)} 张任务卡）",
                     f"完成率 {a.get('completion_rate')}；用时中位数 {a.get('median_minutes')} 分钟", plant,
                     f"复述下一步正确率 {a.get('retell_rate')}；卡 C 看到并理解紧急提示 {a.get('card_c_notice_rate')}", "—",
                     "已完成（模拟情境，非患者）", ut[-1].name))
    else:
        rows.append(("模拟交互测试（目标 10 人 × 2 张卡，含植入错抽）", "未进行", "未进行", "未进行", "—", "待执行", "—"))
    rows += [
        ("门诊访谈（目标 2 家）", interview_status(), "—", "—", "—", "待合作", "docs/访谈记录_脱敏.md"),
        ("协议临床审核（适用范围、事实、问题、红旗）", review_status(), "—", "—", "—", "待临床", "protocols/review/decisions.yaml"),
        ("盲评三组对照（表单 / 普通模型摘要 / 本产品）", "未进行（决赛前）", "—", "—", "—", "待临床", "—"),
    ]
    lines = ["# 证据表（BP 第 5 页）", "",
             f"生成：{time.strftime('%Y-%m-%d %H:%M')}　协议 {PROTOCOL}　由 `eval/evidence_table.py` 自动汇总；未运行、未进行的行不填数字。", "",
             "| 证据 | 模型刚读完原话 | 粗心患者：核对一律点\"对\" | 认真患者：知道真值后核对 | 费用与耗时 | 类型 | 来源文件 |",
             "|---|---|---|---|---|---|---|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    lines += ["", "说明：",
              "- 场景与压力集均由工程起草、尚未经临床审核，所有数字只能称为\"开发基线\"，不能说成临床准确率。",
              "- \"认真患者\"一列由知道真值的模拟患者点出，等于用答案核对答案，只证明流程能闭合；\"粗心患者\"一列更接近最坏情况；真人会不会抓到错抽，看模拟交互测试的植入错抽比例。",
              "- 离线词表曾按压力集发现的问题修过（见 eval/CHANGELOG.md），它在压力集上的数字是事后的，只作兜底基线；对外的能力数字以真实模型为准。",
              "- 锁定集在调试中被查看过（见 eval/CHANGELOG.md），临床审核并改写真值后才算真正锁定。",
              "- 对照 A / B 用同一位如实作答的模拟患者（脚本没写答案的题也按真实情况回答）；只发问卷时，写在原话里的\"好像有\"这类不确定表达记不下来，排在后面的题受 16 题上限限制问不到，身体图与原话的矛盾也发现不了。",
              f"- 费用按公开价估算，汇率按 1 美元约 {USD_CNY} 元假设；\"每次就诊\"= 评测里的一个场景。"]
    out = RES / "证据表.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)
    print("\n".join(lines[4:]))


if __name__ == "__main__":
    main()
