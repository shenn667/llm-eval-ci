"""Markdown report writer. Exact layout per DESIGN.md §3 (GFM, PII masked)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _tokens_of(case: Any) -> str:
    usage = getattr(case, "usage", None)
    if isinstance(usage, Mapping):
        tokens = usage.get("tokens")
        if isinstance(tokens, int) and not isinstance(tokens, bool) and tokens >= 0:
            return str(tokens)
    return "n/a"


def _cost_of(case: Any) -> str:
    usage = getattr(case, "usage", None)
    if isinstance(usage, Mapping):
        cost = usage.get("cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0:
            return f"{float(cost):.4f}"
    return "n/a"


def _status_cell(case: Any) -> str:
    if case.status == "pass":
        return "✅ pass"
    return "❌ FAIL"


def _failed_cell(case: Any) -> str:
    if not case.failed_checks:
        return "—"
    return ", ".join(case.failed_checks)


def _total_cost(result: Any) -> float:
    try:
        return float(result.total_cost_usd)
    except (AttributeError, TypeError, ValueError):
        return 0.0


def render_markdown(result: Any) -> str:
    total = len(result.cases)
    passed = sum(1 for c in result.cases if c.status == "pass")
    failed = total - passed
    rate = (passed / total * 100) if total else 0.0
    total_s = sum(getattr(c, "latency_ms", 0) or 0 for c in result.cases) / 1000.0
    suite_name = getattr(result, "suite_name", "") or "suite"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# llm-eval report — {suite_name} — {now}",
        "",
        f"{total} cases, {passed} passed ({rate:.1f}%), "
        f"{failed} failed — {total_s:.1f} s total, {_total_cost(result):.4f} USD total.",
        "",
        "| case | status | latency | tokens | cost_usd | failed_checks |",
        "|------|--------|---------|--------|----------|----------------|",
    ]
    for case in result.cases:
        lines.append(
            f"| {case.id} | {_status_cell(case)} | {case.latency_ms} ms | "
            f"{_tokens_of(case)} | {_cost_of(case)} | {_failed_cell(case)} |"
        )
    lines += ["", "## Failures", ""]
    failures = [c for c in result.cases if c.status != "pass"]
    if not failures:
        lines.append("_Aucun._")
    else:
        for case in failures:
            lines.append(f"### ❌ {case.id}")
            details = getattr(case, "details", None) or {}
            for name in case.failed_checks:
                detail = details.get(name, f"check `{name}` failed.")
                lines.append(f"- check `{name}`: {detail}")
            lines.append("")
    lines += ["## PII / injection detections", ""]
    det_lines = []
    for case in result.cases:
        for det in getattr(case, "detections", None) or []:
            check = det.get("check", "?")
            pattern = det.get("pattern", "?")
            count = det.get("count", 1)
            det_lines.append(
                f"- {case.id}: `{check}` — pattern `{pattern}`, "
                f"{count} occurrence(s), valeur masquée `***`."
            )
    if det_lines:
        lines.extend(det_lines)
    else:
        lines.append("_Aucune détection._")
    lines += ["", "## Budgets", ""]
    budget_lines = []
    for case in result.cases:
        usage = getattr(case, "usage", None)
        tokens = _tokens_of(case)
        cost = _cost_of(case)
        budget_lines.append(
            f"- {case.id}: tokens {tokens}, latency {case.latency_ms} ms, "
            f"cost {cost} USD → {'OK' if case.status == 'pass' else 'FAIL'}."
        )
    if budget_lines:
        lines.extend(budget_lines)
    else:
        lines.append("_Aucun._")
    lines.append("")
    return "\n".join(lines)


def write_markdown_report(result: Any, path: str) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(result))
    return path
