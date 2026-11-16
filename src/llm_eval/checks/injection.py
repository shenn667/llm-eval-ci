"""Alias module (task layout): re-exports injection/refusal checks.

Canonical implementation lives in :mod:`llm_eval.checks.security`
(no_injection_obey) and :mod:`llm_eval.checks.refusal` (refusal).
"""

from .refusal import REFUSAL_PHRASES, check_refusal
from .security import DEFAULT_INJECTION_SIGNALS, check_no_injection_obey

# Backwards-friendly alias: default obedience signals used by the bare
# no_injection_obey heuristic (no explicit `forbidden` list).
OBEDIENCE_SIGNALS = DEFAULT_INJECTION_SIGNALS

__all__ = [
    "DEFAULT_INJECTION_SIGNALS",
    "OBEDIENCE_SIGNALS",
    "REFUSAL_PHRASES",
    "check_no_injection_obey",
    "check_refusal",
    "RefusalCheck",
    "NoInjectionObeyCheck",
]


class RefusalCheck:
    """PASS iff output matches a refusal template (EN + FR, case-insensitive)."""

    name = "refusal"

    def __call__(self, output, params=None, ctx=None):
        return check_refusal(output, params or {}, ctx or {})

    run = __call__


class NoInjectionObeyCheck:
    """PASS iff no ``forbidden`` obedience signal is in output (SPEC mode).

    ``forbidden`` is required (SPEC_CASES.md §3 #11): without it the check
    FAILS — the runner never guesses obedience signals.
    """

    name = "no_injection_obey"

    def __call__(self, output, params=None, ctx=None):
        return check_no_injection_obey(output, params or {}, ctx or {})

    run = __call__
