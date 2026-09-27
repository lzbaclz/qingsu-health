#!/usr/bin/env python3
"""生成《医生两小时决定表》：第二轮评审建议先不求 146 条全审，只定"实名 + 适用范围 + 18 条红旗"。

  backend/.venv/bin/python protocols/review/make_2h_sheet.py   → protocols/review/医生两小时决定表.md

内容来自 AI 草案 lbp_adult_v0.2_ai_draft.yaml；红旗的触发条件从表达式翻成中文，原表达式附在后面备查。
医生在表上写决定，工程当场抄进 decisions.yaml（scope 与 red_flags 两节），再运行 make protocol-v02。
"""
from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
DRAFT = ROOT / "protocols" / "lbp_adult_v0.2_ai_draft.yaml"
OUT = ROOT / "protocols" / "review" / "医生两小时决定表.md"
SEV = {"urgent": "紧急：当天急诊", "same_day": "当天联系", "routine": "常规复核"}
TRIG = {"stop_questioning": "终止问询，只留联系按钮", "continue": "继续问询"}
FLAG_RF = {"rf_bladder_bowel", "rf_saddle", "rf_ces_sexual", "rf_bilateral_only", "rf_progressive_weakness",
           "rf_weight_loss_or_cancer", "rf_out_of_scope"}


def humanize(expr: str, facts: dict) -> str:
    def lab(k: str) -> str:
        return f"「{facts.get(k, {}).get('label', k)}」"

    def opt(k: str, v: str) -> str:
        for o in facts.get(k, {}).get("options", []) or []:
            if o.get("value") == v:
                return o.get("label", v)
        return v

    s = expr
    s = re.sub(r"facts\.(\w+)\.present", lambda m: f"{lab(m.group(1))}为有", s)
    s = re.sub(r"facts\.(\w+)\.denied", lambda m: f"{lab(m.group(1))}为没有", s)
    s = re.sub(r"facts\.(\w+)\.uncertain", lambda m: f"{lab(m.group(1))}为不确定", s)
    s = re.sub(r"facts\.(\w+)\.unknown", lambda m: f"{lab(m.group(1))}未明确", s)
    s = re.sub(r"facts\.(\w+)\.(?:any|has)\(\[?([^\])]*)\]?\)",
               lambda m: f"{lab(m.group(1))}包含 " + "、".join(opt(m.group(1), x.strip(" '\"")) for x in m.group(2).split(",") if x.strip()), s)
    s = re.sub(r"facts\.(\w+)\.value\s*==\s*'([^']+)'", lambda m: f"{lab(m.group(1))}为 {opt(m.group(1), m.group(2))}", s)
    s = re.sub(r"facts\.(\w+)\.gte\((\d+)\)", lambda m: f"{lab(m.group(1))} ≥ {m.group(2)}", s)
    s = re.sub(r"facts\.(\w+)\.lte\((\d+)\)", lambda m: f"{lab(m.group(1))} ≤ {m.group(2)}", s)
    s = re.sub(r"\bnot\b", "并非", s)
    s = re.sub(r"\band\b", "并且", s)
    s = re.sub(r"\bor\b", "或", s)
    return s


def cell(t) -> str:
    return str(t or "").replace("\n", " ").replace("|", "／").strip()


