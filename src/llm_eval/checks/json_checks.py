"""JSON checks: json_valid / json_schema_lite (in-house subset, no jsonschema dep)."""

from __future__ import annotations

import json
from typing import Any, Dict

from .base import CheckResult, as_params, failed, is_int, is_num, passed

TYPE_NAMES = ("string", "integer", "number", "boolean", "array", "object", "null")


def _matches_type(value: Any, want: str) -> bool:
    if want == "string":
        return isinstance(value, str)
    if want == "integer":
        return is_int(value)  # bool is NOT an integer
    if want == "number":
        return is_num(value)  # bool is NOT a number
    if want == "boolean":
        return isinstance(value, bool)
    if want == "array":
        return isinstance(value, list)
    if want == "object":
        return isinstance(value, dict)
    if want == "null":
        return value is None
    return False


def _coerce_schema(params: Dict[str, Any]) -> Dict[str, Any]:
    """Accept SPEC params {required, types, allow_extra} and the legacy
    JSON-schema style {schema: {required, properties: {f: {type}}}}."""
    schema = params.get("schema")
    if isinstance(schema, dict) and ("required" not in params and "types" not in params):
        props = schema.get("properties", {})
        types = {k: v.get("type") for k, v in props.items() if isinstance(v, dict) and "type" in v}
        out = dict(params)
        if "required" in schema:
            out["required"] = schema["required"]
        if types:
            out["types"] = types
        return out
    return params


def check_json_valid(output: str, params: Any, ctx: Dict[str, Any]) -> CheckResult:
    try:
        json.loads(output.strip())
    except (json.JSONDecodeError, ValueError) as exc:
        return failed(f"output is not valid JSON ({exc})")
    return passed("output parses as JSON")


def check_json_schema_lite(output: str, params: Any, ctx: Dict[str, Any]) -> CheckResult:
    params = _coerce_schema(as_params(params))
    required = params.get("required", [])
    types = params.get("types", {})
    allow_extra = params.get("allow_extra", True)
    if not isinstance(required, list) or not all(isinstance(r, str) for r in required):
        return failed("json_schema_lite: 'required' must be a list of strings")
    if not isinstance(types, dict) or not all(
        isinstance(k, str) and v in TYPE_NAMES for k, v in types.items()
    ):
        return failed(f"json_schema_lite: 'types' values must be in {list(TYPE_NAMES)}")
    if not isinstance(allow_extra, bool):
        return failed("json_schema_lite: 'allow_extra' must be a bool")
    try:
        doc = json.loads(output.strip())
    except (json.JSONDecodeError, ValueError):
        return failed("json_schema_lite: output is not valid JSON")
    if not isinstance(doc, dict):
        return failed("json_schema_lite: top-level JSON value must be an object")
    # Top-level only in v0.1.0 (dotted keys like "a.b" are literal field names).
    for key in required:
        if key not in doc:
            return failed(f"json_schema_lite: required field {key!r} missing")
    for key, want in types.items():
        if key in doc and not _matches_type(doc[key], want):
            return failed(f"json_schema_lite: field {key!r} is not of type {want}")
    if allow_extra is False:
        known = set(required) | set(types)
        extra = [k for k in doc if k not in known]
        if extra:
            return failed(f"json_schema_lite: extra fields not allowed: {extra}")
    return passed("output matches json_schema_lite")
