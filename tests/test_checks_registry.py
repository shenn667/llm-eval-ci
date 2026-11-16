"""Registry + base helpers: dispatch, fail-closed output, param coercion."""

from llm_eval.checks import CHECKS, run_check
from llm_eval.checks.base import (
    FLAG_MAP,
    CheckResult,
    as_params,
    failed,
    is_int,
    is_num,
    passed,
)


def test_registry_has_11_checks():
    assert set(CHECKS) == {
        "contains", "not_contains", "regex", "json_valid", "json_schema_lite",
        "refusal", "budget_tokens", "budget_latency", "budget_cost",
        "no_pii_leak", "no_injection_obey",
    }


def test_run_check_dispatch_ok():
    assert run_check("contains", "hello", {"text": "hell"}, {}).passed
    assert not run_check("contains", "hello", {"text": "zzz"}, {}).passed


def test_run_check_unknown_name_fails():
    r = run_check("nope_not_a_check", "hello", {}, {})
    assert not r.passed
    assert "unknown" in r.detail


def test_run_check_non_string_output_fails_closed():
    assert not run_check("contains", None, {"text": "a"}, {}).passed  # type: ignore[arg-type]
    assert not run_check("json_valid", 42, {}, {}).passed  # type: ignore[arg-type]
    assert not run_check("refusal", ["x"], {}, {}).passed  # type: ignore[arg-type]


def test_base_result_helpers():
    ok = passed("fine")
    assert isinstance(ok, CheckResult) and ok.passed and ok.detail == "fine"
    assert ok.detections == []
    ko = failed("bad", [{"check": "x"}])
    assert not ko.passed and ko.detections == [{"check": "x"}]
    assert passed().detections == []


def test_as_params_coercion():
    assert as_params({"a": 1}) == {"a": 1}
    assert as_params(None) == {}
    assert as_params("nope") == {}
    assert as_params([1]) == {}


def test_is_int_and_is_num():
    assert is_int(3) and not is_int(True) and not is_int(3.0) and not is_int("3")
    assert is_num(3) and is_num(2.5)
    assert not is_num(True) and not is_num("3") and not is_num(None)
    assert FLAG_MAP["IGNORECASE"] is not None
