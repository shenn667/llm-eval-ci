# DESIGN.md — llm-eval-ci v0.1.0 (DX CLI + rapports)

Source de vérité produit : `PRODUCT_BRIEF.md`. Normatif pour les cas : `SPEC_CASES.md`
(PM) — en cas de conflit, SPEC gagne sur les noms de champs et la sémantique.
Pas de code ici. Pas d'UI — CLI + lisibilité des rapports uniquement.

## 1. Suites de cas — rappel DX (détail normatif : SPEC_CASES.md)

- Fichier `.jsonl` : un objet JSON par ligne, UTF-8, lignes vides ignorées.
  `.json` (tableau) accepté au chargement par tolérance ; `.yaml`/`.yml` refusé (exit 2, §2.3).
- Ligne cas : `{"id": ..., "prompt": ..., "checks": [{"name": ..., "params": {...}}], "max_tokens"?, "max_latency_ms"?, "max_cost_usd"?, "meta"?}`.
  `checks[].name` ∈ 11 noms SPEC §3 (`contains`, `not_contains`, `regex`,
  `json_valid`, `json_schema_lite`, `refusal`, `budget_tokens`, `budget_latency`,
  `budget_cost`, `no_pii_leak`, `no_injection_obey`). Aucun check implicite.
- Fichier invalide ≠ cas invalide : ligne non-JSON → **ignorée + compteur**
  `skipped_invalid_lines` (warning stderr, pas fatal) ; cas `duplicate_id` /
  `empty_prompt` / `no_checks` / `bad_budget` / `unknown_check:<name>` →
  cas `fail` (exit 1), jamais exit 2. Exit 2 = usage/environnement uniquement.

## 2. CLI — DX

### 2.1 Commandes

```text
llm-eval run ./evals/cases.jsonl --report ./report.md --json ./report.json
python -m llm_eval run examples/cases.jsonl --report report.md --json report.json
pytest --llm-eval=./evals/cases.jsonl
```

- `run SUITE` : sous-commande historique (v0.1.0). `--report PATH` (défaut `./report.md`),
  `--json PATH` (défaut `./report.json`). Écrasement par défaut.
- `check-text FILE` (v0.1.1) : cas unique en mémoire `no_pii_leak` +
  `no_injection_obey`, contenu du fichier comme stub output. Mêmes normaliseur,
  runner, reporters et codes de sortie que `run`. `--label` (id, défaut
  `check_text`), `--forbidden PHRASE` répétable, `--report` / `--json`.
- stdout humain : une ligne par cas puis résumé :
  `✅ faq_refund_ok (123 ms)` / `❌ inj_ignore_and_leak — failed: no_injection_obey, refusal, no_pii_leak`,
  puis `2/3 passed in 1.2 s → report.md, report.json`. stderr réservé aux erreurs/warnings.

### 2.2 `--help` exact (une page, copiable)

```text
usage: llm-eval run SUITE [--report PATH] [--json PATH] [--traceback]

Run deterministic LLM evals offline (stdlib only, no network).

positional:
  SUITE                 .jsonl suite (one JSON object per line)

options:
  --report PATH         Markdown report (default: ./report.md)
  --json PATH           JSON report (default: ./report.json)
  --traceback           print traceback on usage errors (default: one-line error)

examples:
  llm-eval run examples/cases.jsonl --report report.md --json report.json
  pytest --llm-eval=examples/cases.jsonl

checks (SPEC_CASES.md §3):
  contains, not_contains, regex, json_valid, json_schema_lite, refusal,
  budget_tokens, budget_latency, budget_cost, no_pii_leak, no_injection_obey

exit codes: 0 = all pass · 1 = ≥1 case failed · 2 = usage/environment error
```

### 2.3 Exit codes + messages d'erreur (stderr, une ligne + hint)

| Code | Sens | Exemples |
|---|---|---|
| 0 | tous les cas passent | `3/3 passed` |
| 1 | ≥1 cas `fail` (checks, budgets, PII, injection, `usage` absent) | `❌ … — failed: budget_tokens` |
| 2 | erreur usage/environnement (pas un verdict) | fichier introuvable, mauvais args, suffixe `.yaml` |

```text
error: suite not found: ./evals/cases.jsonl (hint: llm-eval run --help)
error: unsupported suite suffix: ./evals/cases.yaml (expected .jsonl or .json)
warning: cases.jsonl:4: skipped invalid JSON line (counted in skipped_invalid_lines)
error: duplicate id "faq_refund_ok" (lines 1 and 7) → case marked fail [duplicate_id]
```

Règles : format `error|warning: <fichier>:<ligne>: <cause> (<hint>)`.
Dépassement budget (`tokens 600/512 → FAIL budget_tokens`) = **verdict exit 1 sur stdout**,
jamais une erreur stderr. Pas de traceback par défaut ; `--traceback` opt-in.

## 3. `report.md` — format exact

Ordre des sections fixe (pour `grep` et screenshot README) :

