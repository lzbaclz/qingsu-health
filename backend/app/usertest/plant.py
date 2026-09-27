"""可用性测试专用：在任务卡 A / B 里故意植入一次"错抽"，统计真人在一键核对里点"不对"的比例。

为什么：评测里"走完核对后关键错误 0"是知道真值的模拟患者点出来的，等于用答案核对答案（第二轮评审 §3.2 Q3）。
能回答"真实的人会不会一路点'对'"的只有真人测试，所以在测试里放一条卡片情境里明确不存在的信息。

边界：
- 只有 TIJI_USER_TEST_PLANT=1（make user-test-backend）时生效；演示与评测默认关闭。
- 只对 UT-Pxx-A / UT-Pxx-B 编号、只在该次就诊的第一段自由描述上植入一次。
- 植入的是"模型输出"这一层：替换或加入一条候选，引文取自参与者自己的原话（能过逐字校验），
  之后的核对、问卷、摘要与真实错抽完全一样。
- 每次植入写审计日志 usertest.plant（卡片、事实、植入值、引文、原来的候选），汇总脚本据此统计；
  测试结束后主持人当场向参与者说明（见 eval/user_test/任务卡与记录表.md）。
"""
from __future__ import annotations

import os
import re
from typing import Optional

from sqlmodel import Session, select

from ..config import settings
from ..llm.provider import CandidateFact, ExtractionOutput
from ..models import AuditLog, Encounter, Patient
from ..protocol.schema import Protocol
from ..tasks.service import audit

PLANTS: dict[str, dict] = {
    # 卡 A · 显眼型：腰酸、腿没有麻 → 植入"疼痛串到臀部或腿：有"。引文多半是"腿没有麻"，错误值旁边就是反驳它的原话。
    "A": {"fact_key": "radiation_present", "status": "present", "value": True, "type": "obvious",
          "why": "卡 A 情境是腰酸、腿没有麻，没有串到腿", "quote_hints": ["腿", "腰"]},
    # 卡 B · 隐蔽型（第三轮评审 §2.1 Q4）：卡片写了"去年也闪过一次腰"，植入"这次开始多久：超过 3 个月"，
    # 引文取这句——引文看起来支持错误值，和压力集里真实错抽"腰疼老毛病了 → 超过 3 个月"同型。
    # 参与者没提去年那次时，退回用"一个多月"那句做引文，记为显眼型。
    "B": {"fact_key": "onset_timing", "status": "present", "value": "over_12_weeks", "type": "subtle",
          "why": "卡 B 这一次是腰不舒服一个多月；去年那次说的是以前，不是这次开始的时间",
          "quote_hints": ["去年", "以前", "之前", "闪过", "老毛病", "犯过"], "fallback_hints": ["月", "周", "星期", "天"]},
}
_CODE = re.compile(r"^UT-P\d+-([A-Z])$")
_CLAUSE = re.compile(r"[^，。,.;；！!？?\n]+")


def enabled() -> bool:
    return settings.user_test_plant or os.environ.get("TIJI_USER_TEST_PLANT") == "1"


def _card(session: Session, enc: Encounter) -> Optional[str]:
    pat = session.get(Patient, enc.patient_id)
    m = _CODE.match((pat.display_code or "") if pat else "")
    return m.group(1) if m else None


def pick_quote(text: str, hints: list[str], max_len: int = 16) -> Optional[str]:
    """从参与者原话里挑一段逐字片段做引文：优先含提示词的短句，太长就截取提示词附近。"""
    clauses = [(m.start(), m.group()) for m in _CLAUSE.finditer(text) if m.group().strip()]
    for h in hints:
        for start, c in clauses:
            i = c.find(h)
            if i < 0:
                continue
            if len(c) <= max_len:
                return c.strip() or None
            lo = max(0, i - max_len // 2)
            return c[lo:lo + max_len].strip() or None
    if clauses:
        return clauses[0][1][:max_len].strip() or None
    return None


def _quote_with(text: str, hints: list[str], max_len: int = 16) -> Optional[str]:
    """只在含提示词的短句里取引文；没有任何短句含提示词时返回 None（与 pick_quote 的"退回第一句"不同）。"""
    clauses = [m.group() for m in _CLAUSE.finditer(text) if m.group().strip()]
    for h in hints:
        for c in clauses:
            i = c.find(h)
            if i < 0:
                continue
            if len(c) <= max_len:
                return c.strip() or None
            lo = max(0, i - max_len // 2)
            return c[lo:lo + max_len].strip() or None
    return None


def maybe_plant(session: Session, enc: Encounter, protocol: Protocol, text: str, out: ExtractionOutput) -> ExtractionOutput:
    if not enabled():
        return out
    card = _card(session, enc)
    spec = PLANTS.get(card or "")
    if not spec or spec["fact_key"] not in protocol.fact_index:
        return out
    done = session.exec(select(AuditLog).where(AuditLog.action == "usertest.plant", AuditLog.target_id == enc.id)).first()
    if done:
        return out
    ptype = spec.get("type", "obvious")
    quote = _quote_with(text, spec["quote_hints"])
    if not quote and spec.get("fallback_hints"):
        quote, ptype = _quote_with(text, spec["fallback_hints"]), "obvious"
    if not quote:
        quote, ptype = pick_quote(text, []), "obvious"
    if not quote or quote not in text:
        return out
    original = [c.model_dump() for c in out.facts if c.key == spec["fact_key"]]
    facts = [c for c in out.facts if c.key != spec["fact_key"]]
    facts.append(CandidateFact(key=spec["fact_key"], status=spec["status"], value=spec["value"], quote=quote))
    audit(session, "usertest", "usertest.plant", "encounter", enc.id,
          {"card": card, "plant_type": ptype, "fact_key": spec["fact_key"], "status": spec["status"], "value": spec["value"], "quote": quote,
           "why": spec["why"], "original_candidates": original})
    return out.model_copy(update={"facts": facts})
