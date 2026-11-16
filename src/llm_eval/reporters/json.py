"""JSON reporter: machine-readable report (DESIGN.md section 4).

Contract keys (always present): version, cases[{id, status, failed_checks,
latency_ms, usage}]. Extras (suite, summary, detections, skipped_invalid_lines,
generated_at) are additive, never replacements. Secret samples always "***".
"""
from __future__ import annotations

import json as _json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _scrub_detections(detections):
    clean = []
    for det in detections or []:
        if not isinstance(det, dict):
            continue
        entry = {k: det.get(k) for k in ("check", "pattern", "count")}
        entry["sample"] = "***"
        clean.append(entry)
    return clean


def result_to_dict(result) -> Dict[str, Any]:
    total = result.total
    passed = result.passed
    cases = []
    for case in result.cases:
        cases.append(
            {
                "id": case.id,
                "status": case.status,
                "failed_checks": list(case.failed_checks),
                "latency_ms": case.latency_ms,
                "usage": case.usage,
                "detections": _scrub_detections(case.detections),
            }
        )
    return {
        "version": getattr(result, "version", "0.1.0"),
        "suite": getattr(result, "suite_name", ""),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total, 3) if total else 0.0,
            "total_latency_ms": result.total_latency_ms,
            "total_cost_usd": round(result.total_cost_usd, 6),
        },
        "skipped_invalid_lines": getattr(result, "skipped_invalid_lines", 0),
        "cases": cases,
    }


def write_json_report(result, path) -> str:
    payload = result_to_dict(result)
    target = Path(path)
    if target.parent != Path(".") and str(target.parent):
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(target)
