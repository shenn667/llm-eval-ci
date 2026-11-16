"""Content checks: contains / not_contains / regex (case-sensitive)."""

from __future__ import annotations

import re
from typing import Any, Dict

from .base import FLAG_MAP, CheckResult, as_params, failed, passed


def _want_text(params: Dict[str, Any]) -> Any:
    # SPEC key is "text"; legacy/DESIGN suites use "value" — accept both.
    if "text" in params:
        return params["text"]
    return params.get("value")


def check_contains(output: str, params: Any, ctx: Dict[str, Any]) -> CheckResult:
    text = _want_text(as_params(params))
    if not isinstance(text, str):
        return failed("contains: missing or non-string 'text' param")
    if text in output:
        return passed(f"found {text!r}")
    return failed(f"substring {text!r} not found in output")


def check_not_contains(output: str, params: Any, ctx: Dict[str, Any]) -> CheckResult:
    text = _want_text(as_params(params))
    if not isinstance(text, str):
        return failed("not_contains: missing or non-string 'text' param")
    if text not in output:
        return passed(f"{text!r} absent")
    return failed(f"forbidden substring {text!r} present in output")


def check_regex(output: str, params: Any, ctx: Dict[str, Any]) -> CheckResult:
    params = as_params(params)
    pattern = params.get("pattern")
    if not isinstance(pattern, str):
        return failed("regex: missing or non-string 'pattern' param")
    flags = params.get("flags", [])
    if not isinstance(flags, list) or any(f not in FLAG_MAP for f in flags):
        return failed("regex: 'flags' must be a subset of [IGNORECASE, MULTILINE, DOTALL]")
    try:
        rx = re.compile(pattern, sum(FLAG_MAP[f] for f in flags))
    except re.error as exc:
        return failed(f"regex: invalid pattern ({exc})")
    if rx.search(output):
        return passed(f"pattern {pattern!r} matched")
    return failed(f"pattern {pattern!r} did not match")
