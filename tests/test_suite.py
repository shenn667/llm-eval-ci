"""Suite loading + runner (SPEC_CASES.md §2/§4/§5)."""

import json

import pytest

from llm_eval.models import StubModel
from llm_eval.suite import (
    CaseSpec,
    Suite,
    SuiteLoadError,
    load_suite_file,
    normalize_case,
    run_case,
)


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def ok_model(prompt):
    return {"output": "hello world", "usage": {"tokens": 5, "cost_usd": 0.0001}}


def test_load_jsonl_ok(tmp_path):
    p = write(tmp_path / "s.jsonl",
              '{"id": "a", "prompt": "hi", "checks": [{"name": "contains", "params": {"text": "x"}}]}\n'
              '\n'
              '{"id": "b", "prompt": "yo", "checks": [{"name": "contains", "params": {"text": "y"}}]}\n')
    ok_specs, errors, skipped = load_suite_file(p)
    assert len(ok_specs) == 2 and errors == [] and skipped == 0


def test_load_jsonl_skips_invalid_lines(tmp_path):
    p = write(tmp_path / "s.jsonl",
              '{"id": "a", "prompt": "hi", "checks": [{"name": "contains", "params": {"text": "x"}}]}\n'
              'NOT JSON {\n')
    ok_specs, errors, skipped = load_suite_file(p)
    assert len(ok_specs) == 1 and skipped == 1


def test_load_json_array_and_single_object(tmp_path):
    case = {"id": "a", "prompt": "hi", "checks": [{"name": "contains", "params": {"text": "x"}}]}
    p = write(tmp_path / "s.json", json.dumps([case, dict(case, id="b")]))
    ok_specs, errors, skipped = load_suite_file(p)
    assert len(ok_specs) == 2
    p2 = write(tmp_path / "one.json", json.dumps(case))
    ok_specs2, _, _ = load_suite_file(p2)
    assert len(ok_specs2) == 1


def test_load_errors_exit2_class():
    with pytest.raises(SuiteLoadError):
        load_suite_file("/does/not/exist.jsonl")
    with pytest.raises(SuiteLoadError):
        Suite.from_file("suite.yaml")


def test_load_bad_json_document_and_suffix(tmp_path):
    p = write(tmp_path / "bad.json", "{oops")
    with pytest.raises(SuiteLoadError):
        load_suite_file(p)
    p2 = write(tmp_path / "s.txt", "hello")
    with pytest.raises(SuiteLoadError):
        load_suite_file(p2)


def test_normalize_case_errors():
    seen = set()
    spec, err = normalize_case({"id": "a", "prompt": "", "checks": [{"name": "contains"}]}, seen)
    assert err == ["empty_prompt"]
    seen2 = set()
    spec, err = normalize_case({"id": "a", "prompt": "hi", "checks": []}, seen2)
    assert err == ["no_checks"]
    spec, err = normalize_case({"id": "a", "prompt": "hi"}, set())
    assert err == ["no_checks"]


def test_duplicate_id_second_case_errors():
    seen = set()
    raw = {"id": "dup", "prompt": "hi", "checks": [{"name": "contains", "params": {"text": "x"}}]}
    spec1, err1 = normalize_case(raw, seen)
    assert err1 is None
    spec2, err2 = normalize_case(raw, seen)
    assert err2 == ["duplicate_id"]


@pytest.mark.parametrize("bad_id", ["Bad", "a b", "", 42, None, "x" * 70])
def test_bad_ids_rejected(bad_id):
    _, err = normalize_case(
        {"id": bad_id, "prompt": "hi", "checks": [{"name": "contains"}]}, set())
    assert err is not None


def test_bad_budget_rejected():
    for budgets in ({"max_tokens": 0}, {"max_tokens": -1}, {"max_tokens": "x"},
                    {"max_latency_ms": 0}, {"max_cost_usd": -0.5}):
        raw = {"id": "a", "prompt": "hi", "checks": [{"name": "contains"}], **budgets}
        _, err = normalize_case(raw, set())
        assert err == ["bad_budget"], budgets


def test_non_mapping_raw_and_unknown_check():
    _, err = normalize_case("nope", set())
    assert err == ["invalid_case"]
    spec, err = normalize_case(
        {"id": "a", "prompt": "hi", "checks": [{"name": "mystery"}]}, set())
    assert err is None
    assert spec is not None
    assert spec.checks[0][0] == "unknown_check:mystery"


