"""Base model interface: ModelFn(prompt) -> dict (stdlib only)."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Protocol, Tuple, runtime_checkable


class ModelResult(Dict[str, Any]):
    """Convention: {"output": str, "usage": {"tokens": int, "cost_usd": float}}."""


ModelFn = Callable[[str], Dict[str, Any]]


@runtime_checkable
class _ModelFnProtocol(Protocol):
    def __call__(self, prompt: str) -> Dict[str, Any]: ...


class BaseModel:
    """Minimal base class for model adapters (optional convenience)."""

    name = "base"

    def __call__(self, prompt: str) -> Dict[str, Any]:  # pragma: no cover - override
        raise NotImplementedError("subclass must implement __call__(prompt)")


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _as_cost(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    return None


def normalize_result(raw: Any) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Normalize a raw ModelFn return into (output, usage).

    Never raises: malformed payloads degrade to (None, None) and the
    runner marks every check FAIL (fail-closed, SPEC section 3/5).
    """
    if not isinstance(raw, dict):
        return None, None
    output = raw.get("output")
    if not isinstance(output, str):
        output = None
    usage_raw = raw.get("usage")
    usage: Optional[Dict[str, Any]] = None
    if isinstance(usage_raw, dict):
        tokens = _as_int(usage_raw.get("tokens"))
        cost_raw = usage_raw.get("cost_usd", usage_raw.get("cost"))
        cost = _as_cost(cost_raw)
        if tokens is not None or cost is not None:
            usage = {}
            if tokens is not None:
                usage["tokens"] = tokens
            if cost is not None:
                usage["cost_usd"] = cost
    return output, usage
