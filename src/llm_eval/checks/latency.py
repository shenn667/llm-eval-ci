"""Alias module (task layout): re-exports the latency budget check.

Canonical implementation lives in :mod:`llm_eval.checks.budgets`
(budget_latency, wall-clock ms, fail-closed).
"""

from .budgets import COST_EPSILON, check_budget_latency, resolve_max

__all__ = ["COST_EPSILON", "check_budget_latency", "resolve_max", "BudgetLatencyCheck"]


class BudgetLatencyCheck:
    """PASS iff wall-clock ``latency_ms <= max`` (explicit ``max_ms`` wins)."""

    name = "budget_latency"

    def __call__(self, output, params=None, ctx=None):
        return check_budget_latency(output, params or {}, ctx or {})

    run = __call__