def test_normalize_check_variants():
    spec, err = normalize_case(
        {"id": "a", "prompt": "hi",
         "checks": ["oops", {}, {"type": "contains", "value": "hi"}, {"name": ""}]}, set())
    assert err is None
    assert spec is not None
    names = [n for n, _ in spec.checks]
    assert names[0].startswith("unknown_check:")
    assert names[1].startswith("unknown_check:")
    assert names[2] == "contains"
    assert names[3].startswith("unknown_check:")
    # meta / stub passthrough
    spec2, _ = normalize_case(
        {"id": "b", "prompt": "hi", "checks": [{"name": "contains"}],
         "stub": {"output": "hi"}, "meta": {"category": "x"}}, set())
    assert spec2 is not None
    assert spec2.stub == {"output": "hi"}
    assert spec2.meta == {"category": "x"}


def test_run_case_pass_and_budgets_auto():
    spec = CaseSpec(id="a", prompt="hi",
                    checks=[("contains", {"text": "hello"})],
                    budgets={"max_tokens": 50})
    res = run_case(spec, ok_model)
    assert res.status == "pass" and res.failed_checks == []
    assert res.latency_ms >= 0
    assert res.usage == {"tokens": 5, "cost_usd": 0.0001}


def test_run_case_unknown_check_and_budget_auto_fail():
    spec = CaseSpec(id="a", prompt="hi", checks=[("mystery", {})],
                    budgets={"max_tokens": 1})
    res = run_case(spec, ok_model)
    assert res.status == "fail"
    assert "mystery" in res.failed_checks
    assert "budget_tokens" in res.failed_checks  # 5 tokens > 1


def test_run_case_explicit_budget_wins_over_case_level():
    spec = CaseSpec(id="a", prompt="hi",
                    checks=[("budget_tokens", {"max": 1000})],
                    budgets={"max_tokens": 1})
    res = run_case(spec, ok_model)
    assert res.status == "pass"  # explicit 1000 wins, auto skipped


def test_run_case_model_errors_fail_closed():
    def boom(prompt):
        raise RuntimeError("kaput")

    res = run_case(CaseSpec(id="a", prompt="hi", checks=[("contains", {})]), boom)
    assert res.status == "fail" and res.failed_checks == ["model_error"]

    def weird(prompt):
        return {"output": None, "usage": None}

    res2 = run_case(CaseSpec(id="a", prompt="hi", checks=[("contains", {"text": "x"})]), weird)
    assert res2.status == "fail"


def test_run_case_missing_stub():
    model = StubModel({})
    res = run_case(CaseSpec(id="a", prompt="unknown?", checks=[("contains", {})]), model)
    assert res.status == "fail" and res.failed_checks == ["missing_stub"]


def test_suite_run_includes_error_specs_and_summary(tmp_path):
    p = write(tmp_path / "s.jsonl",
              '{"id": "good", "prompt": "hi", "checks": [{"name": "contains", "params": {"text": "hello"}}]}\n'
              '{"id": "good", "prompt": "hi again", "checks": [{"name": "contains"}]}\n'
              '{"id": "bad", "prompt": "", "checks": [{"name": "contains"}]}\n')
    suite = Suite.from_file(p)
    assert suite.skipped_invalid_lines == 0
    assert len(suite.errors) == 2
    result = suite.run(ok_model)
    assert result.total == 3
    assert result.passed == 1 and result.failed == 2
    assert not result.ok
    assert "1/3 passed" in result.summary()
    assert result.total_latency_ms >= 0
    assert result.total_cost_usd >= 0


def test_suite_helpers(tmp_path):
    p = write(tmp_path / "s.json", json.dumps([
        {"id": "a", "prompt": "hi", "stub": {"output": "hello"},
         "checks": [{"name": "contains", "params": {"text": "ell"}}]}]))
    suite = Suite.from_json(p)
    assert suite.embedded_stubs() == {"hi": {"output": "hello"}}
    assert Suite.from_jsonl(p).source == p
    d = suite.run(ok_model).to_dict()
    assert d["version"] and d["cases"][0]["id"] == "a"
