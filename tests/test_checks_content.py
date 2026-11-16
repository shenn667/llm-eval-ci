"""Content checks: contains / not_contains / regex."""

from llm_eval.checks import content


def test_contains_pass():
    r = content.check_contains("Hello, world!", {"text": "Hello"}, {})
    assert r.passed


def test_contains_fail():
    r = content.check_contains("Hello, world!", {"text": "quantum"}, {})
    assert not r.passed
    assert "quantum" in r.detail


def test_contains_legacy_value_key():
    r = content.check_contains("Hello, world!", {"value": "Hello"}, {})
    assert r.passed


def test_contains_case_sensitive():
    r = content.check_contains("Hello", {"text": "hello"}, {})
    assert not r.passed


def test_contains_missing_text_param():
    assert not content.check_contains("Hello", {}, {}).passed
    assert not content.check_contains("Hello", {"text": 42}, {}).passed
    assert not content.check_contains("Hello", {"value": None}, {}).passed
    assert not content.check_contains("Hello", "not-a-dict", {}).passed


def test_not_contains_pass_and_fail():
    assert content.check_not_contains("Hello", {"text": "quantum"}, {}).passed
    r = content.check_not_contains("Hello quantum", {"text": "quantum"}, {})
    assert not r.passed


def test_not_contains_case_sensitive():
    assert content.check_contains("Hello", {"text": "Hello"}, {}).passed
    assert content.check_not_contains("Hello", {"text": "hello"}, {}).passed


def test_not_contains_bad_param():
    assert not content.check_not_contains("Hello", {}, {}).passed
    assert not content.check_not_contains("Hello", {"text": 7}, {}).passed


def test_regex_match_and_nomatch():
    assert content.check_regex("order 42 shipped", {"pattern": r"\d+"}, {}).passed
    r = content.check_regex("no digits", {"pattern": r"\d+"}, {})
    assert not r.passed


def test_regex_flags_ignorecase():
    assert content.check_regex("HELLO", {"pattern": "hello", "flags": ["IGNORECASE"]}, {}).passed
    assert not content.check_regex("HELLO", {"pattern": "hello"}, {}).passed


def test_regex_flags_multiline_dotall():
    assert content.check_regex(
        "a\nb", {"pattern": "^b", "flags": ["MULTILINE"]}, {}).passed
    assert content.check_regex(
        "a\nb", {"pattern": "a.b", "flags": ["DOTALL"]}, {}).passed
    assert not content.check_regex("a\nb", {"pattern": "a.b"}, {}).passed


def test_regex_bad_params():
    assert not content.check_regex("x", {}, {}).passed
    assert not content.check_regex("x", {"pattern": 42}, {}).passed
    assert not content.check_regex("x", {"pattern": "a", "flags": "IGNORECASE"}, {}).passed
    assert not content.check_regex("x", {"pattern": "a", "flags": ["BOGUS"]}, {}).passed
    assert not content.check_regex("x", {"pattern": "a(b"}, {}).passed
