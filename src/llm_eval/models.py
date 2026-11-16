"""Model interface: ModelFn + StubModel (offline fixture replay)."""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, Mapping

# ModelFn(prompt) -> {"output": str, "usage": {"tokens": int, "cost_usd": float}}
ModelFn = Callable[[str], Dict[str, Any]]


class StubMissingError(KeyError):
    """Raised when a StubModel has no canned response for a prompt."""


class StubModel:
    """Deterministic offline model: maps prompt -> canned response.

    Mapping values are dicts: {"output": str, "usage": {"tokens": int,
    "cost_usd": float} | None, "delay_ms": int (StubModel-only latency knob)}.
    Unknown prompt -> StubMissingError (runner fails the case closed).
    """

    def __init__(self, mapping: Mapping[str, Mapping[str, Any]]) -> None:
        self._map: Dict[str, Mapping[str, Any]] = dict(mapping)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._map)

    def __call__(self, prompt: str) -> Dict[str, Any]:
        if prompt not in self._map:
            raise StubMissingError(f"no stubbed response for prompt: {prompt!r}")
        entry = self._map[prompt]
        raw_delay = entry.get("delay_ms", 0) if isinstance(entry, Mapping) else 0
        if isinstance(raw_delay, bool):
            delay_ms = 0
        elif isinstance(raw_delay, (int, float)) and raw_delay > 0:
            delay_ms = raw_delay
        else:
            delay_ms = 0
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
        output = entry.get("output", "") if isinstance(entry, Mapping) else ""
        usage = entry.get("usage") if isinstance(entry, Mapping) else None
        return {"output": output, "usage": usage}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StubModel":
        if isinstance(data, Mapping) and "fixtures" in data and isinstance(data["fixtures"], Mapping):
            data = data["fixtures"]
        if not isinstance(data, Mapping):
            raise ValueError("fixtures must be a JSON object mapping prompt -> response")
        return cls(data)

    @classmethod
    def from_file(cls, path: str) -> "StubModel":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    @classmethod
    def from_list(cls, items: list) -> "StubModel":
        mapping: Dict[str, Any] = {}
        for item in items:
            if isinstance(item, Mapping) and "prompt" in item:
                mapping[item["prompt"]] = {
                    "output": item.get("output", ""),
                    "usage": item.get("usage"),
                    "delay_ms": item.get("delay_ms", 0),
                }
        return cls(mapping)
