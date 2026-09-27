"""同一协议表达式的确定／矛盾候选评估；潜在提醒不把事实改成已确定。"""
from itertools import islice, product
import json

from .expr import evaluate


def evaluate_rule(rule, facts: dict) -> tuple[bool, bool]:
    if evaluate(rule.when, facts):
        return True, False
    if not rule.escalate_on_conflict:
        return False, False
    choices = []
    for key in rule.fact_keys:
        status, value = facts.get(key, ("not_asked", None))
        if status != "conflicting" or not isinstance(value, dict):
            continue
        seen, options = set(), []
        for candidate in value.get("candidates", []):
            state = (candidate.get("status", "uncertain"), candidate.get("value"))
            identity = json.dumps(state, sort_keys=True, ensure_ascii=False)
            if identity not in seen:
                seen.add(identity); options.append((key, state))
        if options:
            choices.append(options)
    if not choices:
        return False, False
    # 组合过多时按协议保持潜在提醒，交人工；不选定任何候选为事实。
    for index, variant in enumerate(islice(product(*choices), 257)):
        if index == 256 or evaluate(rule.when, {**facts, **dict(variant)}):
            return True, True
    return False, False
