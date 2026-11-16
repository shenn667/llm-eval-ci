# PRODUCT_BRIEF — llm-eval-ci v0.1.0

Outcome: un repo GitHub public qui fait dire à un recruteur AI Engineer « il sait shipper du testé, du CI et du mesurable ».
Promise: `pytest pour LLM/agents en CI` — CLI + lib Python + plugin pytest, stdlib-only (zéro dépendance runtime), offline-first, qui échoue un build CI quand une sortie LLM régresse.

## 1. Concept

- Usage: `llm-eval run ./evals/cases.jsonl --report ./report.md --json ./report.json` → exit ≠ 0 si un seuil casse. Lib: `from llm_eval import Suite, RegexCheck, JsonSchemaCheck`. CI: `pytest --llm-eval=./evals/cases.jsonl` (un test par cas, JUnit natif).
- Évaluations déterministes (offline, sans clé API, reproductibles): `contains` / `not_contains` / `regex` / `json_valid` / `json_schema_lite` (sous-ensemble maison: types requis, pas de `jsonschema`) / `refusal` + budgets `max_latency_ms` / `max_tokens` / `max_cost_usd` + détection prompt-injection (patterns) & PII (regex FR+EN: email, tél, IBAN, sécu simplifiée — valeurs toujours masquées `***` dans les rapports).
- Modèle BYO strictement local: interface `ModelFn(prompt) -> {"output": str, "usage": {"tokens": int, "cost_usd": float}}` + `StubModel` (map prompt→réponse depuis fixtures JSON) pour CI/démo. Aucun appel réseau dans le runtime.
- Contraintes: Python ≥3.10, stdlib seule au runtime (`argparse`, `json`, `re`, `time`), cases en JSON/JSONL uniquement (pas de YAML → pas de PyYAML), rapports Markdown + JSON, suite démo <5 s CPU, tests sans réseau (fixture bloque `socket`).

Non-objectifs v0.1.0: pas de juge-LLM, pas d'adapter provider réseau (OpenAI & co → v0.2.0 opt-in, hors core), pas de similarité sémantique/embeddings, pas de dashboard web, pas de stockage serveur, pas de streaming.

## 2. Critères testables v0.1.0 (Definition of Done)

1. `pip install -e .` puis `python -m llm_eval run examples/cases.jsonl --report report.md --json report.json` passe en <5 s sans réseau ni clé API.
2. `pytest`: ≥30 tests, 100 % sur `checks/` (via `coverage`), tous verts; `pytest --llm-eval=examples/cases.jsonl` collecte N tests = N cas.
3. `report.md` contient: taux de succès, tableau par cas (nom, statut, latence, coût), liste des PII/injections détectées (valeurs masquées); `report.json` parsable avec les mêmes champs (`{version, cases: [{id, status, failed_checks[], latency_ms, usage}]}`).
4. Un cas injection/PII volontairement mauvais fait échouer la commande (exit 1) — prouvé par un test CI; `grep` des vraies valeurs secrètes dans `report.*` → 0 hit (fixtures `FAKE`/`EXAMPLE` uniquement).
5. Budget: cas avec `usage.tokens > max_tokens` → fail `budget_tokens`; latence > `max_latency_ms` → fail `budget_latency`; usage non déclaré → fail.
6. CI GitHub Actions: `lint + pytest + démo CLI` verte sur push (<60 s, Python 3.10–3.14, sans secret) ; badge README.
7. README (EN): install 30 s, exemple 10 lignes, screenshot/extrait du rapport, section « limites » honnête (dont « pourquoi pas de LLM-juge »: coût, flaky, offline).

## 3. Architecture (cible)

```
src/llm_eval/  cli.py  suite.py  models.py (ModelFn, StubModel)  checks/ (regex, jsonschema_lite, latency, cost, injection, pii)  reporters/ (markdown, json)  pytest_plugin.py
examples/  cases.jsonl  fixtures_injection.json  fixtures_pii.json
tests/  test_checks_*  test_cli.py  test_reporters.py  test_plugin.py
.github/workflows/ci.yml
```

Suite charge JSONL → appelle ModelFn → exécute checks purs (fonctions `-> Verdict`) → reporters sérialisent. Aucun import réseau; aucun secret réel.

## 4. Plan d'exécution (frozen decisions pour les workers)

Décisions figées: package `llm-eval-ci`, import `llm_eval`, layout ci-dessus, Python ≥3.10, stdlib-only, checks nommés snake_case (`contains`, `not_contains`, `regex`, `json_valid`, `json_schema_lite`, `refusal`, `budget_tokens`, `budget_latency`, `budget_cost`, `no_pii_leak`, `no_injection_obey`), schéma `report.json` §2.3.

| Carte | Profil | Entrée → Sortie |
|---|---|---|
| PM — spec cas & budgets | `pm` | ce brief → `SPEC_CASES.md` (schéma exact ligne `cases.jsonl`, sémantique de chaque check, règles budgets). |
| Designer — DX CLI + rapports | `designer` | brief (+ SPEC si prête, sinon défauts §2.3) → `DESIGN.md` (format `report.md`: tableau, statuts ✅/❌, section PII/injection masquée; DX `--help`, messages d'erreur; quickstart 5 min). |
| Dev — core + CLI + plugin | `dev` | SPEC + DESIGN (défauts du brief si absents) → code + tests verts couvrant critères §2.1–2.5. |
| Security — audit injection/PII | `security` | code Dev (ou contrats du brief si Dev pas fini) → fixtures d'attaque, revue `injection.py`/`pii.py` (bypass, faux positifs FR/EN, ReDoS), preuve masquage §2.4. |
| QA — validation indépendante | `qa` | tout le dessus → `QA_REPORT_v0.1.0.md` (PASS/FAIL par critère §2 avec commandes et preuves, install venv vierge, CI <60 s). |
| Ops — CI + release | `ops` | QA vert → `pyproject.toml` (hatchling, MIT, entry point `llm-eval` + plugin), CI GitHub Actions, tag v0.1.0. Ne publie rien sans approbation founder. |

Ordre: PM → (Designer ∥ Dev) → Security → QA → Ops. Voir cartes kanban (dépendances `parents`) pour l'ordre d'exécution.
