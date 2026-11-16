"""Model adapters — Bring-Your-Own-Model callables (stdlib only)."""

from .base import BaseModel, ModelFn, normalize_result
from .stub import StubModel

__all__ = ["ModelFn", "BaseModel", "StubModel", "normalize_result"]
