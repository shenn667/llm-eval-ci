"""CLI: `llm-eval run SUITE [--report PATH] [--json PATH] [--traceback]`.

Stdlib only (argparse/json/re/time). Offline-first: model outputs come from
embedded `stub` blocks in the suite file or from `--fixtures` (JSON object
mapping prompt -> {output, usage, delay_ms}). Exit codes: 0 = all pass,
1 = >=1 case failed, 2 = usage/environment error.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from typing import List, Optional

from . import __version__
from .models import StubModel
from .suite import Suite, SuiteLoadError

HELP_CHECKS = (
    "checks (SPEC_CASES.md §3):\n"
    "  contains, not_contains, regex, json_valid, json_schema_lite, refusal,\n"
    "  budget_tokens, budget_latency, budget_cost, no_pii_leak, no_injection_obey"
)

HELP_EPILOG = """examples:
  llm-eval run examples/cases.jsonl --report report.md --json report.json
  pytest --llm-eval=examples/cases.jsonl

%s

exit codes: 0 = all pass · 1 = ≥1 case failed · 2 = usage/environment error
""" % HELP_CHECKS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-eval",
        usage="llm-eval run SUITE [--report PATH] [--json PATH] [--overwrite] [--traceback]",
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
    try:
        result.write_markdown(report_path)
        result.write_json(json_path)
    except OSError as exc:
        if err_lines is not None:
            err_lines.append(f"error: cannot write report ({exc})")
        else:
            print(f"error: cannot write report ({exc})", file=sys.stderr)
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
    parser.print_help()  # pragma: no cover - argparse enforces command
    return 2
