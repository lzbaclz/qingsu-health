import pytest

from app.protocol.expr import ExprError, evaluate, parse


def test_basic_and_or_not():
    facts = {"a": ("present", True), "b": ("denied", None), "n": ("present", 8)}
    assert evaluate("facts.a.present and not facts.b.present", facts)
    assert evaluate("facts.b.denied or facts.zzz.present", facts)
    assert evaluate("facts.zzz.unknown", facts)
    assert evaluate("facts.n.gte(7) and facts.n.value >= 8", facts)
    assert not evaluate("facts.n.gte(9)", facts)


def test_multi_value_helpers():
    facts = {"r": ("present", ["lower_back_left", "buttock_left"])}
    assert evaluate("facts.r.has('buttock_left')", facts)
    assert evaluate("facts.r.any(['x', 'lower_back_left'])", facts)
    assert evaluate("'buttock_left' in facts.r.value", facts)


@pytest.mark.parametrize("bad", ["__import__('os')", "facts.a.__class__", "open('x')", "facts.a.value + 1", "x.present"])
def test_rejects_unsafe(bad):
    with pytest.raises(ExprError):
        parse(bad)


def test_empty_is_true():
    assert evaluate(None, {}) and evaluate("  ", {})
