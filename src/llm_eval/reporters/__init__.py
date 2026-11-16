"""Reporters package: Markdown + JSON report writers (stdlib only)."""

from .json_report import result_to_dict, write_json_report
from .markdown import render_markdown, write_markdown_report

__all__ = [
    "result_to_dict",
    "write_json_report",
    "render_markdown",
    "write_markdown_report",
]
