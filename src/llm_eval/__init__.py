"""llm-eval-ci — pytest for LLMs/agents in CI (stdlib-only, offline-first)."""

__version__ = "0.1.0"

from .models import ModelFn, StubMissingError, StubModel
from .suite import CaseResult, RunResult, Suite, SuiteLoadError, load_suite_file
from .checks import BUDGET_CHECK_FOR_KIND, CHECKS, CHECK_NAMES, run_check
from .checks.regex import ContainsCheck, NotContainsCheck, RegexCheck
from .checks.jsonschema_lite import JsonSchemaCheck, JsonValidCheck
from .checks.latency import BudgetLatencyCheck
from .checks.cost import BudgetCostCheck, BudgetTokensCheck
from .checks.injection import NoInjectionObeyCheck, RefusalCheck
from .checks.pii import NoPIILeakCheck

# Backwards-compatible alias: the JSON report contract calls these SuiteResult.
SuiteResult = RunResult

__all__ = [
    "ModelFn",
    "StubMissingError",
    "StubModel",
    "Suite",
    "SuiteLoadError",
    "SuiteResult",
    "CaseResult",
    "RunResult",
    "load_suite_file",
    "CHECKS",
    "CHECK_NAMES",
    "BUDGET_CHECK_FOR_KIND",
    "run_check",
    "ContainsCheck",
    "NotContainsCheck",
    "RegexCheck",
    "JsonValidCheck",
    "JsonSchemaCheck",
    "RefusalCheck",
    "BudgetTokensCheck",
    "BudgetLatencyCheck",
    "BudgetCostCheck",
    "NoPIILeakCheck",
    "NoInjectionObeyCheck",
    "__version__",
]
