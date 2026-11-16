"""JSON checks: json_valid / json_schema_lite (incl. legacy schema coercion)."""

from llm_eval.checks import json_checks
from llm_eval.checks.json_checks import _coerce_schema, _matches_type


def test_json_valid_ok_and_whitespace():
    assert json_checks.check_json_valid('{"a": 1}', {}, {}).passed
    assert json_checks.check_json_valid('  [1, 2]\n', {}, {}).passed


def test_json_valid_ko():
    r = json_checks.check_json_valid("not json", {}, {})
    assert not r.passed
    assert "not valid" in r.detail.lower() or "JSON" in r.detail


def _schema_required_types():
    return {"required": ["policy", "days"], "types": {"policy": "string", "days": "integer"}}


def test_schema_lite_pass():
    r = json_checks.check_json_schema_lite(
        '{"policy": "30 jours", "days": 30}', _schema_required_types(), {})
    assert r.passed


def test_schema_lite_missing_required():
    r = json_checks.check_json_schema_lite('{"policy": "x"}', _schema_required_types(), {})
    assert not r.passed
    assert "days" in r.detail


def test_schema_lite_wrong_type():
    r = json_checks.check_json_schema_lite(
        '{"policy": "x", "days": "thirty"}', _schema_required_types(), {})
    assert not r.passed


def test_schema_lite_invalid_json_and_non_object():
    assert not json_checks.check_json_schema_lite("nope", _schema_required_types(), {}).passed
    assert not json_checks.check_json_schema_lite("[1,2]", _schema_required_types(), {}).passed
    assert not json_checks.check_json_schema_lite('"str"', _schema_required_types(), {}).passed


def test_schema_lite_bad_params():
    assert not json_checks.check_json_schema_lite("{}", {"required": "policy"}, {}).passed
    assert not json_checks.check_json_schema_lite("{}", {"required": [42]}, {}).passed
    assert not json_checks.check_json_schema_lite("{}", {"types": {"a": "weird"}}, {}).passed
    assert not json_checks.check_json_schema_lite("{}", {"types": ["not-a-dict"]}, {}).passed
    assert not json_checks.check_json_schema_lite(
        "{}", {"required": [], "allow_extra": "yes"}, {}).passed


def test_schema_lite_extra_fields():
    params = {"required": ["a"], "types": {"a": "string"}, "allow_extra": False}
    assert json_checks.check_json_schema_lite('{"a": "x"}', params, {}).passed
    r = json_checks.check_json_schema_lite('{"a": "x", "b": 1}', params, {})
    assert not r.passed
    assert "extra" in r.detail
    # default allow_extra=True tolerates extras
    assert json_checks.check_json_schema_lite('{"a": "x", "b": 1}',
                                              {"required": ["a"]}, {}).passed


def test_schema_lite_absent_typed_field_ok():
    # types only constrain fields that ARE present (top-level only)
    r = json_checks.check_json_schema_lite('{"a": "x"}', {"types": {"zzz": "string"}}, {})
    assert r.passed


def test_bool_is_not_integer_nor_number():
    assert not json_checks.check_json_schema_lite(
        '{"n": true}', {"types": {"n": "integer"}}, {}).passed
    assert not json_checks.check_json_schema_lite(
        '{"n": true}', {"types": {"n": "number"}}, {}).passed
    assert json_checks.check_json_schema_lite(
        '{"n": true}', {"types": {"n": "boolean"}}, {}).passed
    assert json_checks.check_json_schema_lite(
        '{"n": 3}', {"types": {"n": "number"}}, {}).passed
    assert json_checks.check_json_schema_lite(
        '{"n": 3.5}', {"types": {"n": "number"}}, {}).passed


def test_matches_type_all_branches():
    assert _matches_type("s", "string")
    assert _matches_type(3, "integer")
    assert _matches_type([1], "array")
    assert _matches_type({"k": 1}, "object")
    assert _matches_type(None, "null")
    assert _matches_type(False, "boolean")
    assert not _matches_type("s", "integer")
    assert not _matches_type("s", "bogus-type")
    assert not _matches_type([1], "object")


def test_coerce_legacy_schema_style():
    out = _coerce_schema({"schema": {"required": ["city"],
                                     "properties": {"city": {"type": "string"}}}})
    assert out["required"] == ["city"]
    assert out["types"] == {"city": "string"}
    # params already SPEC-style: untouched
    params = {"required": ["a"], "schema": {"required": ["b"]}}
    assert _coerce_schema(params) is params
    # no schema key: untouched
    params2 = {"required": ["a"]}
    assert _coerce_schema(params2) is params2
    # non-dict schema: untouched
    params3 = {"schema": "weird"}
    assert _coerce_schema(params3) is params3


def test_coerce_legacy_schema_end_to_end():
    params = {"schema": {"type": "object", "required": ["city", "temp_c"],
                         "properties": {"city": {"type": "string"},
                                        "temp_c": {"type": "number"}}}}
    assert json_checks.check_json_schema_lite(
        '{"city": "Lyon", "temp_c": 21}', params, {}).passed
    assert not json_checks.check_json_schema_lite(
        '{"city": "Lyon"}', params, {}).passed
