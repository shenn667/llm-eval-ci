# QA Report — llm-eval-ci v0.1.0

Date: 2026-11-16 · QA: `qa` (task t_53762f8f, board llm-eval-ci)
Scope: PRODUCT_BRIEF.md §2, critères 1–7. Repo `/home/sh/ai_env/labs/llm-eval-ci` @ `1cf97f5` (+ untracked: DESIGN, README, examples, src, tests — non committés, voir remarque).
Environnement QA: /usr/bin/python3 = Python 3.14.10, pytest 9.2.0, coverage 7.x (outils dev uniquement).

Verdict global: **6/7 PASS, 1 FAIL (critère 6 — CI absente, relève ops). NO SHIP tant que le critère 6 n'est pas vert.**

Toutes les commandes ci-dessous ont été exécutées par QA sur la machine (pas de reprise d'un relevé antérieur). Note méthode : mesurer `$?` sans pipe (`| tail` écrase le code de sortie).

## Résultats par critère

### 1. Install offline + démo CLI < 5 s — PASS
- `pip install --no-index --no-deps --no-build-isolation .` en venv vierge (`--system-site-packages` pour setuptools, aucun téléchargement) → `Successfully installed llm-eval-ci-0.1.0`. Zéro dépendance runtime (`pyproject.toml`: `dependencies = []`).
- `/usr/bin/python3 -m llm_eval run examples/cases.jsonl` → **~0,2 s** (real 0m0,256s), < 5 s. Exit 1 — attendu : le fichier contient des cas rouges volontaires (cf. critère 4).
- Preuve offline : `tests/conftest.py` remplace `socket.socket` par une fonction qui lève (`network disabled in tests`) et les **146 tests passent quand même**. `grep` réseau (`urllib|requests|socket|http`) sur `cli.py/suite.py/__init__.py/models.py` → 0 hit ; `openai_compat` n'est importé par aucun chemin core (opt-in v0.2.0).

### 2. pytest ≥ 30 tests, 100 % sur checks/, plugin N cas = N tests — PASS
- `pytest -q` → **146 passed** (≥ 30), ~11 s, 0 failure.
- `coverage run -m pytest -q` + `coverage report --include="*/checks/*"` → **100 % sur les 13 fichiers de checks/** (333 statements, 0 miss).
- `pytest examples/basic.json --llm-eval=examples/basic.json --collect-only` → **4 tests** = 4 cas du fichier. `pytest --llm-eval=examples/cases.jsonl` → 149 tests = 146 + 3 cas (`faq_refund_ok`, `faq_refund_broken`, `inj_ignore_and_leak`), dont 2 failed = les cas rouges volontaires. Additivité exacte : N cas = N tests.

### 3. report.md / report.json (structure, totaux, masquage PII) — PASS
- `report.md` contient : taux de succès (`4 cases, 3 passed (75.0%), 1 failed`), tableau par cas (case, status, latency, tokens, cost_usd, failed_checks), section `PII / injection detections` avec valeurs `***`, section `Budgets`.
- `report.json` parsable : clés `{version, suite, summary, skipped_invalid_lines, cases}` ; chaque cas `{id, status, failed_checks[], latency_ms, usage{tokens, cost_usd}, details}` — champs §2.3 présents (sur-ensemble avec `details`/`detections`, acceptable).
- `grep -o "[...]@[...]"` sur les 4 rapports (md+json, suites cases + injection_pii) → **0 adresse** ; `***` présent (3 occurrences md + 3 json sur la suite injection). Fixtures : `FAKE`/`EXAMPLE`/`example.com` uniquement, aucun secret réel.

### 4. Exit 1 sur injection/PII — PASS
- `examples/cases.jsonl` → exit **1** (`inj_ignore_and_leak` fail : `no_injection_obey, refusal, no_pii_leak`).
- `examples/injection_pii.json` → exit **1** (`injection_obeyed` fail `no_injection_obey`, `pii_leaked_email` fail `no_pii_leak`) ; `examples/latency_cost.json` → exit **1**.
- Contraste : 1er cas de cases.jsonl isolé (suite 100 % verte) → exit **0**. Le gate 0/1 fonctionne dans les deux sens.

### 5. Budgets tokens/latence/coût/usage manquant — PASS
Relevé sur `latency_cost.json` : `within_budgets` pass ; `too_many_tokens` fail [`budget_tokens`] (500 > 100) ; `too_slow` fail [`budget_latency`] (300 ms > 50 ms) ; `too_expensive` fail [`budget_cost`] (0.05 > 0.01 USD) ; `usage_not_declared` fail [`budget_tokens`, `budget_cost`] (fail-closed, usage manquant).

### 6. CI GitHub Actions < 60 s + badge — FAIL
- **Aucun `.github/workflows/` dans le repo** : pas de lint/pytest/démo en CI, donc `<60 s` et matrice 3.10–3.14 non prouvées. Relève de la carte ops (pyproject + CI + tag), pas encore exécutée.
- Badge CI présent dans README mais URL `YOUR_ORG` placeholder — normal avant publication, à remplacer à la release.
- Élément favorable : démo CLI ~0,2 s et pytest ~11 s → budget 60 s crédible une fois le workflow écrit.

### 7. README (EN) — PASS avec 1 remarque mineure
- Install 30 s ✓ (stdlib-only, `pip install` + source), exemple 10 lignes `Suite` ✓, extrait de rapport md + schéma `report.json` ✓, section `Limitations & Roadmap` honnête avec justification « no LLM-judge » (coût, flaky, offline) ✓, badges CI/PyPI/Python/License ✓.
- **Doc bug mineur** : README ligne 55 (démo `examples/basic.json`) dit `echo $? # 0`, mais le comportement réel — et la `note` du cas `missing_keyword` lui-même — est **exit 1** (fail `contains` volontaire, le CLI échoue correctement). Corriger le `# 0` en `# 1`. Non bloquant pour le code, à fixer avant release.

## Remarques
- Le travail dev/design/spec (src, tests, examples, docs) est présent mais **non committé** (`git status` : tout en untracked, seul SPEC_CASES.md est committé). Recommandation ops : commiter avant de tagger v0.1.0.
- `basic.json` vs `cases.jsonl` utilisent deux schémas de checks différents (`{type,value,budgets}` vs `{name,params,max_*}`) — les deux sont chargés et testés, mais uniformiser éviterait une confusion (suggestion, non bloquant).

## Recommandation
**NO SHIP** : corriger le `# 0` README (1 ligne), commiter, puis carte ops (workflow CI + tag). Re-run QA ciblé : vérifier le workflow vert + relire le README corrigé.
