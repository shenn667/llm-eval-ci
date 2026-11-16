"""pytest plugin: `pytest --llm-eval=SUITE` collects N tests = N cases.

One test item per case (including error specs: duplicate id, empty prompt,
no checks, bad budget). Each item replays the embedded suite stub offline via
StubModel and fails closed when the stub is missing or a check fails.
Stdlib only (no third-party imports besides pytest itself).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Generator, List, Tuple

import pytest

from .models import StubModel
from .suite import CaseSpec, Suite, SuiteLoadError


def pytest_addoption(parser: Any) -> None:
    group = parser.getgroup("llm-eval")
    group.addoption(
        "--llm-eval",
        action="store",
        default=None,
        metavar="SUITE",
        help=".jsonl/.json eval suite to collect as tests (one test per case)",
    )


def pytest_configure(config: Any) -> None:
    """Collect the suite even when it is not passed as a positional arg.

    `pytest --llm-eval=SUITE` (DESIGN section 2.1) carries the suite via the
    option only, so the suite file is appended to the collection args here.
    No-op for normal runs (no --llm-eval given).
    """
    try:
        opt = config.getoption("llm_eval", None)
    except (ValueError, AttributeError):
        return
    if opt and str(opt) not in [str(a) for a in getattr(config, "args", [])]:
        config.args.append(str(opt))


def pytest_collect_file(file_path: Path, parent: Any) -> Any:
    opt = getattr(parent.config.option, "llm_eval", None)
    if not opt:
        return None
    wanted = Path(str(opt))
    try:
        if Path(str(file_path)).resolve() != wanted.resolve():
            return None
    except OSError:
        return None
    suffix = Path(str(file_path)).suffix.lower()
    if suffix not in (".jsonl", ".json"):
        return None
    return LlmEvalFile.from_parent(parent, path=Path(str(file_path)))


class LlmEvalFile(pytest.File):
    def collect(self) -> Generator[Any, None, None]:
        try:
            suite = Suite.from_file(str(self.path))
        except SuiteLoadError as exc:
            raise self.CollectError(f"llm-eval: cannot load suite: {exc}") from exc
        specs: List[Tuple[CaseSpec, List[str] | None]] = [
            (spec, None) for spec in suite.cases
        ] + [(spec, failed) for spec, failed in suite.errors]
        stubs = suite.embedded_stubs()
        for spec, error in specs:
            yield LlmEvalItem.from_parent(
                self, name=spec.id, spec=spec, error=error,
                stub=spec.stub, stubs=stubs,
            )


class LlmEvalItem(pytest.Item):
    def __init__(
        self, *args: Any, spec: CaseSpec, error: List[str] | None,
        stub: Any = None, stubs: Any = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.spec = spec
        self.error = error
        self.stub = stub
        self.stubs = dict(stubs or {})

    def runtest(self) -> None:
        if self.error:
            raise LlmEvalFailure(
                f"case {self.spec.id!r}: invalid spec ({', '.join(self.error)})"
            )
        from .suite import run_case

        if self.stub is not None:
            # Per-case stub: correct even when several cases share one prompt.
            model = StubModel({self.spec.prompt: self.stub})
        else:
            model = StubModel(self.stubs)
        result = run_case(self.spec, model)
        if result.status != "pass":
            failed = ", ".join(result.failed_checks) or "failed"
            details = "; ".join(
                f"{k}: {v}" for k, v in (result.details or {}).items() if k in result.failed_checks
            )
            msg = f"case {self.spec.id!r}: failed: {failed}"
            if details:
                msg += f" ({details})"
            raise LlmEvalFailure(msg)

    def repr_failure(self, excinfo: Any) -> str:
        if excinfo.errisinstance(LlmEvalFailure):
            return str(excinfo.value)
        return super().repr_failure(excinfo)

    def reportinfo(self) -> Tuple[Any, Any, str]:
        return self.path, 0, f"llm-eval: {self.name}"


class LlmEvalFailure(Exception):
    """Case verdict failure (failed checks or invalid spec)."""
