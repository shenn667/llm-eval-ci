"""Model interface: StubModel mapping / constructors / errors."""

import json

import pytest

from llm_eval.models import StubMissingError, StubModel


def test_stub_call_ok_and_len():
    m = StubModel({"hi": {"output": "hello",
                           "usage": {"tokens": 3, "cost_usd": 0.1}}})
    assert len(m) == 1
    assert m("hi") == {"output": "hello", "usage": {"tokens": 3, "cost_usd": 0.1}}


def test_stub_missing_raises():
    m = StubModel({})
    with pytest.raises(StubMissingError):
        m("unknown prompt")


def test_stub_entry_defaults():
    m = StubModel({"hi": {}})
    assert m("hi") == {"output": "", "usage": None}


def test_stub_from_dict_fixtures_key():
    m = StubModel.from_dict({"fixtures": {"hi": {"output": "yo"}}})
    assert m("hi")["output"] == "yo"
    with pytest.raises(ValueError):
        StubModel.from_dict(["not", "a", "dict"])  # type: ignore[arg-type]


def test_stub_from_file_and_from_list(tmp_path):
    p = tmp_path / "fix.json"
    p.write_text(json.dumps({"hi": {"output": "hello", "usage": {"tokens": 1}}}),
                 encoding="utf-8")
    m = StubModel.from_file(str(p))
    assert m("hi")["output"] == "hello"
    m2 = StubModel.from_list([{"prompt": "hi", "output": "hello",
                               "usage": {"tokens": 2}}])
    assert m2("hi") == {"output": "hello", "usage": {"tokens": 2}}
    m3 = StubModel.from_list([{"nope": 1}])
    assert len(m3) == 0


def test_stub_delay_ms_sleeps():
    m = StubModel({"slow": {"output": "ok", "delay_ms": 30}})
    import time
    t0 = time.perf_counter()
    assert m("slow")["output"] == "ok"
    assert (time.perf_counter() - t0) * 1000 >= 20
