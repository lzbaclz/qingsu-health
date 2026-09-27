"""协议规则表达式：一个极小、白名单式的表达式求值器（不使用 eval）。

语法示例（写在协议 YAML 的 when 字段里）：
    facts.leg_numbness.present and facts.pain_side.value == 'left'
    facts.severity.value >= 7
    facts.regions.has('lower_back_left')
    not facts.onset.answered
    facts.red_flag_bladder.present or facts.red_flag_saddle.present

每个 facts.<key> 提供：
    .present / .denied / .uncertain / .conflicting / .unknown（未问或未答）/ .answered（present 或 denied）
    .value                        原始值
    .has('x')                     多选值包含 x
    .any(['x','y'])               多选值与列表有交集
    .gte(n) / .lte(n)             数值比较（非数值返回 False）
"""
from __future__ import annotations

import ast
from typing import Any, Mapping


class FactView:
    __slots__ = ("key", "status", "value")

    def __init__(self, key: str, status: str, value: Any):
        self.key, self.status, self.value = key, status, value

    @property
    def present(self) -> bool:
        return self.status == "present"

    @property
    def denied(self) -> bool:
        return self.status == "denied"

    @property
    def uncertain(self) -> bool:
        return self.status == "uncertain"

    @property
    def conflicting(self) -> bool:
        return self.status == "conflicting"

    @property
    def unknown(self) -> bool:
        return self.status in ("not_asked", "asked_unanswered")

    @property
    def answered(self) -> bool:
        return self.status in ("present", "denied")

    def has(self, item: Any) -> bool:
        if isinstance(self.value, list):
            return item in self.value
        return self.value == item

    def any(self, items: list) -> bool:
        return any(self.has(i) for i in items)

    def gte(self, n: float) -> bool:
        return isinstance(self.value, (int, float)) and not isinstance(self.value, bool) and self.value >= n

    def lte(self, n: float) -> bool:
        return isinstance(self.value, (int, float)) and not isinstance(self.value, bool) and self.value <= n


class FactsNamespace:
    def __init__(self, facts: Mapping[str, tuple[str, Any]]):
        self._facts = facts

    def __getattr__(self, key: str) -> FactView:
        if key.startswith("_"):
            raise AttributeError(key)
        status, value = self._facts.get(key, ("not_asked", None))
        return FactView(key, status, value)


_ALLOWED_ATTRS = {"present", "denied", "uncertain", "conflicting", "unknown", "answered", "value"}
_ALLOWED_CALLS = {"has", "any", "gte", "lte"}


class ExprError(ValueError):
    pass


def parse(expr: str) -> ast.Expression:
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:  # pragma: no cover
        raise ExprError(f"表达式语法错误: {expr!r}: {e}") from e
    _validate(tree.body)
    return tree


def _validate(node: ast.AST) -> None:
    if isinstance(node, ast.BoolOp):
        for v in node.values:
            _validate(v)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        _validate(node.operand)
    elif isinstance(node, ast.Compare):
        _validate(node.left)
        for op in node.ops:
            if not isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn, ast.Gt, ast.GtE, ast.Lt, ast.LtE)):
                raise ExprError(f"不支持的比较运算: {type(op).__name__}")
        for c in node.comparators:
            _validate(c)
    elif isinstance(node, ast.Attribute):
        _validate(node.value)
        if node.attr.startswith("_"):
            raise ExprError("不允许访问下划线属性")
    elif isinstance(node, ast.Call):
        if not (isinstance(node.func, ast.Attribute) and node.func.attr in _ALLOWED_CALLS):
            raise ExprError("只允许调用 has/any/gte/lte")
        _validate(node.func.value)
        if node.keywords:
            raise ExprError("不允许关键字参数")
        for a in node.args:
            _validate(a)
    elif isinstance(node, ast.Name):
        if node.id not in ("facts", "True", "False", "None"):
            raise ExprError(f"未知名称: {node.id}")
    elif isinstance(node, ast.Constant):
        if not isinstance(node.value, (str, int, float, bool, type(None))):
            raise ExprError("不支持的常量类型")
    elif isinstance(node, (ast.List, ast.Tuple)):
        for e in node.elts:
            _validate(e)
    else:
        raise ExprError(f"不支持的语法节点: {type(node).__name__}")


def _eval(node: ast.AST, ns: FactsNamespace) -> Any:
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval(v, ns) for v in node.values)
        return any(_eval(v, ns) for v in node.values)
    if isinstance(node, ast.UnaryOp):
        return not _eval(node.operand, ns)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, ns)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval(comp, ns)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.In):
                ok = right is not None and left in right
            elif isinstance(op, ast.NotIn):
                ok = right is None or left not in right
            else:
                if not isinstance(left, (int, float)) or not isinstance(right, (int, float)) \
                        or isinstance(left, bool) or isinstance(right, bool):
                    ok = False
                elif isinstance(op, ast.Gt):
                    ok = left > right
                elif isinstance(op, ast.GtE):
                    ok = left >= right
                elif isinstance(op, ast.Lt):
                    ok = left < right
                else:
                    ok = left <= right
            if not ok:
                return False
            left = right
        return True
    if isinstance(node, ast.Attribute):
        base = _eval(node.value, ns)
        if isinstance(base, FactView) and node.attr not in _ALLOWED_ATTRS and node.attr not in _ALLOWED_CALLS:
            raise ExprError(f"不允许的属性: {node.attr}")
        return getattr(base, node.attr)
    if isinstance(node, ast.Call):
        fn = _eval(node.func, ns)
        return fn(*[_eval(a, ns) for a in node.args])
    if isinstance(node, ast.Name):
        return {"facts": ns, "True": True, "False": False, "None": None}[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(e, ns) for e in node.elts]
    raise ExprError(f"无法求值: {type(node).__name__}")


def evaluate(expr: str | None, facts: Mapping[str, tuple[str, Any]]) -> bool:
    """facts: {key: (status, value)}。空表达式视为 True。"""
    if not expr or not expr.strip():
        return True
    tree = parse(expr)
    return bool(_eval(tree.body, FactsNamespace(facts)))


def referenced_facts(expr: str | None) -> list[str]:
    """表达式里出现过的 facts.<key>（按出现顺序去重）。用于红旗证据与"触发事实"判断。"""
    if not expr:
        return []
    out: list[str] = []
    for node in ast.walk(parse(expr)):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "facts":
            if node.attr not in out:
                out.append(node.attr)
    return out
