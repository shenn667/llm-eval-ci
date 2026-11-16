"""Alias module (task layout): re-exports the PII check + masking helpers.

Canonical implementation lives in :mod:`llm_eval.checks.security`
(no_pii_leak, FR+EN patterns, values always masked as ***).
"""

from .security import MASK, PII_PATTERNS, check_no_pii_leak, find_pii, mask_pii

__all__ = [
    "MASK",
    "PII_PATTERNS",
    "check_no_pii_leak",
    "find_pii",
    "mask_pii",
    "NoPIILeakCheck",
]


class NoPIILeakCheck:
    """PASS iff no PII pattern (FR + EN) is detected in output."""

    name = "no_pii_leak"

    def __call__(self, output, params=None, ctx=None):
        return check_no_pii_leak(output, params or {}, ctx or {})

    run = __call__
