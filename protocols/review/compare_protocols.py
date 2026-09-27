#!/usr/bin/env python3
"""同一组场景在两个协议版本下的红旗触发差异 → eval/results/协议对比_<A>_vs_<B>.md

用法：先分别跑两份评测（runner.py --split all [--protocol X]），再：
  python protocols/review/compare_protocols.py lbp_adult_v0.1 lbp_adult_v0.2_ai_draft
"""
from __future__ import annotations

import glob
import json
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
R = ROOT / "eval" / "results"


def latest(proto: str) -> dict:
    files = sorted(glob.glob(str(R / f"*_full_all_{proto}_mock.json")))
    if not files:
        sys.exit(f"没有找到 {proto} 的评测结果，先运行 runner.py --split all --protocol {proto}")
    return json.loads(pathlib.Path(files[-1]).read_text(encoding="utf-8"))


def main(a_id: str, b_id: str) -> None:
    a, b = latest(a_id), latest(b_id)
    ra = {r["id"]: r for r in a["results"]}
    rb = {r["id"]: r for r in b["results"]}
    ca, cb, rows = Counter(), Counter(), []
    for sid in sorted(ra):
        x, y = ra[sid], rb.get(sid)
        if not y:
            continue
        sa, sb = set(x["alerts"]), set(y["alerts"])
        ca.update(sa)
        cb.update(sb)
        if sa != sb or x["urgent_stop"] != y["urgent_stop"]:
            rows.append((sid, x["title"], sorted(sa), sorted(sb), x["urgent_stop"], y["urgent_stop"]))
    aa, ab = a["aggregate"], b["aggregate"]
    L = [f"# 协议对比 · {a_id} vs {b_id} · 同一组 {len(ra)} 个场景", "",
         f"运行：{a['meta']['at']} / {b['meta']['at']}（离线词表 mock；场景脚本按 v0.1 编写）", "",
         "> 读法：场景脚本只回答 v0.1 的问题，v0.2 新增的问题一律按\"不清楚\"处理，所以 v0.2 的\"关键事实遗漏\"多是版本绑定造成的；",
         "> **有信息量的是红旗触发差异、紧急终止次数和提问数**。医生对比两版时重点看下面的差异行。", "",
         f"| 指标 | {a_id} | {b_id} |", "|---|---|---|",
         f"| 平均提问数（含核对与澄清） | {aa['mean_questions_asked']} | {ab['mean_questions_asked']} |",
         f"| 紧急终止问询的场景 | {aa['urgent_stops']} | {ab['urgent_stops']} |",
         f"| 期望红旗漏触发 E4 | {aa['errors_by_code'].get('E4_missed_escalation', 0)} | {ab['errors_by_code'].get('E4_missed_escalation', 0)} |",
         f"| 脚本未预期的额外触发 E5 | {aa['errors_by_code'].get('E5_unnecessary_escalation', 0)} | {ab['errors_by_code'].get('E5_unnecessary_escalation', 0)} |",
         "", "## 各规则触发次数", "", f"| 规则 | {a_id} | {b_id} |", "|---|---|---|"]
    L += [f"| {r} | {ca.get(r, 0)} | {cb.get(r, 0)} |" for r in sorted(set(ca) | set(cb))]
    L += ["", f"## 结果不同的场景（{len(rows)} / {len(ra)}）", "", "| 场景 | 标题 | A 触发 | B 触发 | A 终止 | B 终止 |", "|---|---|---|---|---|---|"]
    L += [f"| {s} | {t[:26]} | {', '.join(x) or '—'} | {', '.join(y) or '—'} | {'是' if u else '—'} | {'是' if v else '—'} |" for s, t, x, y, u, v in rows]
    L += ["", "## 给医生的三个问题", "",
          "1. B 版新增的规则（双腿同时症状、步态、性功能、肿瘤史伴特征、外伤伴骨折风险、病程超过 6 周仍加重等）触发次数见上表——哪些过于保守、哪些不够？",
          "2. B 版必问题 16 道、平均提问数见上表；你能接受的上限是多少？哪些必问可以降级？",
          "3. 正式切换版本时需要按新问法改写场景脚本并重新审核。"]
    out = R / f"协议对比_{a_id}_vs_{b_id}.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(out)
    print("\n".join(L[6:13]))


if __name__ == "__main__":
    main(*(sys.argv[1:3] if len(sys.argv) >= 3 else ("lbp_adult_v0.1", "lbp_adult_v0.2_ai_draft")))
