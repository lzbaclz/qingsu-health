#!/usr/bin/env python3
"""生成盲评材料：对若干场景，产出 A/B/C 三份摘要，随机编号，附答案。

用法：cd backend && .venv/bin/python ../eval/blind_review/prepare.py --split examples --n 4
输出：eval/blind_review/packet_<时间>.md（给评审）与 answer_key_<时间>.json（评审不可见）
说明：B 组"普通模型摘要"在 mock 模式下只是原话复述；请在 TIJI_LLM_PROVIDER=anthropic 下生成正式材料。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import random
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))
os.environ["TIJI_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix='tiji_blind_')}/b.db"

from app.db import init_db, session_scope  # noqa: E402
from app.llm import get_provider  # noqa: E402
from app.protocol import get_protocol  # noqa: E402
from app.summary.build import latest_summary  # noqa: E402
from runner import _play, load_scenarios  # noqa: E402


def _render_product(content: dict) -> str:
    def j(items: list[str]) -> str:
        return "；".join(items) if items else "—"

    lines = [f"**主诉与时间线**：{content['headline']}", "", f"**叙述**：{content.get('narrative', '')}", "",
             "**已明确**：" + j([f"{k['label']}：{k['value_label']}" for k in content["key_facts"]]),
             "**明确否认**：" + j([k["label"] for k in content["denied"]]),
             "**尚未明确**：" + j([f"{k['label']}（{k['value_label']}）" for k in content["unknown"] if k.get("required")]),
             "**表达不确定**：" + j([f"{k['label']}：{k['value_label']}" for k in content["uncertain"]]),
             "**矛盾**：" + j([f"{k['label']}：{k['value_label']}" for k in content["conflicts"]]),
             "**关注项**：" + j([f"[{a['severity']}] {a['label']}" for a in content["alerts"]])]
    return "\n".join(lines)


def _render_form(content: dict) -> str:
    """A 组：只有问答结果，无自由文本抽取；不区分未问/未答，模拟表单的典型呈现。"""
    rows = [f"{k['label']}：{k['value_label']}" for k in content["key_facts"]]
    rows += [f"{k['label']}：否" for k in content["denied"]]
    rows += [f"{k['label']}：（空）" for k in content["unknown"]]
    return "\n".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="examples")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    random.seed(args.seed)
    init_db()
    scenarios = [s for s in load_scenarios(args.split) if s.get("kind", "pre_visit") == "pre_visit"][: args.n]
    provider = get_provider()
    packet, key = [], {}
    for sc in scenarios:
        proto = get_protocol(sc.get("protocol_id") or "lbp_adult_v0.1")
        with session_scope() as session:
            enc_c, _, _ = _play(session, sc["inputs"], kind="pre_visit", code=f"BLIND-C-{sc['id']}", parent_id=None, arm="full", protocol_id=proto.protocol_id)
            c_text = _render_product(latest_summary(session, enc_c.id).content)
            enc_a, _, _ = _play(session, sc["inputs"], kind="pre_visit", code=f"BLIND-A-{sc['id']}", parent_id=None, arm="form_only", protocol_id=proto.protocol_id)
            a_text = _render_form(latest_summary(session, enc_a.id).content)
        raw = sc["inputs"].get("free_text", "")
        answers = "；".join(f"{k}={v}" for k, v in (sc["inputs"].get("answers") or {}).items())
        b_text = provider.narrative([f"患者原话：{raw}", f"问答：{answers}"], proto)
        arms = [("A", a_text), ("B", b_text), ("C", c_text)]
        random.shuffle(arms)
        codes = [f"{sc['id']}-{i+1}" for i in range(3)]
        packet.append(f"# 病例 {sc['id']}（{sc['title']}）\n\n> 原始材料：身体图 {sc['inputs'].get('body_map')}；原话：{raw}；问答：{answers}\n")
        for code, (arm, text) in zip(codes, arms):
            packet.append(f"## 摘要 {code}\n\n{text}\n")
            key[code] = arm
    out = ROOT / "eval" / "blind_review"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    (out / f"packet_{stamp}.md").write_text("\n".join(packet), encoding="utf-8")
    (out / f"answer_key_{stamp}.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {out / f'packet_{stamp}.md'}（评审用）\n→ {out / f'answer_key_{stamp}.json'}（评审不可见）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
