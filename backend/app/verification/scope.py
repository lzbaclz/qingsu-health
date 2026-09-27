"""患者原话里的药名、剂量、诊断性表述和疑似指令：不阻断、不改写，只给医生打标记。

越界检查（V4）管的是系统生成的文字。患者自己写的"建议布洛芬400mg每日3次"不是系统建议，
但原样出现在"目前用药"一栏、摘要和打印页里，医生可能把它误读成系统结论或医嘱（第二轮评审 T1 实测）。
所以：text 类 / 用药类事实的值、以及模型整理出的"协议外提到"，命中越界词或疑似指令时加 flags；
V4 同时检查摘要里命中的条目都带了标记。
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from ..protocol.schema import FactDef, Protocol

INSTRUCTION_PATTERNS = [
    r"忽略(以上|之前|前面|上面|所有|全部)",
    r"(请|要|必须|务必)(在|把)?(摘要|总结|报告|病历)(里|中|上)?(写|改|填)",
    r"(system|系统)\s*(prompt|提示词)",
    r"(?i)ignore\s+(all|previous|the\s+above)",
    r"你(现在)?(的身份)?是(一名|一个|一位)?(医生|助手|AI|人工智能)",
]
_INSTRUCTION_RE = [re.compile(p) for p in INSTRUCTION_PATTERNS]

FLAG_SCOPE = {"code": "patient_words_scope", "label": "患者原话，含药名/剂量或诊断性表述，不是系统建议"}
FLAG_INSTRUCTION = {"code": "patient_words_instruction", "label": "原话含疑似对系统的指令，已按原话记录，未执行"}


@lru_cache(maxsize=32)
def _scope_res(patterns: tuple[str, ...]) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(p) for p in patterns)


def text_flags(text: str, protocol: Protocol) -> list[dict]:
    if not text:
        return []
    flags = []
    if any(r.search(text) for r in _scope_res(tuple(protocol.scope_guard.forbidden_patterns))):
        flags.append(FLAG_SCOPE)
    if any(r.search(text) for r in _INSTRUCTION_RE):
        flags.append(FLAG_INSTRUCTION)
    return flags


def _texts(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, dict):  # 矛盾：{"candidates": [{status, value}, ...]}
        return [t for c in value.get("candidates", []) for t in _texts(c.get("value"))]
    return []


def is_patient_words(fdef: FactDef) -> bool:
    """这些事实的值就是患者原话（自由文本或用药自述），不经协议选项归一。"""
    return fdef.type == "text" or fdef.category == "medication"


def annotate_fact_item(item: dict, fdef: FactDef, protocol: Protocol) -> dict:
    """给 fact_to_dict 的结果加 flags（就地修改并返回）。不命中则不加字段。"""
    if not is_patient_words(fdef):
        return item
    flags: list[dict] = []
    for t in _texts(item.get("value")):
        for f in text_flags(t, protocol):
            if f not in flags:
                flags.append(f)
    if flags:
        item["flags"] = flags
    return item


def flag_mentions(mentions: list[str], protocol: Protocol) -> list[dict]:
    return [{"text": m, **({"flags": fl} if (fl := text_flags(m, protocol)) else {})} for m in mentions]
