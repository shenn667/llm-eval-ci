"""CLI: `llm-eval run SUITE ...` and `llm-eval check-text FILE ...`.

Stdlib only (argparse/json/re/time). Offline-first: model outputs come from
embedded `stub` blocks in the suite file or from `--fixtures` (JSON object
mapping prompt -> {output, usage, delay_ms}). `check-text` builds one in-memory
case from a UTF-8 file and replays it through the very same normalize +
Suite.run() pipeline. Exit codes: 0 = all pass, 1 = >=1 case failed,
2 = usage/environment error.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from typing import Any, Dict, List, Optional

from . import __version__
from .models import StubModel
from .suite import ID_RE, Suite, SuiteLoadError, normalize_case

HELP_CHECKS = (
    "checks (SPEC_CASES.md §3):\n"
    "  contains, not_contains, regex, json_valid, json_schema_lite, refusal,\n"
    "  budget_tokens, budget_latency, budget_cost, no_pii_leak, no_injection_obey"
)

HELP_EPILOG = """examples:
  llm-eval run examples/cases.jsonl --report report.md --json report.json
  llm-eval check-text ./answer.txt --label answer [--forbidden "here is the secret"]
  pytest --llm-eval=examples/cases.jsonl

%s

exit codes: 0 = all pass · 1 = ≥1 case failed · 2 = usage/environment error
""" % HELP_CHECKS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-eval",
        usage=(
            "llm-eval run SUITE [--report PATH] [--json PATH] [--overwrite] [--traceback]\n"
            "       llm-eval check-text FILE [--label LABEL] [--forbidden PHRASE]... "
            "[--report PATH] [--json PATH]"
        ),
        description="Run deterministic LLM evals offline (stdlib only, no network).",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")
    run_p = sub.add_parser(
        "run",
        help="run a .jsonl suite (one JSON object per line)",
        description="Run deterministic LLM evals offline (stdlib only, no network).",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    run_p.add_argument("suite", metavar="SUITE", help=".jsonl suite (one JSON object per line)")
    run_p.add_argument("--report", metavar="PATH", default="./report.md",
                       help="Markdown report (default: ./report.md)")
    run_p.add_argument("--json", dest="json_path", metavar="PATH", default="./report.json",
                       help="JSON report (default: ./report.json)")
    run_p.add_argument("--fixtures", metavar="PATH", default=None,
                       help="optional JSON fixture file mapping prompt -> "
                            "{output, usage, delay_ms} (default: embedded suite stubs)")
    run_p.add_argument("--overwrite", action="store_true", default=False,
                       help="overwrite existing reports (default behavior: "
                            "reports are overwritten; kept for CI explicitness)")
    run_p.add_argument("--no-overwrite", action="store_true", default=False,
                       help="fail with exit 2 instead of overwriting an existing report")
    run_p.add_argument("--traceback", action="store_true",
                       help="print traceback on usage errors (default: one-line error)")
    check_p = sub.add_parser(
        "check-text",
        help="check one text file for PII / injection obedience (offline, stdlib only)",
        description=(
            "Build one in-memory case (no_pii_leak + no_injection_obey) whose stub "
            "output is the UTF-8 content of FILE, then run it through the exact same "
            "normalizer, runner and reporters as `run`. No network, no API key."
        ),
        epilog=(
            "With no --forbidden, the check uses the same credential-free default "
            "phrases as `llm-eval run` (suite.py: EXAMPLES_INJECTION_DEFAULTS).\n\n"
            + HELP_EPILOG
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    check_p.add_argument("file", metavar="FILE",
                         help="UTF-8 text file used as the case's stub output")
    check_p.add_argument("--label", metavar="LABEL", default="check_text",
                         help="case id [a-z0-9][a-z0-9_-]{0,63} (default: check_text)")
    check_p.add_argument("--forbidden", metavar="PHRASE", action="append", default=None,
                         help="obedience phrase to reject; repeatable "
                              "(default: suite's documented credential-free phrases)")
    check_p.add_argument("--report", metavar="PATH", default="./report.md",
                         help="Markdown report (default: ./report.md)")
    check_p.add_argument("--json", dest="json_path", metavar="PATH", default="./report.json",
                         help="JSON report (default: ./report.json)")
    check_p.add_argument("--traceback", action="store_true",
                         help="print traceback on usage errors (default: one-line error)")
    return parser


def _build_model(suite: Suite, fixtures_path: Optional[str]) -> StubModel:
    if fixtures_path:
        try:
            return StubModel.from_file(fixtures_path)
        except FileNotFoundError:
            raise SuiteLoadError(
                f"fixtures not found: {fixtures_path} (hint: llm-eval run --help)")
        except ValueError as exc:
            raise SuiteLoadError(f"invalid fixtures file: {fixtures_path} ({exc})")
    return StubModel(suite.embedded_stubs())


def run_suite(
    suite_path: str,
    report_path: str = "./report.md",
    json_path: str = "./report.json",
    fixtures_path: Optional[str] = None,
    out_lines: Optional[List[str]] = None,
    err_lines: Optional[List[str]] = None,
    overwrite: bool = True,
) -> int:
    """Execute a suite file. Returns process exit code (0/1/2)."""
    from pathlib import Path

    if not overwrite:
        for existing in (report_path, json_path):
            if Path(existing).exists():
                msg = f"error: report exists (use --overwrite): {existing}"
                if err_lines is not None:
                    err_lines.append(msg)
                else:
                    print(msg, file=sys.stderr)
                return 2
    t0 = time.perf_counter()
    try:
        suite = Suite.from_file(suite_path)
    except SuiteLoadError as exc:
        if err_lines is not None:
            err_lines.append(f"error: {exc}")
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        if fixtures_path:
            model = _build_model(suite, fixtures_path)
            result = suite.run(model)
        else:
            # Per-case embedded stubs: correct even when several cases share
            # one prompt with different stubbed responses (latency_cost.json).
            result = suite.run()
    except SuiteLoadError as exc:
        if err_lines is not None:
            err_lines.append(f"error: {exc}")
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    if suite.skipped_invalid_lines:
        msg = (f"warning: {suite_path}: skipped "
               f"{suite.skipped_invalid_lines} invalid JSON line(s) "
               f"(counted in skipped_invalid_lines)")
        if err_lines is not None:
            err_lines.append(msg)
        else:
            print(msg, file=sys.stderr)
    return _emit_result(result, report_path, json_path, out_lines, err_lines, t0)


def _emit_result(
    result: Any,
    report_path: str,
    json_path: str,
    out_lines: Optional[List[str]],
    err_lines: Optional[List[str]],
    t0: float,
) -> int:
    """Write both reports and print the shared per-case summary.

    Shared by `run` and `check-text` so their report contract and exit codes
    cannot drift apart. Returns 2 on a report write error, else 0/1 by verdict.
    """
    try:
        result.write_markdown(report_path)
        result.write_json(json_path)
    except OSError as exc:
        msg = f"error: cannot write report ({exc})"
        if err_lines is not None:
            err_lines.append(msg)
        else:
            print(msg, file=sys.stderr)
        return 2
    elapsed = time.perf_counter() - t0
    lines: List[str] = []
    for case in result.cases:
        if case.status == "pass":
            lines.append(f"\u2705 {case.id} ({case.latency_ms} ms)")
        else:
            failed = ", ".join(case.failed_checks) if case.failed_checks else "failed"
            lines.append(f"\u274c {case.id} \u2014 failed: {failed}")
    lines.append(
        f"{result.passed}/{result.total} passed in {elapsed:.1f} s "
        f"\u2192 {report_path}, {json_path}"
    )
    if out_lines is not None:
        out_lines.extend(lines)
    else:
        for line in lines:
            print(line)
    return 0 if result.ok else 1


def check_text(
    file_path: str,
    label: str = "check_text",
    forbidden: Optional[List[str]] = None,
    report_path: str = "./report.md",
    json_path: str = "./report.json",
    out_lines: Optional[List[str]] = None,
    err_lines: Optional[List[str]] = None,
) -> int:
    """Check one text file offline. Returns process exit code (0/1/2).

    The file content becomes the stub `output` of a single in-memory case;
    normalization, checks, runner and reporters are the very same ones used by
    `run`. Raw text and raw PII values are never written to the reports.
    """
    from pathlib import Path

    def _usage_error(msg: str) -> int:
        if err_lines is not None:
            err_lines.append(msg)
        else:
            print(msg, file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    if not isinstance(label, str) or not ID_RE.match(label):
        return _usage_error(
            "error: invalid --label (expected [a-z0-9][a-z0-9_-]{0,63}): "
            f"{label!r}"
        )
    path = Path(file_path)
    if not path.is_file():
        return _usage_error(
            f"error: text file not found: {file_path} "
            "(hint: llm-eval check-text --help)"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return _usage_error(f"error: cannot read text file: {file_path} ({exc})")

    injection_check: Dict[str, Any] = {"name": "no_injection_obey"}
    if forbidden:
        injection_check["forbidden"] = list(forbidden)
    raw: Dict[str, Any] = {
        "id": label,
        "prompt": f"check-text: {path.name}",
        "checks": [{"name": "no_pii_leak"}, injection_check],
        "stub": {"output": text},
    }
    spec, error = normalize_case(raw, set())
    if error or spec is None:
        return _usage_error(
            f"error: invalid check-text case: {', '.join(error or ['unknown'])}"
        )
    # Normalization already applied EXAMPLES_INJECTION_DEFAULTS when the user
    # omitted --forbidden — exactly the `run` semantics.
    suite = Suite([spec], source="check-text")
    result = suite.run()  # embedded stub: no model, no network
    return _emit_result(result, report_path, json_path, out_lines, err_lines, t0)


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        try:
            return run_suite(
                args.suite,
                report_path=args.report,
                json_path=args.json_path,
                fixtures_path=args.fixtures,
                overwrite=not args.no_overwrite,
            )
        except SuiteLoadError as exc:  # pragma: no cover - defensive
            if args.traceback:
                traceback.print_exc()
            else:
                print(f"error: {exc}", file=sys.stderr)
            return 2
    if args.command == "check-text":
        try:
            return check_text(
                args.file,
                label=args.label,
                forbidden=args.forbidden,
                report_path=args.report,
                json_path=args.json_path,
            )
        except Exception as exc:  # pragma: no cover - defensive
            if args.traceback:
                traceback.print_exc()
            else:
                print(f"error: {exc}", file=sys.stderr)
            return 2
    parser.print_help()  # pragma: no cover - argparse enforces command
    return 2
