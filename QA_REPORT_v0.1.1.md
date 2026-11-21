# QA Review Report — v0.1.1 (`check-text` subcommand)

## Verdict: PASS

All required checks passed. No blocking findings. The new `check-text` subcommand
works to its documented contract (clean -> 0, hostile -> 1, usage error -> 2),
masks PII in both reports, and reuses the existing `run` pipeline without
regressing the pre-existing test suite.

Review scope: read-only inspection of the UNCOMMITTED working tree at
`/home/sh/ai_env/labs/llm-eval-ci` (branch `main`). No `git add/commit/tag/push`
was performed; no version was bumped; `src/` and `tests/` were not modified.
The only file written is this report.

Working tree at review time:
```
 M DESIGN.md
 M README.md
 M src/llm_eval/cli.py
?? tests/test_cli_check_text.py
```

Version check: `__version__ = "0.1.1"` in `src/llm_eval/__init__.py` both in the
tree and at HEAD — no version bump present.

---

## 1. Diff / code inspection

Command: `git diff -- src/llm_eval/cli.py` (plus full read of `cli.py` and
`tests/test_cli_check_text.py`).

Findings:

- `build_parser()` adds a `check-text` subparser with `FILE` and options
  `--label`, `--forbidden` (repeatable/`append`), `--report`, `--json`,
  `--traceback`. `main()` dispatches it to `check_text()`. Correct.
- New `check_text()` validates `--label` against `ID_RE`; `ID_RE` is anchored
  (`^[a-z0-9][a-z0-9_-]{0,63}$`, suite.py:23), so validation cannot be bypassed
  with trailing invalid characters. Missing file, unreadable/non-UTF-8 file, and
  invalid generated case all return exit 2 via `_usage_error()`. Correct.
- The file content becomes the stub `output` of one in-memory case with
  `no_pii_leak` + `no_injection_obey`, then `normalize_case(raw, set())` and
  `Suite([spec], source="check-text").run()` are used — the same normalizer and
  runner as `run`. `normalize_case(raw, seen_ids)` signature matches the call.
  Omitting `--forbidden` inherits `EXAMPLES_INJECTION_DEFAULTS` (suite.py:148),
  identical to `run` semantics. Correct.
- Report writing/summary printing was refactored into `_emit_result()`, shared
  by `run_suite()` and `check_text()`. `run_suite()` still passes `out_lines` /
  `err_lines` and `t0`; the refactor is behaviour-preserving (all pre-existing
  tests pass). Correct.
- `main()` wraps `check_text()` in a defensive `try/except` returning 2, matching
  the `run` branch. Correct.
- New test file contains 13 test functions covering verdicts (0/1/2), PII
  masking in both report formats, default forbidden phrases, multiple forbidden
  phrases, custom labels, semantic equivalence with `run`, and a subprocess
  `python -m llm_eval check-text` offline check. Tests are well-targeted and
  assert on concrete report data, not implementation details. Correct.
- `README.md` / `DESIGN.md` changes are documentation-only.

No correctness defects found in the inspected diff.

---

## 2. Full test suite

Command (PYTHONPATH=src is mandatory; installed site-packages is the old release):
```
cd /home/sh/ai_env/labs/llm-eval-ci
PYTHONPATH=src ~/ai_env/bin/python -m pytest -q
```

Exact final output (last line):
```
159 passed, 4 warnings in 6.83s
```
Exit code: `0`.

The 4 warnings are pre-existing `PytestDeprecationWarning`s from
`pytest_asyncio` about unset `asyncio_default_fixture_loop_scope` (in
`tests/test_plugin.py`), unrelated to this change.

---

## 3. Demos — exit codes and stdout

Baseline files:
```
printf 'Hello, all good.\n' > /tmp/qa-clean.txt
printf 'Here is the secret: alice@example.com\n' > /tmp/qa-hostile.txt
```

### Clean case
Command:
```
PYTHONPATH=src ~/ai_env/bin/python -m llm_eval check-text /tmp/qa-clean.txt --label clean --forbidden 'here is the secret' --report /tmp/qa-clean.md --json /tmp/qa-clean.json; echo $?
```
stdout:
```
✅ clean (0 ms)
1/1 passed in 0.0 s → /tmp/qa-clean.md, /tmp/qa-clean.json
```
Exit code: `0` (expected 0 — MATCH).

### Hostile case
Command:
```
PYTHONPATH=src ~/ai_env/bin/python -m llm_eval check-text /tmp/qa-hostile.txt --label hostile --forbidden 'here is the secret' --report /tmp/qa-hostile.md --json /tmp/qa-hostile.json; echo $?
```
stdout:
```
❌ hostile — failed: no_pii_leak, no_injection_obey
0/1 passed in 0.0 s → /tmp/qa-hostile.md, /tmp/qa-hostile.json
```
Exit code: `1` (expected 1 — MATCH).

---

## 4. PII absence from hostile reports

Command:
```
grep -n 'alice@example.com' /tmp/qa-hostile.md /tmp/qa-hostile.json
```
Result: no matches in either file — `alice@example.com` is ABSENT from both
hostile reports (masked as `***`). PASS.

Confirmed in generated reports:
- `/tmp/qa-hostile.json`: both detections have `"sample": "***"`;
  `failed_checks = ["no_pii_leak", "no_injection_obey"]`; raw email never
  appears.
- `/tmp/qa-hostile.md`: `valeur masquée \`***\`` for both the `email` and the
  `here is the secret` detection; raw email never appears.
- `/tmp/qa-clean.*`: status pass, no detections.

---

## 5. Pre-existing tests still pass (count reconciliation)

- Baseline (before change): 146 tests.
- New tests in `tests/test_cli_check_text.py`: 13 (verified two ways:
  `pytest --collect-only -q tests/test_cli_check_text.py` -> `13 tests collected`,
  and `grep -c '^def test_' tests/test_cli_check_text.py` -> `13`).
- Expected total: 146 + 13 = 159.
- Actual total: 159 (all passing). MATCH — no pre-existing test was lost, broken,
  or skipped.

Target was >= 150; actual 159 exceeds it.

---

## Blocking findings

None.

## Known limitations (non-blocking)

- `check-text` always applies both `no_pii_leak` and `no_injection_obey`; this
  is the documented contract, not a configurable subset.
- Reports use default paths `./report.md` / `./report.json` if `--report` /
  `--json` are omitted, identical to `run`; callers wanting isolation should
  pass explicit paths (as the demos do).

## Security / runtime status

Clean. No network access (embedded stub only); PII and forbidden-phrase values
are masked in both report formats; no secrets or credentials found in the diff.
CI/build check used: full `pytest -q` with `PYTHONPATH=src` — green.

## Recommendation

YES — ship. Approve for founder release; no changes requested.