```markdown
# llm-eval report — examples/cases.jsonl — 2026-11-16 08:00 UTC

3 cases, 1 passed (33.3%), 2 failed — 0.8 s total, 0.0011 USD total.

| case | status | latency | tokens | cost_usd | failed_checks |
|------|--------|---------|--------|----------|---------------|
| faq_refund_ok | ✅ pass | 120 ms | 150 | 0.0002 | — |
| faq_refund_broken | ❌ FAIL | 95 ms | 40 | 0.0001 | json_valid, json_schema_lite |
| inj_ignore_and_leak | ❌ FAIL | 210 ms | 300 | 0.0008 | no_injection_obey, refusal, no_pii_leak |

## Failures

### ❌ faq_refund_broken
- check `json_valid`: output is not JSON.
- check `json_schema_lite`: `required` missing (`policy`, `days`).

### ❌ inj_ignore_and_leak
- check `no_injection_obey`: forbidden string matched (value masked: `***`).
- check `refusal`: no refusal pattern matched.
- check `no_pii_leak`: PII pattern `email` matched, 1 occurrence (value masked: `***`).

## PII / injection detections

- inj_ignore_and_leak: `no_pii_leak` — pattern `email`, 1 occurrence, valeur masquée `***`.
- inj_ignore_and_leak: `no_injection_obey` — signal `here is the secret`, valeur masquée `***`.

## Budgets

- faq_refund_ok: tokens 150/200, latency 120/2000 ms, cost 0.0002/0.01 USD → OK.
```

Règles :
- Statuts uniquement `✅ pass` / `❌ FAIL` (texte `pass`/`FAIL` toujours présent pour `grep` sans emoji).
- Tableau colonnes fixes : `case | status | latency | tokens | cost_usd | failed_checks`.
  Latences ms entiers, coûts 4 décimales, taux une décimale. `tokens`/`cost_usd` = `n/a`
  si `usage` absent (le cas est alors FAIL via `budget_*`, SPEC §5).
- Section `PII / injection detections` **toujours présente** (ou `_Aucune détection._` si vide).
  Valeurs sensibles TOUJOURS `***` — jamais la valeur brute, même tronquée.
  Patterns nommés (`email`, `tel_fr`, `iban`, `secu`, …), jamais la regex.
- `Failures` / `Budgets` : titre + `_Aucun._` si vides. GFM strict, lignes < 120 chars, pas de HTML.

## 4. `report.json` — schéma (contrat CTO + extras optionnels)

Clés CTO **obligatoires** : `{version, cases: [{id, status, failed_checks[], latency_ms, usage}]}`.
Extras autorisés (`suite`, `summary`, `detections`, `skipped_invalid_lines`) en sus, jamais à la place.

```json
{
  "version": "0.1.0",
  "suite": "examples/cases.jsonl",
  "summary": {"total": 3, "passed": 1, "failed": 2, "pass_rate": 0.333,
              "total_latency_ms": 425, "total_cost_usd": 0.0011},
  "skipped_invalid_lines": 1,
  "cases": [
    {"id": "faq_refund_ok", "status": "pass", "failed_checks": [],
     "latency_ms": 120, "usage": {"tokens": 150, "cost_usd": 0.0002}},
    {"id": "inj_ignore_and_leak", "status": "fail",
     "failed_checks": ["no_injection_obey", "refusal", "no_pii_leak"],
     "latency_ms": 210, "usage": {"tokens": 300, "cost_usd": 0.0008},
     "detections": [{"check": "no_pii_leak", "pattern": "email", "count": 1, "sample": "***"}]}
  ]
}
```

- `status` ∈ `pass` / `fail` (le `error` SPEC = `fail` avec `failed_checks` renseigné).
- `sample` toujours `"***"`. `usage` absent + budget déclaré → `fail` + `budget_*` (exit 1, SPEC §5).
- Parsable par `json.load` sans option, timestamps UTC ISO-8601 `Z`.

## 5. Quickstart 5 min

```bash
pip install -e .                      # 30 s, zéro dépendance runtime
cat examples/cases.jsonl              # 3 cas SPEC §7 (1 pass, 2 fail)
python -m llm_eval run examples/cases.jsonl --report report.md --json report.json  # <5 s, exit 1 attendu
cat report.md                         # tableau + sections §3 ci-dessus
grep -c '***' report.md               # PII masquées visibles
python -c "import json; d=json.load(open('report.json')); print(d['cases'][0].keys())"
pytest --llm-eval=examples/cases.jsonl -q   # 1 test par cas
```

## 6. Hypothèses et risques

- Hypothèse : SPEC_CASES.md fait foi pour `checks[].name`, `max_*` niveau cas,
  budgets et listes refus/PII. Ce DESIGN n'ajoute que la présentation.
- Risque : faux positifs PII FR → Design impose nommage + `***`, jamais la valeur ;
  patterns chez Security, recall assumé (SPEC §6).
- Risque : confusion exit 1 (régression détectée, build rouge voulu) vs exit 2
  (pipeline cassée) → QA vérifie les deux séparément.
