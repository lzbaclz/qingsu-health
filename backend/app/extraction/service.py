"""抽取服务：调用 LLM 提供者，然后做**确定性**校验后再写入事实库。

模型输出在这里被当作"候选"，不是事实：
- key 必须存在于协议；
- quote 必须逐字出现在患者原文（防编造）；
- 枚举值必须在 options 内；数值必须在范围内；
- 校验不过的候选被丢弃并记录，供评测统计。
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session

from ..facts.store import set_fact
from ..llm import get_provider
from ..models import Encounter, Entry, FactSource
from ..protocol.schema import Protocol
from ..verification.scope import flag_mentions


def _validate_value(protocol: Protocol, key: str, value: Any) -> tuple[bool, Any]:
    fdef = protocol.fact(key)
    if value is None:
        return True, None
    if fdef.type in ("enum",):
        ok = str(value) in {o.value for o in fdef.options}
        return ok, str(value) if ok else None
    if fdef.type in ("multi_enum", "body_regions"):
        vals = value if isinstance(value, list) else [value]
        allowed = {o.value for o in fdef.options}
        if fdef.type == "body_regions":
            from ..protocol.loader import region_index
            allowed |= set(region_index().keys())
        vals = [str(v) for v in vals if str(v) in allowed]
        return bool(vals), vals
    if fdef.type in ("number", "scale"):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False, None
        if fdef.min is not None and v < fdef.min:
            return False, None
        if fdef.max is not None and v > fdef.max:
            return False, None
        return True, v
    if fdef.type == "bool":
        return (True, value) if isinstance(value, bool) else (False, None)
    return True, str(value)


_RANK = {"present": 3, "uncertain": 2, "denied": 1}  # 红旗两遍结果合并：取更警惕的一边（误报由紧急核对兜住）


def _check(protocol: Protocol, text: str, cand) -> tuple[Any, str | None]:
    """返回 (规范化后的值, 拒收原因)。"""
    if cand.key not in protocol.fact_index:
        return None, "unknown_key"
    if not cand.quote or cand.quote not in text:
        return None, "quote_not_in_text"
    ok, value = _validate_value(protocol, cand.key, cand.value)
    if not ok:
        return None, "invalid_value"
    return value, None


def extract_and_apply(session: Session, encounter: Encounter, protocol: Protocol, entry: Entry) -> dict:
    text = entry.payload.get("text", "")
    provider = get_provider()
    out = provider.extract(text, protocol)
    from ..usertest.plant import maybe_plant  # 可用性测试专用，默认关闭
    out = maybe_plant(session, encounter, protocol, text, out)

    # 红旗专查（真实模型才有；离线词表是确定性的，再查一遍结果相同）
    rf_fn = getattr(provider, "extract_red_flags", None)
    rf_out = rf_fn(text, protocol) if rf_fn else None
    from ..llm.provider import red_flag_keys_for_pass
    screen = set(red_flag_keys_for_pass(protocol)) if rf_out is not None else set()

    rejected: list[dict] = []
    valid: list[tuple[Any, Any, str]] = []  # (候选, 值, 来源 main|red_flag_pass)
    for src, cands in (("main", out.facts), ("red_flag_pass", rf_out.facts if rf_out else [])):
        for cand in cands:
            if src == "red_flag_pass" and cand.key not in screen:
                continue  # 专查只认红旗事实
            value, reason = _check(protocol, text, cand)
            if reason:
                rejected.append({"candidate": cand.model_dump(), "reason": reason, "pass": src})
            else:
                valid.append((cand, value, src))

    chosen: list[tuple[Any, Any, str]] = [v for v in valid if v[0].key not in screen]
    rf_added, rf_raised = [], []
    for key in [k for k in dict.fromkeys(v[0].key for v in valid) if k in screen]:
        opts = [v for v in valid if v[0].key == key]
        best = max(opts, key=lambda v: _RANK.get(v[0].status, 0))  # 并列时保留主抽取（排在前面）
        main_opts = [v for v in opts if v[2] == "main"]
        if best[2] == "red_flag_pass":
            if not main_opts:
                rf_added.append(key)
            elif _RANK.get(best[0].status, 0) > max(_RANK.get(v[0].status, 0) for v in main_opts):
                rf_raised.append(key)
        if protocol.event_verification.enabled:
            # 不把他人、历史与本人的候选按阳性优先合并；不同语境和相反证据均须保留。
            import json
            seen_candidates = set()
            for option in opts:
                token = json.dumps(option[0].model_dump(), ensure_ascii=False, sort_keys=True)
                if token not in seen_candidates:
                    seen_candidates.add(token)
                    chosen.append(option)
        else:
            chosen.append(best)

    applied = []
    context_events = []
    for cand, value, src in chosen:
        from ..events.service import record_candidate
        event, apply_current = record_candidate(session, encounter, protocol, entry, cand, value)
        if event:
            context_events.append({"event_id": event.id, "key": cand.key, "subject": event.subject,
                                   "time_relation": event.time_relation, "applied_to_current": apply_current})
        if not apply_current:
            continue
        ambiguous_current = event and (event.subject == "unclear" or (event.time_relation == "historical" and cand.key not in protocol.event_verification.lifetime_fact_keys))
        status = "uncertain" if ambiguous_current else cand.status
        if ambiguous_current:
            value = None
        fact = set_fact(session, encounter, protocol, cand.key, status=status, value=value,
                        evidence=[{"entry_id": entry.id, "quote": cand.quote, "kind": "free_text"}],
                        source=FactSource.EXTRACTION)
        applied.append({"key": cand.key, "status": fact.status, "value": fact.value, "pass": src})
    return {"provider": getattr(provider, "last_used", provider.name), "applied": applied, "rejected": rejected,
            "unmapped_mentions": out.unmapped_mentions,
            "unmapped_flagged": flag_mentions(out.unmapped_mentions, protocol),
            "context_events": context_events,
            "red_flag_pass": {"ran": rf_out is not None, "added": rf_added, "raised": rf_raised}}
