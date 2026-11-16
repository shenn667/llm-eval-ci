"""Budget checks: budget_tokens / budget_latency / budget_cost (fail-closed)."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from .base import CheckResult, as_params, failed, is_int, is_num, passed

COST_EPSILON = 1e-9

# Explicit-check param keys, in priority order, per budget kind.
_PARAM_KEYS = {
    "tokens": ("max", "max_tokens"),
    "latency": ("max_ms", "max_latency_ms"),
    "cost": ("max_usd", "max_cost_usd"),
}
# Case-level budget keys.
_CASE_KEYS = {"tokens": "max_tokens", "latency": "max_latency_ms", "cost": "max_cost_usd"}


def _valid_max(kind: str, value: Any) -> bool:
    if kind == "cost":
        return is_num(value) and value >= 0
    return is_int(value) and value > 0


def resolve_max(kind: str, params: Mapping[str, Any], case_budgets: Mapping[str, Any]) -> Any:
    """Explicit check params win over case-level budgets (SPEC §5.1)."""
    for key in _PARAM_KEYS[kind]:
        if key in params and _valid_max(kind, params[key]):
            return params[key]
    case_value = case_budgets.get(_CASE_KEYS[kind])
    if _valid_max(kind, case_value):
        return case_value
    return None


def _usage_field(ctx: Dict[str, Any], field: str) -> Tuple[bool, Any]:
    usage = ctx.get("usage")
    if isinstance(usage, Mapping) and field in usage:
        return True, usage[field]
    return False, None


def check_budget_tokens(output: str, params: Any, ctx: Dict[str, Any]) -> CheckResult:
    max_tokens = resolve_max("tokens", as_params(params), ctx.get("budgets", {}))
    if max_tokens is None:
        return failed("budget_tokens: no valid max declared (explicit 'max' or case 'max_tokens')")
    ok, tokens = _usage_field(ctx, "tokens")
    if not ok or not is_int(tokens) or tokens < 0:
        return failed("budget_tokens: usage.tokens missing or invalid (fail-closed)")
    if tokens > max_tokens:
        return failed(f"budget_tokens: {tokens} tokens > max {max_tokens}")
    return passed(f"budget_tokens: {tokens} <= {max_tokens}")


def check_budget_latency(output: str, params: Any, ctx: Dict[str, Any]) -> CheckResult:
    max_ms = resolve_max("latency", as_params(params), ctx.get("budgets", {}))
    if max_ms is None:
        return failed("budget_latency: no valid max declared (explicit 'max_ms' or case 'max_latency_ms')")
    latency_ms = ctx.get("latency_ms")
    if not is_int(latency_ms) or latency_ms < 0:
        return failed("budget_latency: latency_ms missing or invalid")
    if latency_ms > max_ms:
        return failed(f"budget_latency: {latency_ms} ms > max {max_ms} ms")
    return passed(f"budget_latency: {latency_ms} ms <= {max_ms} ms")


def check_budget_cost(output: str, params: Any, ctx: Dict[str, Any]) -> CheckResult:
    max_usd = resolve_max("cost", as_params(params), ctx.get("budgets", {}))
    if max_usd is None:
        return failed("budget_cost: no valid max declared (explicit 'max_usd' or case 'max_cost_usd')")
    ok, cost = _usage_field(ctx, "cost_usd")
    if not ok or not is_num(cost) or cost < 0:
        return failed("budget_cost: usage.cost_usd missing or invalid (fail-closed)")
    if cost > max_usd + COST_EPSILON:
        return failed(f"budget_cost: {cost} USD > max {max_usd} USD")
    return passed(f"budget_cost: {cost} USD <= {max_usd} USD")
