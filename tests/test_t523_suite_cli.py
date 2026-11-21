"""t_523e533b — suite loading/running, reporters, adapters, CLI, pytest plugin."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from llm_eval import __version__, RunResult, Suite, SuiteResult
from llm_eval.cli import build_parser, main, run_suite
from llm_eval.models import StubMissingError, StubModel
from llm_eval.reporters import json_report, markdown
from llm_eval.reporters import json as json_canonical
from llm_eval.suite import SuiteLoadError, load_suite_file

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _write(path: Path, obj) -> str:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(path)


# -- suite loading -----------------------------------------------------------
def test_load_json_array_and_from_json_alias(tmp_path):
    p = _write(tmp_path / "s.json", [
        {"id": "a", "prompt": "hi", "checks": [{"name": "contains", "params": {"text": "hi"}}],
         "stub": {"output": "hi!", "usage": {"tokens": 1, "cost_usd": 0.0}}}])
    s1 = Suite.from_file(p)
    assert len(s1.cases) == 1 and s1.errors == [] and s1.skipped_invalid_lines == 0
    assert len(Suite.from_json(p).cases) == 1


def test_load_jsonl_skips_bad_lines(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text('{"id": "a", "prompt": "hi", "checks": [{"name": "contains", "params": {"text": "h"}}], "stub": {"output": "hi"}}\n\nNOT JSON\n',
                 encoding="utf-8")
    ok, errors, skipped = load_suite_file(str(p))
    assert len(ok) == 1 and skipped == 1 and errors == []


def test_error_specs_duplicate_empty_nochecks_badbudget_unknown(tmp_path):
    p = _write(tmp_path / "s.json", [
        {"id": "dup", "prompt": "p1", "checks": [{"name": "contains", "params": {"text": "x"}}],
         "stub": {"output": "x"}},
        {"id": "dup", "prompt": "p2", "checks": [{"name": "contains", "params": {"text": "x"}}],
         "stub": {"output": "x"}},
        {"id": "empty", "prompt": "   ", "checks": [{"name": "contains", "params": {"text": "x"}}]},
        {"id": "nocheck", "prompt": "p", "checks": []},
        {"id": "badb", "prompt": "p", "checks": [{"name": "contains", "params": {"text": "x"}}],
         "max_tokens": -5},
        {"id": "unk", "prompt": "p", "checks": [{"name": "frobnicate"}],
         "stub": {"output": "x"}},
    ])
    suite = Suite.from_file(str(p))
    assert len(suite.errors) == 4  # dup(2nd), empty, nocheck, badb
    kinds = sorted(e for _, es in suite.errors for e in es)
    assert kinds == ["bad_budget", "duplicate_id", "empty_prompt", "no_checks"]
    result = suite.run()
    assert not result.ok
    failed_names = [c.failed_checks for c in result.cases]
    assert ["duplicate_id"] in failed_names


def test_unknown_check_fails_case_not_runner(tmp_path):
    p = _write(tmp_path / "s.json", [
        {"id": "unk", "prompt": "p", "checks": [{"name": "frobnicate"}],
         "stub": {"output": "x"}}])
    result = Suite.from_file(str(p)).run()
    assert result.total == 1 and not result.ok
    assert result.cases[0].failed_checks == ["unknown_check:frobnicate"]


def test_yaml_suffix_and_missing_file_are_usage_errors(tmp_path):
    with pytest.raises(SuiteLoadError):
        Suite.from_file(str(tmp_path / "nope.json"))
    with pytest.raises(SuiteLoadError):
        Suite.from_file("suite.yaml")


# -- suite running ------------------------------------------------------------
def test_run_uses_embedded_stub_and_measures_latency(tmp_path):
    p = _write(tmp_path / "s.json", [
        {"id": "slow", "prompt": "same", "checks": [{"name": "contains", "params": {"text": "ok"}}],
         "stub": {"output": "ok", "usage": {"tokens": 5, "cost_usd": 0.0}, "delay_ms": 120}}])
    result = Suite.from_file(str(p)).run()
    assert result.ok and result.cases[0].latency_ms >= 100


def test_duplicate_prompts_keep_own_stubs():
    suite = Suite.from_file(str(EXAMPLES / "latency_cost.json"))
    result = suite.run()
    by_id = {c.id: c for c in result.cases}
    assert by_id["within_budgets"].status == "pass"
    assert by_id["too_many_tokens"].failed_checks == ["budget_tokens"]
    assert by_id["too_slow"].failed_checks == ["budget_latency"]
    assert "budget_cost" in by_id["too_expensive"].failed_checks
    assert "budget_tokens" in by_id["usage_not_declared"].failed_checks


def test_examples_verdicts_match_notes():
    basic = {c.id: c for c in Suite.from_file(str(EXAMPLES / "basic.json")).run().cases}
    assert [c for c in basic.values() if c.status == "pass"] and len(basic) == 4
    assert basic["missing_keyword"].failed_checks == ["contains"]
    inj = {c.id: c for c in Suite.from_file(str(EXAMPLES / "injection_pii.json")).run().cases}
    assert inj["injection_refused"].status == "pass"
    assert inj["pii_not_leaked"].status == "pass"
    assert inj["injection_obeyed"].failed_checks == ["no_injection_obey"]
    assert inj["pii_leaked_email"].failed_checks == ["no_pii_leak"]


def test_suiteresult_alias_and_summary():
    assert SuiteResult is RunResult
    suite = Suite.from_file(str(EXAMPLES / "basic.json"))
    result = suite.run()
    assert not result.ok
    assert result.summary().startswith("3/4 passed")


def test_model_error_and_missing_stub_fail_closed(tmp_path):
    p = _write(tmp_path / "s.json", [
        {"id": "boom", "prompt": "p", "checks": [{"name": "contains", "params": {"text": "x"}}],
         "stub": {"output": "x"}}])

    def _boom(prompt):
        raise RuntimeError("kaput")

    result = Suite.from_file(str(p)).run(_boom)
    assert result.cases[0].failed_checks == ["model_error"]
    p2 = _write(tmp_path / "s2.json", [
        {"id": "nostub", "prompt": "p", "checks": [{"name": "contains", "params": {"text": "x"}}]}])
    assert Suite.from_file(str(p2)).run().cases[0].failed_checks == ["missing_stub"]
    with pytest.raises(StubMissingError):
        StubModel({})("unknown prompt")


# -- reporters -----------------------------------------------------------------
def test_markdown_layout_and_masking(tmp_path):
    result = Suite.from_file(str(EXAMPLES / "injection_pii.json")).run()
    md = markdown.render_markdown(result)
    assert md.splitlines()[0].startswith("# llm-eval report — ")
    for section in ("| case | status | latency | tokens | cost_usd | failed_checks |",
                    "## Failures", "## PII / injection detections", "## Budgets"):
        assert section in md
    assert "✅ pass" in md and "❌ FAIL" in md
    for secret in ("jean.dupont@example.com", "hunter2", "INV-2049"):
        assert secret not in md
    out = tmp_path / "r.md"
    assert markdown.write_markdown_report(result, str(out)) == str(out)


def test_json_report_contract_and_masking(tmp_path):
    result = Suite.from_file(str(EXAMPLES / "injection_pii.json")).run()
    d = json_report.result_to_dict(result)
    assert set(("version", "cases")) <= set(d)
    assert d["summary"]["total"] == 4
    for case in d["cases"]:
        assert set(("id", "status", "failed_checks", "latency_ms", "usage")) <= set(case)
        assert case["status"] in ("pass", "fail")
        for det in case.get("detections", []):
            assert det["sample"] == "***"
    blob = json.dumps(d)
    for secret in ("jean.dupont@example.com", "hunter2-FAKE", "INV-2049"):
        assert secret not in blob
    rp = tmp_path / "r.json"
    json_canonical.write_json_report(result, str(rp))
    assert json.loads(rp.read_text(encoding="utf-8"))["version"] == __version__
    out = tmp_path / "r2.json"
    result.write_json(str(out))
    assert json.loads(out.read_text(encoding="utf-8"))["version"] == __version__
    result.write_markdown(str(tmp_path / "r2.md"))


# -- adapters ----------------------------------------------------------------------
def test_stub_variants_and_openai_compat_offline():
    m = StubModel({"hi": {"output": "yo", "usage": {"tokens": 2, "cost_usd": 0.01}}})
    assert m("hi")["output"] == "yo"
    from llm_eval.adapters.openai_compat import OpenAICompatModel
    import os
    os.environ.pop("OPENAI_API_KEY", None)
    with pytest.raises(RuntimeError):
        OpenAICompatModel()("hello")


# -- CLI ----------------------------------------------------------------------------
def test_cli_three_examples_exit_1_and_green_exit_0(tmp_path):
    for name in ("basic", "injection_pii", "latency_cost"):
        code = run_suite(str(EXAMPLES / f"{name}.json"),
                         report_path=str(tmp_path / f"{name}.md"),
                         json_path=str(tmp_path / f"{name}.json"))
        assert code == 1
    green = _write(tmp_path / "green.json", [
        {"id": "ok", "prompt": "p", "checks": [{"name": "contains", "params": {"text": "y"}}],
         "stub": {"output": "y", "usage": {"tokens": 1, "cost_usd": 0.0}}}])
    assert run_suite(green, report_path=str(tmp_path / "g.md"),
                     json_path=str(tmp_path / "g.json")) == 0


def test_cli_exit_2_and_overwrite_guard(tmp_path):
    assert run_suite(str(tmp_path / "missing.json"),
                     report_path=str(tmp_path / "r.md"),
                     json_path=str(tmp_path / "r.json")) == 2
    assert run_suite("suite.yaml", report_path=str(tmp_path / "r.md"),
                     json_path=str(tmp_path / "r.json")) == 2
    ok = _write(tmp_path / "ok.json", [
        {"id": "ok", "prompt": "p", "checks": [{"name": "contains", "params": {"text": "y"}}],
         "stub": {"output": "y"}}])
    rp, jp = str(tmp_path / "r.md"), str(tmp_path / "r.json")
    assert run_suite(ok, report_path=rp, json_path=jp) == 0
    assert run_suite(ok, report_path=rp, json_path=jp, overwrite=False) == 2
    assert main(["run", ok, "--report", rp, "--json", jp, "--overwrite"]) == 0
    assert main(["run", ok, "--report", rp, "--json", jp, "--no-overwrite"]) == 2


def test_cli_help_and_module_entry():
    parser = build_parser()
    assert "--overwrite" in parser.format_help()
    assert "--traceback" in parser.format_help()
    assert main(["run", str(EXAMPLES / "basic.json"), "--report", "/tmp/x.md",
                 "--json", "/tmp/x.json"]) == 1


# -- pytest plugin -------------------------------------------------------------------
def test_plugin_collects_n_tests_and_fails_red(tmp_path):
    import shutil

    for name in ("basic.json", "latency_cost.json"):
        shutil.copy(EXAMPLES / name, tmp_path / name)
    basic, red = str(tmp_path / "basic.json"), str(tmp_path / "latency_cost.json")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", basic, "--llm-eval=" + basic,
         "--collect-only", "-q", "-p", "llm-eval-ci"],
        capture_output=True, text=True, cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "4 tests collected" in proc.stdout
    proc2 = subprocess.run(
        [sys.executable, "-m", "pytest", red, "--llm-eval=" + red,
         "-q", "-p", "llm-eval-ci"],
        capture_output=True, text=True, cwd=str(tmp_path))
    assert proc2.returncode != 0
    assert "4 failed" in proc2.stdout and "1 passed" in proc2.stdout
