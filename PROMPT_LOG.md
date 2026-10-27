# Prompt history

Tool: Claude (claude.ai). Prompts are given in order; "outcome" notes what I accepted or changed.

| # | My prompt | Outcome |
|---|---|---|
| 1 | Attached the YottaFlex submission guidelines (PDF) and the problem statement "Lead scoring, follow-ups, opportunity tracking" (synthetic data generation, 20k leads / 10k contacts / 5k companies / 3k opps, edge cases, validation, ground truth, reproducibility). Prompt text: **"build this"** | Claude built the whole repository: generator, validator, evaluator, CLI, 21 tests (now 73), README, data dictionary, design notes, starter data. It ran full-scale generation, validation, tests and reproducibility itself, tuned the win rate and score signal, and delivered a zip. |
| 2 | "`AI_USAGE.md` and `PROMPT_LOG.md` add it yourself as a student ... Push with meaningful commits ... act as me and do it" | Claude wrote this disclosure truthfully (heavy AI reliance; items I must personally verify left unchecked) and created a staged local git history. It cannot push to GitHub or know my 72-hour window; I do those myself. |

| 3 | "tell me what the entire project is about as I am 5 years old"; "how will the company see this"; "how to see it" | Plain-language explanation and instructions; Claude also published a read-only dashboard preview. |
| 4 | "please add a good frontend for this project and integrate it with the project, frontend should follow all the rules and guidelines and build a modern ui/ux frontend and test all the test cases and go through the project details once again and check everything again" | Claude built the integrated web UI + API (`python -m leadgen serve`), 52 additional tests (73 total, incl. real-browser), re-audited the project against the brief (`docs/REQUIREMENTS_TRACEABILITY.md`) and fixed the issues listed in `AI_USAGE.md`. |

> Before submitting I will paste any further prompts here, and attach the full exported chat transcript if the reviewers require it.
