"""Shared base for checks: result type + small validators."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, TypeGuard

REFUSAL_SAMPLE = "***"

FLAG_MAP = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
}


@dataclass
class CheckResult:
    passed: bool
    detail: str = ""
    detections: List[Dict[str, Any]] = field(default_factory=list)


def passed(detail: str = "", detections: List[Dict[str, Any]] | None = None) -> CheckResult:
    return CheckResult(True, detail, detections or [])


def failed(detail: str = "", detections: List[Dict[str, Any]] | None = None) -> CheckResult:
    return CheckResult(False, detail, detections or [])


def as_params(params: Any) -> Dict[str, Any]:
    if isinstance(params, Mapping):
        return dict(params)
    return {}


def is_int(value: Any) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def is_num(value: Any) -> TypeGuard[float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
