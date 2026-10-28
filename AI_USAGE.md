# AI Usage Disclosure

## 1. Summary

I used **Claude (Anthropic, claude.ai)** as my main development tool for this submission, and I used it heavily. Claude produced
the first draft of most of the code, tests and documentation. My role was to set the scope, decide what "done" had to mean,
push for verification instead of accepting output at face value, and take responsibility for what I submit.

I think the honest way to describe this is: **AI wrote, I directed and checked, and the project is built so that its correctness
can be demonstrated by running it rather than by trusting me or the model.**

## 2. Where AI accelerated my work

| Area | What Claude did |
|---|---|
| Architecture | Proposed a standard-library-only Python package: schema → generator → export → validator → evaluator → CLI, so a reviewer can clone and run it with no installs |
| Data generator | Entities, consent timelines, routing, point-in-time scoring, follow-up tasks, outcome model, stage histories, and injection of the five required edge cases |
| Validator / evaluator | Independent validator that re-derives scores, duplicates, statuses and consent from the exported CSVs; held-out (time-based) evaluation |
| Web UI | A local app (`python -m leadgen serve`) with a read-only JSON API and a single-page frontend |
| Tests | Unit, dataset, mutation, brief-compliance, API and real-browser end-to-end tests (73 in total) |
| Documentation | README, data dictionary (generated from the schema), design notes, requirements traceability matrix |

## 3. Where I relied on AI most heavily

- **The outcome model** (`_conversion` and `_make_opp` in `leadgen/generator.py`). Claude designed a hidden-factor model: conversion
  is the top-N of a hidden logit plus noise, so labels come from a documented rule and are not circular with the visible score.
  I rely on this design and I am able to explain its logic, but it is Claude's design, not mine.
- **The independent validator**, including the idea of "detectors" whose output must equal the ground-truth labels exactly.
- **The frontend code and visual design.**

## 4. How I verified the work (instead of trusting it)

I treated every AI output as unreviewed until something executable confirmed it:

- **Exact volumes and reconciliation:** the full run produces exactly 20,000 leads / 10,000 contacts / 5,000 companies / 3,000 opportunities and the conversion funnel reconciles.
- **Independent validation:** 97 invariant checks (keys, foreign keys, enums, dates, arithmetic, lifecycle, duplicates, consent, routing) plus 7 detectors that must match `ground_truth/anomalies.csv` exactly: no edge case missed, none extra.
- **Mutation tests:** the tests deliberately corrupt the data (orphan foreign key, duplicate key, tampered score, outbound contact after opt-out, bad enum, bad date) and assert the validator **fails**. This guards against checks that always pass.
- **Reproducibility:** generating twice with the same seed gives identical row counts and SHA-256 checksums for every file, at full scale.
- **Held-out evaluation:** scores are evaluated on later-created leads using labels from the separate ground-truth files; the evaluation uses only the initial score, not the leaky post-conversion rescores.
- **Brief compliance:** one test per requirement of the problem statement, also run against the full dataset.
- **UI:** exercised end to end in headless Chromium (every page, filters, sorting, search, theme, ground-truth toggle, mobile width, keyboard focus, HTML-escaping).

## 5. Decisions I directed

- That the deliverable must be **runnable and demonstrable**, not just code: hence the web UI, the starter dataset committed to the repo, and clear run steps.
- That verification (tests, a re-audit against the brief) must come before I submit, and that AI use be disclosed.
- That known gaps be stated openly (see section 7) rather than hidden.

## 6. Limitations and what I would do next

- Rates, amounts and reason mixes are plausible but **not calibrated to real business data**; they are synthetic by design.
- Every conversion outcome is fully known by the dataset's as-of date (no right-censoring), a simplification.
- Lead `status` is a derived snapshot that encodes outcomes, so it is excluded from model features (documented in the data dictionary).
- The brief's actors (support agent, analyst, administrator) are not modelled as separate user roles; the UI is a single read-only analyst view.
- Next steps: right-censored outcomes, rep capacity limits and reassignment events, and a trained ML baseline to compare against the transparent score.

## 7. Data provenance

No external or public datasets were used. All data is synthetic, generated from a fixed seed (20261022). Names are fictional, email
domains use the reserved `.example` TLD and phone numbers use the fictional `555` range. See `SOURCE_MANIFEST.md` in the generated output.