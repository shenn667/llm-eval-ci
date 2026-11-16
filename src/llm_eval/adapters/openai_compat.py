"""Optional OpenAI-compatible adapter (stdlib only, opt-in, v0.2.0 preview).

Not imported by the core runtime: no network happens unless you
instantiate and call this class explicitly. Uses ``urllib`` only —
no third-party dependency. Disabled by default because v0.1.0 is
offline-first (see README "Limitations & Roadmap").
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, Optional


class OpenAICompatModel:
    """Minimal ``/chat/completions`` client for OpenAI-compatible APIs."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        api_key: Optional[str] = None,
        timeout_s: float = 30.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        self.timeout_s = timeout_s

    def __call__(self, prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(
                "OpenAICompatModel needs an API key "
                "(pass api_key= or set OPENAI_API_KEY). "
                "The v0.1.0 core stays offline; this adapter is opt-in."
            )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"unexpected chat-completions payload: {exc}") from exc
        tokens: Optional[int] = None
        try:
            u = body.get("usage", {})
            tokens = int(u.get("prompt_tokens", 0)) + int(u.get("completion_tokens", 0))
        except (TypeError, ValueError):
            tokens = None
        usage: Dict[str, Any] = {}
        if tokens is not None:
            usage["tokens"] = tokens
        # Cost is unknown without a pricing table -> omit (budget_cost fails
        # closed when checked, per SPEC section 5).
        return {"output": content if isinstance(content, str) else str(content), "usage": usage or None}
