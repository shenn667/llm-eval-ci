"""Reporters: JSON contract + Markdown layout (DESIGN.md §3/§4, PII masked)."""

import json

from llm_eval.reporters.json_report import render_json, result_to_dict, write_json_report
from llm_eval.reporters.markdown import render_markdown, write_markdown_report
from llm_eval.suite import CaseResult, RunResult


def make_result():
    ok = CaseResult(id="faq_refund_ok", status="pass", failed_checks=[],
                    latency_ms=120, usage={"tokens": 150, "cost_usd": 0.0002},
                    details={"contains": "found 'policy'"})
    ko = CaseResult(
        id="inj_ignore_and_leak", status="fail",
        failed_checks=["no_injection_obey", "refusal", "no_pii_leak"],
        latency_ms=210, usage={"tokens": 300, "cost_usd": 0.0008},
        detections=[{"check": "no_pii_leak", "pattern": "email",
                     "count": 1, "sample": "***"}],
        details={"no_pii_leak": "PII pattern(s) matched: email (values masked)"},
    )
    return RunResult(cases=[ok, ko], suite_name="examples/cases.jsonl",
                     skipped_invalid_lines=1)


def test_json_report_contract():
    d = result_to_dict(make_result())
    assert set(["version", "cases"]).issubset(d)
    assert d["suite"] == "examples/cases.jsonl"
    assert d["skipped_invalid_lines"] == 1
    assert d["summary"]["total"] == 2
    assert d["summary"]["passed"] == 1 and d["summary"]["failed"] == 1
    case = d["cases"][0]
    assert set(["id", "status", "failed_checks", "latency_ms", "usage"]).issubset(case)
    assert case["usage"] == {"tokens": 150, "cost_usd": 0.0002}
    assert d["cases"][1]["detections"][0]["sample"] == "***"
    json.dumps(d)  # parsable sans option


def test_json_report_missing_usage_and_empty():
    r = RunResult(cases=[CaseResult(id="a", status="fail",
                                    failed_checks=["budget_tokens"],
                                    latency_ms=3, usage=None)],
                  suite_name="s")
    d = result_to_dict(r)
    assert d["cases"][0]["usage"] is None
    assert d["summary"]["pass_rate"] == 0.0
    empty = result_to_dict(RunResult(cases=[], suite_name="s"))
    assert empty["summary"]["total"] == 0 and empty["summary"]["pass_rate"] == 0.0


def test_json_write_and_render(tmp_path):
    p = write_json_report(make_result(), str(tmp_path / "r.json"))
    assert json.loads(open(p, encoding="utf-8").read())["version"]
    assert render_json(make_result()).endswith("\n")


def test_markdown_layout_and_masking(tmp_path):
    md = render_markdown(make_result())
    assert md.splitlines()[0].startswith("# llm-eval report")
    assert "| case | status | latency | tokens | cost_usd | failed_checks |" in md
    assert "1 passed (50.0%)" in md
    assert "✅ pass" in md and "❌ FAIL" in md
    assert "## Failures" in md and "## PII / injection detections" in md
    assert "## Budgets" in md and "***" in md
    assert "admin@example.com" not in md and "jean.dupont" not in md
    p = write_markdown_report(make_result(), str(tmp_path / "r.md"))
    assert open(p, encoding="utf-8").read() == md


def test_markdown_empty_sections():
    md = render_markdown(RunResult(cases=[], suite_name="s"))
    assert "_Aucun._" in md and "_Aucune détection._" in md


def test_markdown_usage_na():
    r = RunResult(cases=[CaseResult(id="a", status="fail",
                                    failed_checks=["budget_tokens"],
                                    latency_ms=3, usage=None)], suite_name="s")
    md = render_markdown(r)
    assert "n/a" in md
