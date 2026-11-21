# llm-eval-ci

<!-- Replace YOUR_ORG with the real GitHub org/user when the repo is published. -->

[![CI](https://github.com/shenn667/llm-eval-ci/actions/workflows/ci.yml/badge.svg)](https://github.com/shenn667/llm-eval-ci/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/llm-eval-ci.svg)](https://pypi.org/project/llm-eval-ci/)
[![Python](https://img.shields.io/badge/python-3.10%20%E2%80%93%203.14-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

`pytest` for LLMs and agents, in CI. Deterministic, offline-first evals that fail your build when a model output regresses — stdlib only, zero runtime dependencies, no API key.

```bash
llm-eval run ./examples/basic.json --report ./report.md --json ./report.json
# exit code != 0 as soon as one case breaks a threshold
```

## Install (30 seconds)

```bash
pip install llm-eval-ci
```

From source:

```bash
git clone https://github.com/shenn667/llm-eval-ci.git
cd llm-eval-ci
pip install -e .
```

Requirements: Python 3.10+, nothing else at runtime (`argparse`, `json`, `re`, `time` from the stdlib). No network calls, no API keys.

## 10-line example

```python
from llm_eval import Suite

suite = Suite.from_json("examples/basic.json")          # load cases
result = suite.run(lambda p: {"output": "Hello, world!",  # your ModelFn
                              "usage": {"tokens": 12, "cost_usd": 0.0}})
print(result.summary())        # 3/4 passed, 1 failed: [missing_keyword]
result.write_markdown("report.md")
result.write_json("report.json")
assert result.ok               # False -> CI step fails
```

Bring your own model with one function: `ModelFn(prompt) -> {"output": str, "usage": {"tokens": int, "cost_usd": float}}`. For CI and demos, `StubModel` replays canned prompt-to-response fixtures from JSON — fully offline and reproducible.

## CLI demo

Three pedagogical suites ship in `examples/`. Green one first:

```bash
python -m llm_eval run examples/basic.json --report report.md --json report.json
echo $?   # 1 — 3 pass, 1 clean failure on purpose (see below)
```

Then the red ones — each fails the command with exit code 1, which is the point:

```bash
python -m llm_eval run examples/injection_pii.json --report report.md --json report.json
echo $?   # 1 — injection obeyed + PII leak detected
python -m llm_eval run examples/latency_cost.json --report report.md --json report.json
echo $?   # 1 — token / latency / cost budgets exceeded
```

### Check a single text file (v0.1.1+)

No suite file needed: `check-text` wraps one file as a single in-memory case
with `no_pii_leak` + `no_injection_obey`, then uses the exact same runner and
reporters as `run`. Offline, stdlib-only, values always masked.

```bash
python -m llm_eval check-text ./answer.txt --label answer \
  --forbidden "here is the secret" --report report.md --json report.json
echo $?   # 0 clean · 1 PII or forbidden phrase found · 2 usage error
```

`--forbidden` is repeatable. Omitting it uses the same credential-free default
phrases as a suite case without `forbidden`. Raw file content is never written
to either report — PII detections are reported as `***`.

Same suites as pytest, one test per case with native JUnit output for CI:

```bash
pytest --llm-eval=examples/basic.json
```

Sample `report.md` produced by the CLI:

```markdown
# llm-eval report — 3/5 passed (60%)

| case | status | latency | cost |
|------|--------|---------|------|
| within_budgets | PASS | 5 ms | $0.0001 |
| too_many_tokens | FAIL (budget_tokens) | 5 ms | $0.0001 |
| too_slow | FAIL (budget_latency) | 300 ms | $0.0001 |
| too_expensive | FAIL (budget_cost) | 5 ms | $0.0500 |
| usage_not_declared | FAIL (budget_tokens) | 5 ms | n/a |

## Detections
- `pii_leaked_email`: PII pattern matched (email) — value redacted: ***
```

`report.json` mirrors it in machine-readable form: `{version, cases: [{id, status, failed_checks[], latency_ms, usage}]}`. Secret values are always masked as `***` in both reports.

## Checks

| check | what it does |
|-------|--------------|
| `contains` / `not_contains` | substring present / absent in output |
| `regex` | `re.search` match on output |
| `json_valid` | output parses as JSON |
| `json_schema_lite` | in-house type/required subset (no `jsonschema` dependency) |
| `refusal` | output matches a refusal template (EN + FR) |
| `budget_tokens` / `budget_latency` / `budget_cost` | `usage` vs `max_tokens` / wall-clock vs `max_latency_ms` / `cost_usd` vs `max_cost_usd`; missing `usage` fails closed |
| `no_pii_leak` | FR + EN regexes (email, phone, IBAN, simplified ssn); hits are masked in reports |
| `no_injection_obey` | prompt matches known injection patterns and output is not a refusal |

Case-file format is JSON (array of cases) or JSONL (one case per line) — never YAML, so there is nothing to install. Each case carries a `note` field stating its expected verdict; see `SPEC_CASES.md` for the exact schema.

## Limitations & Roadmap

Honest limits of v0.1.0:

- No LLM-as-judge, on purpose. A model grading a model costs money per run, is non-deterministic (flaky CI), and needs network + secrets — the opposite of a gate that must be fast, free, and reproducible. Deterministic string/schema/budget checks catch regressions; qualitative review stays human.
- `no_injection_obey` and `no_pii_leak` are pattern heuristics (regex + refusal templates), not guarantees. A novel phrasing can bypass them; the security fixtures document known bypass classes. They are tripwires, not proofs.
- No semantic similarity or embeddings: paraphrased-but-correct answers fail `contains`/`regex`. Write checks on invariants (keys, formats, refusals), not on wording.
- Stub latency (`delay_ms`) only simulates slowness; with real models, `budget_latency` is wall-clock and can flake on loaded runners — set generous thresholds in CI.
- No streaming, no server storage, no web dashboard, no provider adapters (OpenAI & co. are a v0.2.0 opt-in, outside the stdlib-only core).

## Development

```bash
pip install -e .          # dev install
pytest                    # >=30 tests, 100% on checks/
```

CI (GitHub Actions, <60 s, Python 3.10–3.14, no secrets): lint + pytest + CLI demo. `LICENSE` is MIT. Releases are tagged `vX.Y.Z`; PyPI publication is manual and requires founder approval.

## License

MIT — see [LICENSE](LICENSE).