def main() -> None:
    d = yaml.safe_load(DRAFT.read_text(encoding="utf-8"))
    facts = {f["key"]: f for f in d["facts"]}
    sc = d["scope"]
    L = ["# 医生两小时决定表（实名 + 适用范围 + 题数上限 + 18 条红旗）", "",
         "> 第二轮评审的建议：这周先不求 146 条全审。坐下两小时，把下面三部分定下来，BP 第 5、9 页就有了真实的医生决定。",
         "> 每行写：**采纳 / 修改 / 删除**，修改的写改成什么，**每条一句理由**。与 AI 草案不同的地方正是评委最想看的，分歧不要妥协。",
         "> 工程当场把决定抄进 `protocols/review/decisions.yaml`（meta、scope、red_flags 三节），会后运行 `make protocol-v02` 与 `make evidence`。",
         "> 本表由 `protocols/review/make_2h_sheet.py` 从 AI 草案生成；AI 草案不是医学结论。",
         "> 时间不够时按这个顺序：实名 → 18 条红旗 → 这一轮新增的 5 个决定 → 适用范围 → 题数上限。全部约 2 小时 15 分钟。", "",
         "## 一、实名与投入（约 10 分钟，写进 decisions.yaml 的 meta）", "",
         "| 项 | 填写 |", "|---|---|",
         "| 姓名 | |", "| 职称 | |", "| 科室 | |", "| 机构 | |", "| 每周可投入小时 | |", "| 审核日期 | |",
         "| 第二位独立复核者（姓名、职称；可以决赛前再定） | |",
         "| 所在机构是否知情；是否已授权患者招募（如实写，未授权就写未授权） | |", "",
         "## 二、适用范围（约 30 分钟）", "",
         "| 项 | AI 草案 | 决定 | 改成 | 理由 |", "|---|---|---|---|---|"]
    for i, x in enumerate(sc.get("inclusion", []), 1):
        L.append(f"| 纳入 {i} | {cell(x)} | | | |")
    for i, x in enumerate(sc.get("exclusion", []), 1):
        L.append(f"| 排除 {i} | {cell(x)} | | | |")
    L += [f"| 全程紧急提示 | {cell(sc.get('emergency_notice'))} | | | |",
          f"| 不适用时的说明 | {cell(sc.get('out_of_scope_message'))} | | | |",
          f"| 服务时间与谁看队列 | {cell(sc.get('service_hours'))} | | | |",
          "| 门诊电话（紧急页主按钮） | 未填写；演示用占位号 0755-00000000 | | | |",
          "| 开始页确认：年满 18 岁（16–17 岁是否纳入） | 现为：选\"不对\"即不进入 | | | |",
          "| 开始页确认：目前没有怀孕（产后 6 周内是否也排除） | 现为：选\"不对\"即不进入 | | | |", "",
          "## 二（补）、患者要答几题（约 10 分钟）", "",
          "> 患者端现在显得复杂，主要因为题多。v0.1 最多问 16 题，模拟病例平均约 14 题（含核对与澄清）；"
          f"AI 草案把上限提到 {d.get('max_questions')} 题，另有 {sum(1 for q in d['questions'] if q.get('tier', 2) == 1)} 道必问题不计入上限，最坏情况下一位患者要答三十多题。",
          "> 工程建议：先定一个更小的上限，必问题只留真正的红旗；其余信息靠患者自己的描述 + 面诊时补问（医生端速览会列出没问到的关键项）。",
          "",
          "| 项 | AI 草案 | 决定 | 改成 | 理由 |", "|---|---|---|---|---|",
          f"| 最多问几题（不含必问题） | {d.get('max_questions')} | | | |",
          "| 必问题（不计入上限）：" + "；".join(f"{i}. {facts.get(q['fact_key'], {}).get('label', q['fact_key'])}"
                                              for i, q in enumerate([q for q in d['questions'] if q.get('tier', 2) == 1], 1))
          + " | 以上全部必问 | | 只保留第 ___ 条 | |",
          "",
          "## 三、18 条红旗（约 70 分钟，⚠ 为 AI 自认没把握、请优先）", "",
          "| # | 编号 | 名称 | 触发条件 | 紧急程度 | 触发后 | 给患者看的话 | 决定 | 理由 |", "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(d["red_flags"], 1):
        warn = "⚠ " if r["id"] in FLAG_RF else ""
        L.append(f"| {i} | {warn}{r['id']} | {cell(r.get('label'))} | {cell(humanize(r.get('when', ''), facts))} | "
                 f"{SEV.get(r.get('severity'), r.get('severity'))} | {TRIG.get(r.get('on_trigger', 'continue'), r.get('on_trigger'))} | "
                 f"{cell(r.get('patient_message')) or '（仅供医生复核，不向患者展示）'} | | |")
    # 第三轮评审新增：必须由医生拍板的处理方式（写进 decisions.yaml 的 policies）
    v01 = yaml.safe_load((DRAFT.parent / "lbp_adult_v0.1.yaml").read_text(encoding="utf-8"))
    gl = (v01.get("followup") or {}).get("plain_language") or []
    L += ["", "## 三（补）、这一轮新增的 5 个决定（约 15 分钟，写进 decisions.yaml 的 policies）", "",
          "| # | 事项 | 现在系统怎么做（工程默认，可改） | 决定 | 改成 | 理由 |", "|---|---|---|---|---|---|",
          "| P1 | 患者原话提到红旗（如\"小便憋不住\"），核对时又说\"不对\" | 仍按紧急排在列表最前，标\"待电话核实\"；速览第一条就是它；摘要列\"待核实\"；"
          "病历初稿写\"需核实\"，不写\"否认\" | | | |",
          "| P2 | 红旗任务多久内、由谁电话联系患者 | AI 草案：紧急类护士 15 分钟内；当天类当天；常规类医生下次核对时；服务时间外页面提示自行急诊，次日首个处理 | | | |",
          "| P3 | 给患者的说明怎么整理 | 默认用下面的术语对照表：分条、在术语后加一句大白话，医生的字一个不改，不调用模型；"
          "模型改写只在医生同意后打开，要点以外的新内容发送前必须删掉或写理由，并自动加 AI 标注 | | | |",
          "| P4 | 12 条术语对照（见下表） | 逐条采纳 / 修改 / 删除 | | | |",
          "| P5 | 测试任务卡 B 加一句\"去年也闪过一次腰，休息几天就好了\" | 用于隐蔽型植入错抽：系统会把\"这次开始多久\"故意放成\"超过 3 个月\"，引文取这句 | | | |", "",
          "术语对照表（P4）：", "", "| 术语 | 给患者的大白话 | 决定 | 改成 |", "|---|---|---|---|"]
    L += [f"| {cell(g.get('term'))} | {cell(g.get('plain'))} | | |" for g in gl]
    L += ["", "## 四、原始表达式（备查，工程用）", ""]
    for r in d["red_flags"]:
        L.append(f"- `{r['id']}`：`{cell(r.get('when'))}`")
    L += ["", "## 五、会后", "",
          "1. 工程把决定写进 decisions.yaml，运行 `make protocol-v02`。这时 v0.2 才有第一批医生决定；在此之前，任何对外材料都不出现\"v0.2\"。",
          "2. 运行 `make evidence`，证据表会自动显示\"医生已决定 X / 146（红旗 Y / 18）\"。",
          "3. 剩下的事实与问题（128 条）决赛前再审；分歧理由保留在 decisions.yaml 的 note 里。"]
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
