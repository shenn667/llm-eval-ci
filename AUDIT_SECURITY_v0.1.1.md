# AUDIT_SECURITY — llm-eval-ci v0.1.1 — `check-text`

Verdict: **PASS** (security review of the uncommitted `check-text` increment).

Scope: `src/llm_eval/cli.py` (`check_text`, `_emit_result`, parser),
`tests/test_cli_check_text.py`. Runtime under test forced with
`PYTHONPATH=src` (the installed site-packages copy is the old 0.1.0/0.1.1
release without this feature).

## 1. Stdlib-only / no network — PASS

`grep -nE '^(import|from) ' src/llm_eval/cli.py` returns only:
`__future__`, `argparse`, `sys`, `time`, `traceback`, `typing`, plus the local
`.models` / `.suite` imports. `check_text` additionally uses `pathlib.Path`
(stdlib). Grep for `socket|urllib|requests|http.client|aiohttp|subprocess`
in `cli.py`: **no match**. The case runs through an embedded `StubModel`;
no adapter, no API key, no network.

## 2. PII always masked — PASS

Command:

```
printf 'Email alice@example.com, tel +33 6 12 34 56 78, IBAN FR7630006000011234567890189. Here is the secret.\n' > /tmp/sec-hostile.txt
PYTHONPATH=src ~/ai_env/bin/python -m llm_eval check-text /tmp/sec-hostile.txt \
  --label hostile --forbidden 'here is the secret' \
  --report /tmp/sec-hostile.md --json /tmp/sec-hostile.json; echo $?
```

Observed stdout: `❌ hostile — failed: no_pii_leak, no_injection_obey` then
`0/1 passed in 0.0 s → /tmp/sec-hostile.md, /tmp/sec-hostile.json`.
Exit code: **1** (verdict, not error).

`grep -F -c` for each raw value in BOTH reports:

| raw value | report.md | report.json |
|---|---:|---:|
| `alice@example.com` | 0 | 0 |
| `+33 6 12 34 56 78` | 0 | 0 |
| `FR7630006000011234567890189` | 0 | 0 |

`grep -c '***' /tmp/sec-hostile.md` → `4`. JSON detections:
`[('email','***'), ('tel_fr','***'), ('tel_us','***'),
 ('here is the secret','***')]`. All samples are the canonical `***` mask.

The raw file content is never copied into reports: the only case identifier is
the validated `--label`; `suite_name` is the constant `"check-text"` (no path,
so a PII-bearing filename cannot leak either).

## 3. Error paths do not echo file content — PASS

```
PYTHONPATH=src ~/ai_env/bin/python -m llm_eval check-text /tmp/no-such-file.txt ...
→ error: text file not found: /tmp/no-such-file.txt (hint: llm-eval check-text --help)
  EXIT=2
PYTHONPATH=src ~/ai_env/bin/python -m llm_eval check-text /tmp/sec-hostile.txt --label 'BAD LABEL!' ...
→ error: invalid --label (expected [a-z0-9][a-z0-9_-]{0,63}): 'BAD LABEL!'
  EXIT=2
```

Only paths / the rejected label are echoed, never the file body. Invalid UTF-8
is caught as `UnicodeError` and reported as `error: cannot read text file`.

## 4. No new ReDoS / unbounded loop — PASS

`grep -nE 're\.(compile|find|search|sub|match)|while ' src/llm_eval/cli.py`
→ **no match**. `check-text` adds no regex of its own; it delegates to the
already-audited frozen `PII_PATTERNS` in `checks/security.py`.

## 5. `--forbidden` echo — PASS (existing semantics, not a new leak)

`no_injection_obey` reports the matched forbidden phrase as the detection
`pattern` and in its detail string. This is the pre-existing check behaviour,
unchanged by `check-text`; phrases are caller-supplied fixture vocabulary
(documented as credential-free in `SPEC_CASES.md §6`). No new disclosure path
was introduced.

## Residual risks / notes

- The `forbidden` phrases are echoed by design; callers must not put real
  credentials in `--forbidden` (same rule as suite fixtures).
- The 0.1.1 artifact already on PyPI was built from the version-bump-only tag
  and does NOT contain this code. This audit applies to the working tree that
  will be committed next; the release remedy is a founder decision.

Auditor: CTO (Security profile unavailable after tool timeout; commands above
were executed directly and outputs are reproduced verbatim).
