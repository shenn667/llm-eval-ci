"""Alias module (task layout): re-exports the token/cost budget checks.

Canonical implementation lives in :mod:`llm_eval.checks.budgets`
(budget_tokens / budget_cost, fail-closed, epsilon 1e-9 on cost).
"""

from .budgets import COST_EPSILON, check_budget_cost, check_budget_tokens, resolve_max

__all__ = [
    "COST_EPSILON",
    "check_budget_tokens",
    "check_budget_cost",
    "resolve_max",
    "BudgetTokensCheck",
    "BudgetCostCheck",
]


class BudgetTokensCheck:
    """PASS iff ``usage.tokens <= max`` (explicit ``max`` wins, fail-closed)."""

    name = "budget_tokens"

    def __call__(self, output, params=None, ctx=None):
        return check_budget_tokens(output, params or {}, ctx or {})

    run = __call__


class BudgetCostCheck:
    """PASS iff ``usage.cost_usd <= max`` (epsilon 1e-9, fail-closed)."""

    name = "budget_cost"

    def __call__(self, output, params=None, ctx=None):
        return check_budget_cost(output, params or {}, ctx or {})

    run = __call__
