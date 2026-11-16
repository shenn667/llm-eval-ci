"""Alias module (task layout): re-exports content checks from content.py.

Canonical implementation lives in :mod:`llm_eval.checks.content`
(SPEC section 3: contains / not_contains / regex, case-sensitive).
"""

from .content import check_contains, check_not_contains, check_regex

__all__ = [
    "check_contains",
    "check_not_contains",
    "check_regex",
    "ContainsCheck",
    "NotContainsCheck",
    "RegexCheck",
]


class ContainsCheck:
    """PASS iff ``params.text`` (alias ``value``) is a substring of output."""

    name = "contains"

    def __call__(self, output, params=None, ctx=None):
        return check_contains(output, params or {}, ctx or {})

    run = __call__


class NotContainsCheck:
    """PASS iff ``params.text`` (alias ``value``) is absent from output."""

    name = "not_contains"

    def __call__(self, output, params=None, ctx=None):
        return check_not_contains(output, params or {}, ctx or {})

    run = __call__


class RegexCheck:
    """PASS iff ``re.search(params.pattern, output, flags)`` matches."""

    name = "regex"

    def __call__(self, output, params=None, ctx=None):
        return check_regex(output, params or {}, ctx or {})

    run = __call__
