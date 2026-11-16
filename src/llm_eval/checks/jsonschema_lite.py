"""Alias module (task layout): re-exports JSON checks from json_checks.py.

Canonical implementation lives in :mod:`llm_eval.checks.json_checks`
(json_valid / json_schema_lite, in-house subset, no jsonschema dep).
"""

from .json_checks import TYPE_NAMES, check_json_schema_lite, check_json_valid

__all__ = [
    "TYPE_NAMES",
    "check_json_valid",
    "check_json_schema_lite",
    "JsonValidCheck",
    "JsonSchemaCheck",
]


class JsonValidCheck:
    """PASS iff ``output.strip()`` parses as JSON."""

    name = "json_valid"

    def __call__(self, output, params=None, ctx=None):
        return check_json_valid(output, params or {}, ctx or {})

    run = __call__


class JsonSchemaCheck:
    """PASS iff output is a JSON object matching the lite schema subset."""

    name = "json_schema_lite"

    def __call__(self, output, params=None, ctx=None):
        return check_json_schema_lite(output, params or {}, ctx or {})

    run = __call__
