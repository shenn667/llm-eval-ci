"""Budget checks: explicit params win, case-level fallback, fail-closed usage."""

from llm_eval.checks import budgets


def ctx(tokens=None, cost=None, latency_ms=5, budgets=None):
    usage = None
    if tokens is not None or cost is not None:
        usage = {}
        if tokens is not None:
            usage["tokens"] = tokens
        if cost is not None:
            usage["cost_usd"] = cost
    return {"usage": usage, "latency_ms": latency_ms, "budgets": budgets or {}}


def test_tokens_explicit_pass_fail_equal():
    assert budgets.check_budget_tokens("ok", {"max": 50}, ctx(tokens=5)).passed
    assert budgets.check_budget_tokens("ok", {"max": 50}, ctx(tokens=50)).passed
    r = budgets.check_budget_tokens("ok", {"max": 50}, ctx(tokens=500))
    assert not r.passed
    assert "budget_tokens" in r.detail


def test_tokens_case_level_and_explicit_wins():
    assert budgets.check_budget_tokens("ok", {}, ctx(tokens=5, budgets={"max_tokens": 50})).passed
    assert not budgets.check_budget_tokens(
        "ok", {}, ctx(tokens=500, budgets={"max_tokens": 50})).passed
    # explicit max=1000 beats case max_tokens=10
    assert budgets.check_budget_tokens(
        "ok", {"max": 1000}, ctx(tokens=500, budgets={"max_tokens": 10})).passed
    # legacy alias max_tokens inside explicit params
    assert budgets.check_budget_tokens(
        "ok", {"max_tokens": 50}, ctx(tokens=5)).passed


def test_tokens_usage_missing_or_invalid_fails_closed():
    assert not budgets.check_budget_tokens("ok", {"max": 50}, ctx()).passed
    assert not budgets.check_budget_tokens(
        "ok", {"max": 50}, {"usage": {"tokens": None}, "latency_ms": 1, "budgets": {}}).passed
    assert not budgets.check_budget_tokens(
        "ok", {"max": 50}, {"usage": {"tokens": -3}, "latency_ms": 1, "budgets": {}}).passed
    assert not budgets.check_budget_tokens(
        "ok", {"max": 50}, {"usage": {"tokens": True}, "latency_ms": 1, "budgets": {}}).passed
    assert not budgets.check_budget_tokens("ok", {"max": 50}, {"usage": "x"}).passed


def test_tokens_no_max_declared_fails():
    r = budgets.check_budget_tokens("ok", {}, ctx(tokens=5))
    assert not r.passed
    assert "no valid max" in r.detail


def test_latency_pass_fail_equal():
    assert budgets.check_budget_latency("ok", {"max_ms": 2000}, ctx(latency_ms=5)).passed
    assert budgets.check_budget_latency("ok", {"max_ms": 50}, ctx(latency_ms=50)).passed
    r = budgets.check_budget_latency("ok", {"max_ms": 50}, ctx(latency_ms=300))
    assert not r.passed
    assert "budget_latency" in r.detail


def test_latency_case_level_and_alias():
    assert budgets.check_budget_latency(
        "ok", {}, ctx(latency_ms=5, budgets={"max_latency_ms": 2000})).passed
    assert not budgets.check_budget_latency(
        "ok", {}, ctx(latency_ms=300, budgets={"max_latency_ms": 50})).passed
    assert budgets.check_budget_latency(
        "ok", {"max_latency_ms": 2000}, ctx(latency_ms=5)).passed


def test_latency_missing_or_invalid():
    bad = {"usage": None, "latency_ms": None, "budgets": {}}
    assert not budgets.check_budget_latency("ok", {"max_ms": 50}, bad).passed
    bad2 = {"usage": None, "latency_ms": -1, "budgets": {}}
    assert not budgets.check_budget_latency("ok", {"max_ms": 50}, bad2).passed
    assert not budgets.check_budget_latency("ok", {}, ctx(latency_ms=5)).passed


def test_cost_pass_fail_epsilon():
    assert budgets.check_budget_cost("ok", {"max_usd": 0.01}, ctx(cost=0.0001)).passed
    assert budgets.check_budget_cost("ok", {"max_usd": 0.01}, ctx(cost=0.01)).passed
    # within float epsilon -> pass
    assert budgets.check_budget_cost("ok", {"max_usd": 0.01}, ctx(cost=0.01 + 5e-10)).passed
    r = budgets.check_budget_cost("ok", {"max_usd": 0.01}, ctx(cost=0.05))
    assert not r.passed
    assert "budget_cost" in r.detail


def test_cost_case_level_and_missing():
    assert budgets.check_budget_cost(
        "ok", {}, ctx(cost=0.0001, budgets={"max_cost_usd": 0.01})).passed
    assert not budgets.check_budget_cost(
        "ok", {}, ctx(cost=0.05, budgets={"max_cost_usd": 0.01})).passed
    assert not budgets.check_budget_cost("ok", {}, ctx(cost=0.0001)).passed
    assert not budgets.check_budget_cost("ok", {"max_usd": 0.01}, ctx()).passed
    assert not budgets.check_budget_cost(
        "ok", {"max_usd": 0.01},
        {"usage": {"cost_usd": -1}, "latency_ms": 1, "budgets": {}}).passed


def test_resolve_max_prefers_explicit():
    assert budgets.resolve_max("tokens", {"max": 7}, {"max_tokens": 1}) == 7
    assert budgets.resolve_max("tokens", {}, {"max_tokens": 9}) == 9
    assert budgets.resolve_max("tokens", {"max": -2}, {"max_tokens": 9}) == 9
    assert budgets.resolve_max("tokens", {}, {}) is None
    assert budgets.resolve_max("cost", {}, {"max_cost_usd": 0.5}) == 0.5
