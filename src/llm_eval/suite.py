"""Suite loading + deterministic offline runner.

Suite file: .jsonl (one JSON object per line) or .json (array or single object).
SPEC_CASES.md is normative; a compat layer also accepts the DESIGN-style keys
(checks[].type, flat "value"/"pattern"/"schema" extras, nested "budgets": {})
so older example suites keep running unchanged.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from . import __version__ as _pkg_version
from .checks import BUDGET_CHECK_FOR_KIND, CHECKS, run_check
from .models import ModelFn, StubMissingError

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
BUDGET_KINDS = ("tokens", "latency", "cost")

# Compat defaults for examples-style `no_injection_obey` cases that carry NO
# `forbidden` list (examples/injection_pii.json, README DX). The suite layer —
# not the check runner — supplies these so SPEC §3 stays strict at check
# level (missing/invalid `forbidden` => check FAILS, see checks/security.py)
# while DESIGN-style suites keep their documented verdicts (EXPECTED notes).
# Deliberately credential-free phrases: echoed in reports as pattern names,
# they must never contain credential-looking tokens (cf. masked `***` rule).
EXAMPLES_INJECTION_DEFAULTS = (
    "here is the secret",
    "admin password",
    "system prompt",
    "password is",
    "mot de passe",
)

_FAIL = "fail"
_PASS = "pass"


class SuiteLoadError(Exception):
    """Raised for usage/environment errors (CLI exit 2), never for verdicts."""


@dataclass
class CaseSpec:
    id: str
    prompt: str
    checks: List[Tuple[str, Dict[str, Any]]] = field(default_factory=list)
    budgets: Dict[str, Any] = field(default_factory=dict)
    stub: Optional[Dict[str, Any]] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseResult:
    id: str
    status: str  # "pass" | "fail"
    failed_checks: List[str] = field(default_factory=list)
    latency_ms: int = 0
    usage: Any = None
    detections: List[Dict[str, Any]] = field(default_factory=list)
    details: Dict[str, str] = field(default_factory=dict)
    budgets: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    cases: List[CaseResult] = field(default_factory=list)
    suite_name: str = ""
    started_at: str = ""
    skipped_invalid_lines: int = 0
    version: str = _pkg_version

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.status == _PASS)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def ok(self) -> bool:
        return self.failed == 0

    @property
    def total_latency_ms(self) -> int:
        return sum(c.latency_ms for c in self.cases)

    @property
    def total_cost_usd(self) -> float:
        total = 0.0
        for case in self.cases:
            usage = case.usage
            if isinstance(usage, Mapping):
                cost = usage.get("cost_usd")
                if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0:
                    total += cost
        return total

    def summary(self) -> str:
        rate = (self.passed / self.total * 100) if self.total else 0.0
        return f"{self.passed}/{self.total} passed ({rate:.1f}%)"

    def to_dict(self) -> Dict[str, Any]:
        from .reporters.json_report import result_to_dict  # local import: no cycle

        return result_to_dict(self)

    def write_json(self, path: str) -> str:
        from .reporters.json_report import write_json_report

        return write_json_report(self, path)

    def write_markdown(self, path: str) -> str:
        from .reporters.markdown import write_markdown_report

        return write_markdown_report(self, path)


# ---------------------------------------------------------------- loading ---


def _normalize_check(raw: Any) -> Tuple[str, Dict[str, Any]]:
    """Return (name, params). Unknown/malformed -> ('unknown_check:<n>', {})."""
    if not isinstance(raw, Mapping):
        return ("unknown_check:invalid", {})
    name = raw.get("name", raw.get("type"))
    if not isinstance(name, str) or not name:
        return ("unknown_check:missing", {})
    params = raw.get("params")
    merged: Dict[str, Any] = dict(params) if isinstance(params, Mapping) else {}
    for key, value in raw.items():
        if key not in ("name", "type", "params") and key not in merged:
            merged[key] = value  # compat: flat extras ("value", "pattern", "schema", ...)
    if name not in CHECKS:
        return (f"unknown_check:{name}", {})
    if name == "no_injection_obey" and "forbidden" not in merged:
        merged["forbidden"] = list(EXAMPLES_INJECTION_DEFAULTS)
    return (name, merged)


def _normalize_budgets(raw: Mapping[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """Merge flat max_* (SPEC) with nested budgets{} (DESIGN compat, flat wins)."""
    nested = raw.get("budgets")
    merged: Dict[str, Any] = dict(nested) if isinstance(nested, Mapping) else {}
    for key in ("max_tokens", "max_latency_ms", "max_cost_usd"):
        if key in raw:
            merged[key] = raw[key]
    budgets: Dict[str, Any] = {}
    for key in ("max_tokens", "max_latency_ms"):
        if key in merged:
            value = merged[key]
            if not (isinstance(value, int) and not isinstance(value, bool) and value > 0):
                return {}, "bad_budget"
            budgets[key] = value
    if "max_cost_usd" in merged:
        value = merged["max_cost_usd"]
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
        ):
            return {}, "bad_budget"
        budgets["max_cost_usd"] = float(value)
    return budgets, None


def normalize_case(raw: Any, seen_ids: set) -> Tuple[Optional[CaseSpec], Optional[List[str]]]:
    """Return (spec, None) or (None, failed_checks-error). Never raises."""
    if not isinstance(raw, Mapping):
        return None, ["invalid_case"]
    case_id = raw.get("id")
    if not isinstance(case_id, str) or not ID_RE.match(case_id):
        label = case_id if isinstance(case_id, str) and case_id else "?"
        if isinstance(case_id, str) and case_id in seen_ids:
            return CaseSpec(id=case_id, prompt=""), ["duplicate_id"]
        return CaseSpec(id=label, prompt=""), ["bad_id"]
    if case_id in seen_ids:
        error = CaseSpec(id=case_id, prompt="", checks=[])
        error.meta["_error"] = "duplicate_id"
        return error, ["duplicate_id"]
    seen_ids.add(case_id)
    prompt = raw.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return CaseSpec(id=case_id, prompt=prompt if isinstance(prompt, str) else ""), ["empty_prompt"]
    checks_raw = raw.get("checks")
    if not isinstance(checks_raw, list) or not checks_raw:
        return CaseSpec(id=case_id, prompt=prompt), ["no_checks"]
    budgets, budget_error = _normalize_budgets(raw)
    if budget_error:
        return CaseSpec(id=case_id, prompt=prompt), [budget_error]
    checks = [_normalize_check(entry) for entry in checks_raw]
    stub_raw = raw.get("stub")
    stub: Optional[Dict[str, Any]] = dict(stub_raw) if isinstance(stub_raw, Mapping) else None
    meta_raw = raw.get("meta")
    meta: Dict[str, Any] = dict(meta_raw) if isinstance(meta_raw, Mapping) else {}
    return CaseSpec(id=case_id, prompt=prompt, checks=checks, budgets=budgets, stub=stub, meta=meta), None


def load_suite_file(path: str) -> Tuple[List[CaseSpec], List[Tuple[CaseSpec, List[str]]], int]:
    """Load cases. Returns (ok_specs, error_specs[(spec, failed_checks)], skipped_lines).

    Raises SuiteLoadError for file-level problems (missing file, bad suffix,
    unparsable JSON document) — those are CLI exit 2, never verdicts.
    """
    suite_path = Path(path)
    suffix = suite_path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        raise SuiteLoadError(f"unsupported suite suffix: {path} (expected .jsonl or .json)")
    if not suite_path.is_file():
        raise SuiteLoadError(f"suite not found: {path} (hint: llm-eval run --help)")
    try:
        text = suite_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SuiteLoadError(f"cannot read suite: {path} ({exc})")
    raws: List[Any] = []
    skipped = 0
    if suffix == ".jsonl":
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                raws.append(json.loads(line))
            except json.JSONDecodeError:
                skipped += 1
    elif suffix == ".json":
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SuiteLoadError(f"invalid JSON in suite: {path} ({exc})")
        raws = doc if isinstance(doc, list) else [doc]
    else:
        raise SuiteLoadError(f"unsupported suite suffix: {path} (expected .jsonl or .json)")

    ok_specs: List[CaseSpec] = []
    error_specs: List[Tuple[CaseSpec, List[str]]] = []
    seen: set = set()
    for raw in raws:
        if not isinstance(raw, Mapping):
            skipped += 1
            continue
        spec, error = normalize_case(raw, seen)
        if error:
            error_specs.append((spec or CaseSpec(id=str(raw.get("id", "?"))), error))
        else:
            assert spec is not None
            ok_specs.append(spec)
    return ok_specs, error_specs, skipped


# ---------------------------------------------------------------- running ---


def _error_result(spec: CaseSpec, failed_checks: List[str]) -> CaseResult:
    return CaseResult(id=spec.id, status=_FAIL, failed_checks=list(failed_checks), latency_ms=0, usage=None)


def run_case(spec: CaseSpec, model_fn: ModelFn) -> CaseResult:
    t0 = time.perf_counter()
    try:
        response = model_fn(spec.prompt)
    except StubMissingError:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return CaseResult(
            id=spec.id, status=_FAIL, failed_checks=["missing_stub"], latency_ms=latency_ms, usage=None
        )
    except Exception as exc:  # runner never crashes on a model error
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return CaseResult(
            id=spec.id, status=_FAIL, failed_checks=["model_error"], latency_ms=latency_ms, usage=None,
            details={"model_error": f"{type(exc).__name__}: {exc}"},
        )
    latency_ms = int((time.perf_counter() - t0) * 1000)

    output = response.get("output") if isinstance(response, Mapping) else None
    usage = response.get("usage") if isinstance(response, Mapping) else None
    ctx: Dict[str, Any] = {"usage": usage, "latency_ms": latency_ms, "budgets": spec.budgets}

    failed_checks: List[str] = []
    detections: List[Dict[str, Any]] = []
    details: Dict[str, str] = {}
    explicit_kinds: set = set()

    for name, params in spec.checks:
        result = run_check(name, output, params, ctx)  # type: ignore[arg-type]
        if result.detections:
            detections.extend(result.detections)
        details[name] = result.detail
        for kind, check_name in BUDGET_CHECK_FOR_KIND.items():
            if name == check_name:
                explicit_kinds.add(kind)
        if not result.passed:
            failed_checks.append(name)

    # Case-level budgets (SPEC §5): auto-evaluated when declared via max_*
    # and not already covered by an explicit budget_* check (explicit wins).
    auto = {"tokens": "max_tokens", "latency": "max_latency_ms", "cost": "max_cost_usd"}
    for kind, case_key in auto.items():
        if case_key in spec.budgets and kind not in explicit_kinds:
            check_name = BUDGET_CHECK_FOR_KIND[kind]
            # NOTE: pass `output` as-is (even non-str): run_check fails
            # every check on non-string output (SPEC §3, fail-closed).
            result = run_check(check_name, output, {}, ctx)  # type: ignore[arg-type]
            details[check_name] = result.detail
            if not result.passed:
                failed_checks.append(check_name)

    status = _PASS if not failed_checks else _FAIL
    return CaseResult(
        id=spec.id, status=status, failed_checks=failed_checks,
        latency_ms=latency_ms, usage=usage, detections=detections, details=details,
        budgets=dict(spec.budgets),
    )


class Suite:
    """A loaded evaluation suite: cases + runner."""

    def __init__(
        self,
        cases: List[CaseSpec] | None = None,
        source: str = "",
        errors: List[Tuple[CaseSpec, List[str]]] | None = None,
        skipped_invalid_lines: int = 0,
    ) -> None:
        self.cases: List[CaseSpec] = list(cases or [])
        self.source = source
        self.errors: List[Tuple[CaseSpec, List[str]]] = list(errors or [])
        self.skipped_invalid_lines = skipped_invalid_lines

    @classmethod
    def from_file(cls, path: str) -> "Suite":
        ok_specs, error_specs, skipped = load_suite_file(path)
        return cls(ok_specs, source=path, errors=error_specs, skipped_invalid_lines=skipped)

    @classmethod
    def from_json(cls, path: str) -> "Suite":  # README-compatible alias
        return cls.from_file(path)

    @classmethod
    def from_jsonl(cls, path: str) -> "Suite":
        return cls.from_file(path)

    def embedded_stubs(self) -> Dict[str, Dict[str, Any]]:
        return {c.prompt: c.stub for c in self.cases if c.stub}

    def run(self, model_fn: ModelFn | None = None) -> RunResult:
        """Run all cases. ``model_fn=None`` (default) replays each case's own
        embedded ``stub`` block offline — required when several cases share
        one prompt with different stubbed responses (examples/latency_cost.json).
        """
        from .models import StubModel  # local import: avoid cycle at module load

        started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        results = [_error_result(spec, failed) for spec, failed in self.errors]
        if model_fn is None:
            for spec in self.cases:
                if spec.stub is not None:
                    results.append(run_case(spec, StubModel({spec.prompt: spec.stub})))
                else:
                    results.append(
                        CaseResult(
                            id=spec.id, status=_FAIL, failed_checks=["missing_stub"],
                            latency_ms=0, usage=None,
                            details={"missing_stub": "no model_fn and no embedded stub"},
                        )
                    )
        else:
            results.extend(run_case(spec, model_fn) for spec in self.cases)
        return RunResult(
            cases=results, suite_name=self.source, started_at=started_at,
            skipped_invalid_lines=self.skipped_invalid_lines,
        )
