# AI usage disclosure

## Summary (honest)
I used **Claude (Anthropic, claude.ai)** for this project and relied on it **heavily**. I gave it the task brief and the
submission guidelines with the single instruction "build this". Claude designed the architecture and wrote essentially all of the
first version of the code, tests and documentation in one session. I did not write the generator by hand.

## Where AI accelerated the work
- Architecture: stdlib-only Python package split into schema, scoring, generator, export, validator, evaluator and CLI.
- Generator: entities, consent timelines, routing, point-in-time scoring, task rules, the hidden outcome model, stage histories,
  and injection of the five required edge cases plus duplicate contacts/leads.
- Validator and evaluator, 21 pytest tests (including mutation tests), README, data dictionary and design notes.

## Where I relied on it most
- The outcome model (`_conversion`, `_make_opp` in `leadgen/generator.py`): hidden logit + Gumbel noise top-N selection. I use it as a
  documented rule, but I need to be able to explain the reasoning myself.
- The independent validator that recomputes scores, dedupe, consent and lead status from the exported CSVs.

## What was verified (by running things, not by trusting the text)
- `python -m leadgen generate` at full scale: exact volumes (20,000 leads / 10,000 contacts / 5,000 companies / 3,000 opportunities).
- Validation: 96/96 invariants pass and each of the 7 anomaly detectors equals `ground_truth/anomalies.csv` exactly.
- `python -m leadgen repro`: two same-seed runs give identical row counts and SHA-256 checksums.
- `pytest`: 21 passing tests; mutation tests prove the validator fails on corrupted FK/PK/score/consent/enum/date data.

## Problems found and fixed during the session
1. Win rate was ~65% of closed deals (unrealistic); recalibrated to ~37%.
2. Score signal was weak (AUC 0.67); outcome-model weights adjusted (held-out AUC ~0.73).
3. Validator crashed on corrupted data instead of reporting a failure; now returns FAIL, with a test.
4. Two validator checks were vacuous (always passed); replaced with real checks.
5. A mutation test for consent did not actually violate consent; rewritten so it does.

## My own review (to be completed by me before submitting: do not leave blank)
- [ ] I read `generator.py` end to end and can explain every phase.
- [ ] I re-ran `python -m pytest -q`, `python -m leadgen generate`, and `python -m leadgen repro --scale 1.0` on my own machine. Result: ________
- [ ] Things I changed or would change (parameters, rules, tier thresholds, anything I disagreed with): ________
- [ ] Known weaknesses I can discuss: outcomes are not right-censored; rates/amounts are plausible but not calibrated to real data;
      lead `status` encodes outcomes so it is excluded from features; names are random combinations with fictional `.example` domains.

## Data provenance
No external or public datasets were used. Everything is synthetic from a fixed seed. See `SOURCE_MANIFEST.md` in the generated output.
