# Requirements traceability

Every requirement from the problem brief and the submission guidelines, where it is implemented, and the evidence that it holds.
`tests/test_brief_compliance.py` encodes the data requirements and can be run against the full dataset (`make audit-full`).

| # | Requirement (brief) | Implementation | Evidence |
|---|---|---|---|
| 1 | Master data first (Company, Contact, Lead, Campaign, Activity), then dependent records with valid parent IDs | `generator.py` phases 1-6; IDs assigned after sorting by `created_at` | FK checks (14), `test_all_invariants_and_detectors_pass` |
| 2 | Business logic: company/contact masters; leads with source + consent; activity histories; transparent score features/weights; dedupe; territory/product routing; follow-up tasks; stage transitions and won/lost reasons | `generator.py`, `scoring.py`, `logic.py` | Dashboard, Lead detail, `docs/DESIGN.md` |
| 3 | State changes as explicit events; never overwrite history | `Consent` timeline, `LeadScore` events, `StageHistory`, effective-dated `ScoreRule` | `test_state_changes_are_events_not_overwrites`; lifecycle checks |
| 4 | Outcomes/labels from documented rules, not independent random assignment | Hidden-logit top-N model (`_conversion`), explicit win/loss and reason rules | `docs/DESIGN.md`; held-out AUC 0.73 (score is informative but not circular) |
| 5 | 11 core entities, PK for each, FK for each relationship, cardinality, optional relationships, effective dates, lifecycles, bridge tables, validated joins | `schema.py` (+ `RepCoverage`, `LeadScoreComponent`) | `docs/DATA_DICTIONARY.md`, Data dictionary page, FK checks, SQL `foreign_key_check` |
| 6 | ID conventions `CO-000001`, `CON-000001`, `LEAD-2026-000001`, `ACT-<lead-id>-001`, `OPP-2026-000001`, `TASK-<lead-id>-001`; zero-padded, immutable, consistent | `generator.py` | `test_id_conventions_exactly_as_specified`, contiguity checks |
| 7 | Step 1: data dictionary (type, required, allowed values, units, uniqueness, validation rule) | generated from `schema.py` | `schema/data_dictionary.md/json` |
| 8 | Step 4: 20,000 leads / 10,000 contacts / 5,000 companies / 3,000 opportunities; fixed seed 20261022; parameterised scale shared by starter and full | `config.py` `Config.scaled` | `LEADGEN_AUDIT_DIR=output/full` run: exact counts |
| 9 | Duplicates, opt-outs, stale leads, high-score non-converters | dedupe, consent timelines, status rules, hidden blockers | `test_required_data_characteristics_present` |
| 10 | Step 5 / edge cases: opted-out lead contacted; score uses post-conversion event; lead assigned outside territory; duplicate creates duplicate opportunity; stage history has gaps, each labelled with `issue_type` | `_inject_anomalies`, `_reps_and_routing`, `_conversion`, `_emit` | `ground_truth/anomalies.csv`; detectors match exactly (7/7); Edge cases page |
| 11 | Step 6: derived values computed from source records | statuses, tiers, bands, territory, `current_stage`, `closed_at`, campaign/task status | arithmetic/derived checks recompute every value |
| 12 | Step 7: separate ground truth, never leaked into features | `ground_truth/` directory; API hides it unless requested | `test_ground_truth_is_separate_and_not_leaked`, `test_truth_is_hidden_unless_requested` |
| 13 | Step 8: PK uniqueness, FK integrity, enums, date ordering, arithmetic reconciliation, lifecycle transitions, duplicate checks | `validate.py` (97 invariants + 7 detectors) | `validation_summary.md`; mutation tests |
| 14 | Step 9: CSV/JSON/SQL, README, schema/dictionary, generator command, fixed seed, source manifest, validation summary | `export.py`, `cli.py` | `test_all_export_formats_and_documentation_present`, SQL load test |
| 15 | Step 10: regenerate twice with the same seed, compare row counts/checksums | `python -m leadgen repro` | `docs/REPRODUCIBILITY_FULL_RUN.txt` (REPRODUCIBLE); `test_reproducible_same_seed_and_different_seed_differs` |
| 16 | Acceptance: score reproducible; consent and routing enforced; funnel reconciles; evaluation on held-out outcomes | validator categories `reproducibility`, `consent`, `routing`, `funnel`; `evaluate.py` temporal split | `test_acceptance_criteria`, Data quality + Scoring model pages |
| 17 | Realistic distributions, meaningful variation; normal, boundary, failure and exception coverage | tier mix 8/20/46/26 %, win rate 37 %, source/territory/size skews, stale 51 % | `docs/EVALUATION_FULL_RUN.md`, Dashboard |
| 18 | Lawful provenance | No external data; `.example` domains, `555` phones, fictional names | `SOURCE_MANIFEST.md` |
| 19 | Guidelines: runnable code with clear steps | stdlib only; `README.md` Quick start; `Makefile` | `python -m leadgen serve` works on a fresh clone |
| 20 | Guidelines: public repo, meaningful commits | staged git history | `git log` |
| 21 | Guidelines: transparent LLM use, prompt history | `AI_USAGE.md`, `PROMPT_LOG.md` | candidate must complete the review checklist |
| 22 | Guidelines: visible reasoning, assumptions, trade-offs, testing approach, limitations | `docs/DESIGN.md`, README "Limitations", this file | n/a |

## Known gaps (stated, not hidden)
* Brief actors "support agent, analyst, system administrator" are not modelled as users/roles; the UI is a single read-only analyst view.
* Outcomes are fully observed by the as-of date (no right-censoring).
* Ground truth is split into `anomalies.csv` and `lead_labels.csv` rather than a single `ground_truth.csv`.
* Rates, amounts and reason mixes are plausible but not calibrated to a real business.
