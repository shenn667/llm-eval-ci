"""Check registry + dispatcher (pure functions: (output, params, ctx) -> CheckResult)."""

from __future__ import annotations

from typing import Any, Callable, Dict

from .base import CheckResult, failed
from .budgets import check_budget_cost, check_budget_latency, check_budget_tokens
from .content import check_contains, check_not_contains, check_regex
from .json_checks import check_json_schema_lite, check_json_valid
from .refusal import check_refusal
from .security import check_no_injection_obey, check_no_pii_leak

CheckFn = Callable[[str, Any, Dict[str, Any]], CheckResult]

CHECKS: Dict[str, CheckFn] = {
    "contains": check_contains,
    "not_contains": check_not_contains,
    "regex": check_regex,
    "json_valid": check_json_valid,
    "json_schema_lite": check_json_schema_lite,
    "refusal": check_refusal,
    "budget_tokens": check_budget_tokens,
    "budget_latency": check_budget_latency,
    "budget_cost": check_budget_cost,
    "no_pii_leak": check_no_pii_leak,
    "no_injection_obey": check_no_injection_obey,
}

CHECK_NAMES = tuple(CHECKS)

BUDGET_CHECK_FOR_KIND = {
    "tokens": "budget_tokens",
    "latency": "budget_latency",
    "cost": "budget_cost",
}


def run_check(name: str, output: str, params: Any, ctx: Dict[str, Any]) -> CheckResult:
    """Dispatch one check. Non-string model output fails every check (SPEC §3)."""
    if not isinstance(output, str):
        return failed(f"{name}: model output is not a string (fail-closed)")
    fn = CHECKS.get(name)
    if fn is None:
        return failed(f"unknown check: {name}")
    return fn(output, params, ctx)
