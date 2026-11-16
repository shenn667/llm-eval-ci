"""StubModel — offline canned prompt->response fixtures (stdlib only)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Union


class UnknownPromptError(KeyError):
    """Raised when a prompt has no stubbed response (strict mode)."""


class StubModel:
    """Replay canned responses — fully offline, reproducible, CI-friendly.

    Mapping values accept either a plain string (used as ``output`` with
    no usage) or a dict ``{"output": str, "usage": {...}, "delay_ms": int}``.
    ``delay_ms`` simulates latency via ``time.sleep`` (StubModel-only knob;
    real-model latency is measured wall-clock by the runner).
    """

    def __init__(
        self,
        mapping: Optional[Mapping[str, Any]] = None,
        *,
        default_output: str = "",
        strict: bool = False,
    ) -> None:
        self._mapping: Dict[str, Any] = dict(mapping or {})
        self.default_output = default_output
        self.strict = strict

    # -- constructors -----------------------------------------------------
    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any], **kwargs: Any) -> "StubModel":
        return cls(mapping, **kwargs)

    @classmethod
    def from_cases(cls, cases: Sequence[Mapping[str, Any]], **kwargs: Any) -> "StubModel":
        """Build from loaded suite cases using each case's prompt.

        Cases may carry an embedded ``stub`` block (examples/*.json style)
        or a top-level ``output``/``stub_output`` fixture.
        """
        mapping: Dict[str, Any] = {}
        for case in cases:
            prompt = case.get("prompt")
            if not isinstance(prompt, str):
                continue
            if isinstance(case.get("stub"), dict):
                mapping[prompt] = case["stub"]
            elif "output" in case and isinstance(case.get("output"), str):
                mapping[prompt] = {
                    "output": case["output"],
                    "usage": case.get("usage"),
                }
        return cls(mapping, **kwargs)

    @classmethod
    def from_json(cls, path: Union[str, Path], **kwargs: Any) -> "StubModel":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "mapping" in raw and isinstance(raw["mapping"], dict):
            raw = raw["mapping"]
        if not isinstance(raw, dict):
            raise ValueError(f"stub fixture must be a JSON object: {path}")
        return cls(raw, **kwargs)

    # -- call -------------------------------------------------------------
    def __call__(self, prompt: str) -> Dict[str, Any]:
        if prompt in self._mapping:
            entry = self._mapping[prompt]
        elif self.strict:
            raise UnknownPromptError(f"no stubbed response for prompt: {prompt!r}")
        else:
            return {"output": self.default_output, "usage": None}
        if isinstance(entry, str):
            return {"output": entry, "usage": None}
        if not isinstance(entry, dict):
            return {"output": self.default_output, "usage": None}
        delay = entry.get("delay_ms", 0)
        try:
            delay_ms = int(delay or 0)
        except (TypeError, ValueError):
            delay_ms = 0
        if delay_ms > 0:
            time.sleep(min(delay_ms, 5000) / 1000.0)
        return {"output": entry.get("output", ""), "usage": entry.get("usage")}
