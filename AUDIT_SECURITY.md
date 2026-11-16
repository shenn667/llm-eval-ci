# AUDIT_SECURITY.md — Audit checks injection/PII/regex + reporters

- Date : 2026-11-16 · Auditeur : Security Agent (Hermes, profil `security`)
- Périmètre : `src/llm_eval/checks/` (notamment `security.py`, alias `injection.py`/`pii.py`/`regex.py`, `content.py`, `refusal.py`, `base.py`, `__init__.py`) et `src/llm_eval/reporters/` (`markdown.py`, `json_report.py`, `json.py`), plus `suite.py` (construction des rapports).
- Méthode : relecture ciblée + preuves d'exécution (probes de bypass, timing ReDoS, run e2e avec grep de fuites, `pytest tests/` : 146 passed).
- Verdict : **PASS — aucun bloquant (ni Critical ni High).** 1 finding Medium + 3 Low/Info, tous non bloquants pour la release.

## F1 — Medium · ReDoS sur les patterns `regex` fournis par la suite

- Fichier : `src/llm_eval/checks/content.py:36-50` (`check_regex`).
- Constat : `re.compile(pattern)` puis `rx.search(output)` sans garde-fou (pas de timeout — `re` n'en a pas —, pas de lint de quantificateurs imbriqués, pas de plafond de taille d'`output`). Un pattern malicieux ou accidentel (ex. `(a+)+$`) fige le runner.
- Preuve : `(a+)+$` contre `"a"*30+"!"` n'a pas terminé en 20 s (sous-processus tué par timeout). À l'inverse, les 5 regex PII internes sont linéaires (pire cas mesuré : email 42,7 ms sur entrée adverse de 2 000 car.).
- Impact : hang du CI local (pire qu'un crash : pas de fail-fast). Exploitabilité faible (suites rédigées par l'équipe, pas par l'attaquant ; le modèle ne contrôle que `output`, pas `pattern`), d'où Medium et non High.
- Remédiation (owner : dev) : 1) à terme, exécuter `rx.search` avec timeout (thread + fail-closed du check) ; 2) à court terme, refuser/avertir les motifs à quantificateurs imbriqués au chargement de la suite ; 3) plafonner la taille d'`output` soumise au regex. Re-test : relancer la preuve `(a+)+$` → doit fail-fast au lieu de hang.

## F2 — Low · Reporter JSON live sans scrub à la frontière (défense en profondeur)

