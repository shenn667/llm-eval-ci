"""Guardrail: no network in tests (brief §2: tests sans réseau)."""

import pytest

pytest_plugins = ["pytester"]

import socket


def _blocked(*args, **kwargs):
    raise RuntimeError("network disabled in tests (socket blocked)")


socket.socket = _blocked
