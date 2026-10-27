# Evaluation on held-out outcomes

Features: `LeadScore.trigger = 'initial'` only. Labels: `ground_truth/lead_labels.csv`. Split: temporal (train = leads created before the holdout cutoff, test = after). Duplicates excluded.

- Scored non-duplicate leads: 19,700 (train 14,638 / test 5,062)
- Conversion rate: overall 15.0%, test 15.7%
- **AUC held-out test: 0.7313** (train 0.7454)
- Top-decile precision (test): 43.7%, lift 2.78x
- AUC by score category (test): {'fit': 0.6728, 'intent': 0.6264, 'engagement': 0.6192}

## Conversion rate by tier

| tier | share of test | train rate | test rate |
|---|---|---|---|
| A | 8.2% | 49.8% | 45.3% |
| B | 20.0% | 25.6% | 25.5% |
| C | 45.7% | 11.7% | 12.4% |
| D | 26.2% | 4.3% | 4.7% |

## Score deciles (test)

| decile | n | score range | conversion rate |
|---|---|---|---|
| 1 | 506 | 0-18 | 3.2% |
| 2 | 506 | 18-22 | 6.5% |
| 3 | 506 | 22-26 | 6.9% |
| 4 | 506 | 26-29 | 7.1% |
| 5 | 507 | 29-32 | 10.8% |
| 6 | 506 | 32-35 | 16.8% |
| 7 | 506 | 35-39 | 14.4% |
| 8 | 506 | 39-44 | 21.7% |
| 9 | 506 | 44-52 | 25.5% |
| 10 | 507 | 52-87 | 44.0% |

## High-score non-converters

674 tier-A leads did not convert. By hidden blocker (ground truth only, invisible to the score): {'no_response': 65, 'none': 446, 'competitor_incumbent': 80, 'no_budget': 83}

## Leakage demonstration

AUC on test using the *latest* score (includes post-conversion rescores) = 0.7333 vs 0.7313 using the initial score. For the 60 injected leaked-score leads the mean score rises from 41.9 to 63.4.
