"""JSON report writer. Contract (CTO): {version, cases: [{id, status,
failed_checks[], latency_ms, usage}]} + extras (suite, summary, detections,
skipped_invalid_lines). Never echoes raw PII (samples are always "***")."""

from __future__ import annotations

import json
from typing import Any, Dict

from .. import __version__ as _pkg_version


def _usage_for_json(usage: Any) -> Any:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return dict(usage)
    return usage


def result_to_dict(result: Any) -> Dict[str, Any]:
    total = len(result.cases)
    passed = sum(1 for c in result.cases if c.status == "pass")
    failed = total - passed
    pass_rate = (passed / total) if total else 0.0
    total_latency_ms = sum(getattr(c, "latency_ms", 0) or 0 for c in result.cases)
    total_cost_usd = 0.0
    try:
        total_cost_usd = float(result.total_cost_usd)
    except (AttributeError, TypeError, ValueError):
        for case in result.cases:
            usage = getattr(case, "usage", None)
            if isinstance(usage, dict):
                cost = usage.get("cost_usd")
                if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0:
                    total_cost_usd += cost
    cases = []
    for case in result.cases:
        entry: Dict[str, Any] = {
            "id": case.id,
            "status": case.status,
            "failed_checks": list(case.failed_checks),
            "latency_ms": case.latency_ms,
            "usage": _usage_for_json(case.usage),
        }
        detections = getattr(case, "detections", None)
        if detections:
            entry["detections"] = [dict(d) for d in detections]
        details = getattr(case, "details", None)
        if details:
            entry["details"] = dict(details)
        cases.append(entry)
    return {
        "version": getattr(result, "version", _pkg_version),
        "suite": getattr(result, "suite_name", ""),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate,
            "total_latency_ms": total_latency_ms,
            "total_cost_usd": total_cost_usd,
        },
        "skipped_invalid_lines": getattr(result, "skipped_invalid_lines", 0),
        "cases": cases,
    }


def render_json(result: Any) -> str:
    return json.dumps(result_to_dict(result), indent=2, ensure_ascii=False) + "\n"


def write_json_report(result: Any, path: str) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_json(result))
    return path
