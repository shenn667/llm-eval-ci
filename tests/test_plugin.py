"""pytest plugin: --llm-eval collects N tests = N cases (end-to-end)."""

import json
import textwrap

pytest_plugins = ["pytester"]

PLUGIN = "llm_eval.pytest_plugin"

GREEN = {"id": "green_case", "prompt": "Say hello.",
         "stub": {"output": "Hello!", "usage": {"tokens": 5, "cost_usd": 0.0001}},
         "checks": [{"name": "contains", "params": {"text": "Hello"}}]}
RED = {"id": "red_case", "prompt": "Say nothing.",
       "stub": {"output": "Hello!", "usage": {"tokens": 5, "cost_usd": 0.0001}},
       "checks": [{"name": "contains", "params": {"text": "quantum"}}]}


def write_suite(pytester, name="cases.jsonl", cases=None):
    if cases is None:
        cases = (GREEN, RED)
    target = pytester.path / name
    target.write_text("\n".join(json.dumps(c) for c in cases) + "\n", encoding="utf-8")
    return target


def run_eval(pytester, suite, *extra):
    # No explicit -p: the installed `llm-eval-ci` pytest11 entry point
    # auto-loads the plugin. Passing -p llm_eval.pytest_plugin as well
    # registers the same module twice -> "Plugin already registered".
    return pytester.runpytest(f"--llm-eval={suite}", *extra)


def test_collect_n_tests_equals_n_cases(pytester):
    suite = write_suite(pytester)
    result = run_eval(pytester, suite, "--collect-only", "-q")
    result.stdout.fnmatch_lines(["*green_case*", "*red_case*"])
    assert result.stdout.str().count("_case") >= 2


def test_green_passes_red_fails(pytester):
    suite = write_suite(pytester)
    result = run_eval(pytester, suite, "-q")
    result.assert_outcomes(passed=1, failed=1)


def test_error_spec_collected_and_fails(pytester):
    dup = {"id": "dup", "prompt": "hi",
           "stub": {"output": "hi", "usage": {"tokens": 1, "cost_usd": 0.0}},
           "checks": [{"name": "contains",
                       "params": {"text": "hi"}}]}
    suite = write_suite(pytester, cases=[dup, dict(dup)])
    result = run_eval(pytester, suite, "-q")
    result.assert_outcomes(passed=1, failed=1)


def test_missing_stub_fails_closed(pytester):
    lonely = {"id": "lonely", "prompt": "no stub here",
              "checks": [{"name": "contains", "params": {"text": "x"}}]}
    suite = write_suite(pytester, cases=[lonely])
    result = run_eval(pytester, suite, "-q")
    result.assert_outcomes(failed=1)


def test_no_option_collects_nothing(pytester):
    from llm_eval import pytest_plugin

    class FakeParent:
        class config:
            class option:
                llm_eval = None

    target = write_suite(pytester)
    assert pytest_plugin.pytest_collect_file(target, FakeParent()) is None
