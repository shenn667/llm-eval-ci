"""Guardrail: no network in tests (brief §2: tests sans réseau)."""

import socket

# Import ssl BEFORE patching socket.socket.
# ssl.SSLSocket subclasses socket.socket at import time: if socket.socket
# has already been replaced by a plain function, `import ssl` blows up with
# `TypeError: type 'SSLSocket' is not an acceptable base type` (seen on CI
# run 43835474441, env with only `pytest` installed — locally pytest-asyncio
# pre-imports ssl and masks the bug).
import ssl  # noqa: F401  # pylint: disable=wrong-import-position,unused-import

import pytest

pytest_plugins = ["pytester"]


def _blocked(*args, **kwargs):
    raise RuntimeError("network disabled in tests (socket blocked)")


# Block at the method level so already-defined socket subclasses
# (e.g. ssl.SSLSocket, bound to the real class before our patch) stay blocked.
socket.socket.connect = _blocked  # type: ignore[method-assign,assignment]
socket.create_connection = _blocked  # type: ignore[assignment]
try:
    ssl.SSLSocket.connect = _blocked  # type: ignore[method-assign]
except Exception:
    pass


class _BlockedSocket(socket.socket):
    """Drop-in replacement for socket.socket: still a real subclass (so
    `class SSLSocket(socket.socket)` keeps working if ssl is imported late),
    but instantiation always raises."""

    def __new__(cls, *args, **kwargs):
        raise RuntimeError("network disabled in tests (socket blocked)")


socket.socket = _BlockedSocket  # type: ignore[assignment]
