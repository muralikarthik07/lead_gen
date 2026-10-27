# Design notes, assumptions and trade-offs

**Assumptions.** "Today" (`as_of`) is 2026-10-22 (the seed date). Leads are created Jan 1 to Aug 31 2026 so every lead has a full 14-day
scoring window and time to convert before `as_of`. All timestamps are naive UTC.

**Why a hidden outcome model.** If the label were a function of the score, evaluation would be circular. Conversion depends on hidden fit/intent/engagement
indices (different weights), hidden blockers (no_budget, competitor_incumbent, no_response: 22% of leads) and rep responsiveness (tenure). Blockers
also set the loss reason, which links labels to causes. Exactly N opportunities come from top-N ranking with Gumbel noise (Plackett-Luce), so volumes match the spec exactly while staying rule-based.

**Point-in-time scoring.** `extract_features(..., t)` ignores activity after `t`; the validator recomputes every stored score from source rows.
The post-conversion edge case is a *separate rescore row* (history is append-only), flagged by `scored_at > opportunity.created_at`.

**Consent as a timeline.** Per contact/channel periods with exclusive `effective_to`; a later lead may re-opt-in (new row). Leads capture the consent period in force at creation.

**Deduplication.** Contacts: same normalised email (lowercase, `+tag` stripped). Leads: same master contact + product within 90 days. Natural data is generated so
that no accidental duplicates occur (same-product leads for one person are ≥95 days apart); injected duplicates are the ground truth and the generator asserts dedupe(output) == truth. Duplicates are linked, never deleted.

**Routing.** Eligible = active rep covering (territory, product) in `RepCoverage`; least-loaded wins, ties by rep_id. Duplicates follow the master's rep and get no score/tasks.

**IDs.** Assigned after sorting by `created_at`, so counters are monotonic in time; never reused.

**Not done / possible extensions.** Right-censored outcomes, rep capacity limits, reassignment events, multiple opportunities per lead, a trained ML baseline.

## Web UI (LeadScope)
* **Why stdlib + vanilla JS:** the project's selling point is "clone, run, verify". A zero-install server (`http.server`) and a no-build SPA keep that promise; the UI also works offline.
* **Read-only by design:** the UI is a lens on exported files, so it cannot corrupt the dataset. The only write is `POST /api/revalidate`, which regenerates the validation/evaluation reports.
* **Ground truth is opt-in:** hidden by default and returned by the API only with `truth=1`, so the UI itself demonstrates the "no leakage" rule.
* **Live record checks are independent detectors:** the lead page recomputes score reproducibility, pre-conversion data, routing, consent and stage continuity for that one record; a test asserts these find exactly the ground-truth leads.
* **Security:** localhost bind, GET-only data endpoints, path-traversal-safe static serving, `nosniff`, and `esc()` on every dynamic value (verified in a browser test).
* **Bugs the UI review caught:** stale rule-set-v2 descriptions in `ScoreRule` (data bug, now validated), a navigation race where a slow page could overwrite a newer one, focus management that skipped the skip-link, clipped chart axes.
