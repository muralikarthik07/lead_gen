# Evaluation on held-out outcomes

Features: `LeadScore.trigger = 'initial'` only. Labels: `ground_truth/lead_labels.csv`. Split: temporal (train = leads created before the holdout cutoff, test = after). Duplicates excluded.

- Scored non-duplicate leads: 985 (train 746 / test 239)
- Conversion rate: overall 15.0%, test 11.7%
- **AUC held-out test: 0.6989** (train 0.6976)
- Top-decile precision (test): 34.8%, lift 2.97x
- AUC by score category (test): {'fit': 0.6754, 'intent': 0.635, 'engagement': 0.6197}

## Conversion rate by tier

| tier | share of test | train rate | test rate |
|---|---|---|---|
| A | 11.7% | 36.7% | 32.1% |
| B | 21.8% | 23.8% | 13.5% |
| C | 41.0% | 15.1% | 9.2% |
| D | 25.5% | 5.0% | 4.9% |

## Score deciles (test)

| decile | n | score range | conversion rate |
|---|---|---|---|
| 1 | 23 | 6-18 | 4.3% |
| 2 | 24 | 19-23 | 4.2% |
| 3 | 24 | 24-25 | 4.2% |
| 4 | 24 | 26-29 | 8.3% |
| 5 | 24 | 29-31 | 20.8% |
| 6 | 24 | 32-36 | 4.2% |
| 7 | 24 | 36-41 | 8.3% |
| 8 | 24 | 41-45 | 12.5% |
| 9 | 24 | 45-57 | 12.5% |
| 10 | 24 | 58-81 | 37.5% |

## High-score non-converters

50 tier-A leads did not convert. By hidden blocker (ground truth only, invisible to the score): {'no_budget': 8, 'none': 21, 'no_response': 10, 'competitor_incumbent': 11}

## Leakage demonstration

AUC on test using the *latest* score (includes post-conversion rescores) = 0.6994 vs 0.6989 using the initial score. For the 3 injected leaked-score leads the mean score rises from 54.7 to 74.7.