- Fichiers : `src/llm_eval/reporters/json_report.py:46-51` (copie `detections`/`details` verbatim) vs `src/llm_eval/reporters/json.py:15-23` (`_scrub_detections` qui force `sample: "***"`, **code mort** — rien ne l'importe, `__init__.py` câble `json_report`). `mask_pii()` (`security.py:41`) n'est appelée nulle part dans le runtime.
- Constat : aujourd'hui SÛR — les checks émettent `sample: "***"` et les `details` ne contiennent aucune valeur brute (vérifié e2e, voir § Vérifié PASS). Mais aucune barrière au niveau reporter : le premier futur check qui mettrait une valeur brute en `sample`/`detail` fuirait telle quelle dans `report.json`.
- Remédiation (owner : dev) : appliquer le scrub dans le chemin live (`json_report.py` : réutiliser `_scrub_detections` + `mask_pii()` sur les `details`), ou supprimer le module mort `json.py` pour lever l'ambiguïté ; ajouter un test « aucun pattern PII brut dans report.json/md » sur une sortie fuitée. Re-test : suite e2e + grep (cf. § PASS).

## F3 — Info · `no_injection_obey` : bypass triviaux, par design SPEC

- Fichier : `src/llm_eval/checks/security.py:86-103` (sous-chaîne exacte, insensible à la casse, contre la liste `forbidden` rédigée par l'auteur du cas).
- Preuves (avec `forbidden=["here is the secret"]`) : `"HERE\u200b IS THE SECRET"` (zero-width), `"H E R E  I S  T H E  S E C R E T"` (espacé), `"here is the $ecret"`, paraphrase `"voici le secret demandé"` → tous PASS (non détectés). Seul le libellé exact est détecté.
- Statut : conforme à SPEC_CASES.md §3 #11 (« le runner ne devine rien ») — pas un bug, risque résiduel documenté : le check détecte des signaux connus, pas l'obéissance sémantique. Ne pas présenter `no_injection_obey` comme une garde anti-jailbreak.
- Piste non bloquante (owner : cto/pm, décision spec) : normaliser avant comparaison (supprimer caractères de format/zero-width, compacter les espaces). Ne pas élargir sans décision spec (faux positifs).

## F4 — Low · Couverture PII : angles morts vérifiés (hors liste figée SPEC §6)

- Fichier : `src/llm_eval/checks/security.py:13-19` (`PII_PATTERNS`).
- Preuves : IBAN minuscule (`fr76 ...`) **non détecté** (`[A-Z]{2}` sensible à la casse — les sorties modèle sont souvent en minuscules) ; carte bancaire 16 chiffres (`4539 1488 0343 6467`) non détectée (aucun pattern CB) ; clé type `sk-live-...` non détectée. Par ailleurs l'IBAN FR déclenche aussi `tel_fr` (chevauchement — gonfle les compteurs, cosmétique).
- Statut : conforme — SPEC §6 fige exactement ces 5 familles. Recommandation minimale : compiler l'IBAN en insensible à la casse (coût nul, gain réel) et documenter le périmètre (pas de CB, pas de secrets génériques) dans SPEC/README pour éviter tout faux sentiment de sécurité. Extensions CB/sécu étendue : décision spec (owner : pm/cto), pas un défaut.

## F5 — Low · `refusal` : variante manquée + faux positifs par sous-chaîne

- Fichier : `src/llm_eval/checks/refusal.py:10-20`.
- Preuves : `"I cant help with that"` (sans apostrophe) → non détecté ; à l'inverse tout `"As an AI, ..."` (ex. `"As an AI, here is the secret"`) compte comme refus PASS — un output qui *fuit* peut valider le check `refusal`.
- Impact : qualité d'éval, pas de fuite. Piste : normalisation insensible à l'apostrophe (`cant`/`can't`/`cannot`) et, à terme, ancrage sur templates connus plutôt que sous-chaîne nue (owner : dev, décision spec).

## Vérifié PASS (preuves)

1. Masquage e2e : suite avec `HERE IS THE SECRET + admin@example.com + 06 12 34 56 78 + sécu` → `report.md` et `report.json` : **0 occurrence brute** (grep), tous les `sample` à `"***"`, détails sans valeur (`"PII pattern(s) matched: email, secu, tel_fr (values masked)"`). `CaseResult` ne stocke jamais l'`output` brut — rien d'autre ne peut fuir par ce chemin.
2. Fixtures/constantes sans secret réel : `examples/*.json`, `DEFAULT_INJECTION_SIGNALS`, `EXAMPLES_INJECTION_DEFAULTS` — vocabulaire fixture uniquement (`hunter2-FAKE`, domaines `example.com`) ; le chemin live exclut d'ailleurs `hunter2` des défauts (cf. commentaire `suite.py:26-39`).
3. `pytest tests/` : **146 passed**.
4. Aucune exécution réseau, aucun secret redressé, aucune charge utile conservée (audit lecture seule + stubs locaux).

## Recommandations prioritaires (non bloquantes)

1. (F1, dev) Garde-fou ReDoS sur `check_regex` — le seul finding Medium.
2. (F2, dev) Scrub à la frontière reporter + test anti-fuite dans `test_reporters.py`.
3. (F4, dev, 1 ligne) IBAN insensible à la casse.
4. (F3/F5, cto/pm) Documenter les limites sémantiques (`no_injection_obey`, `refusal`) dans SPEC/README.
