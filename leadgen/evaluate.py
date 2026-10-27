"""Evaluate the transparent score against HELD-OUT outcomes.

Features = LeadScore(trigger='initial') only. Labels come from ground_truth/lead_labels.csv (never from input tables).
Train/test split is temporal (leads created >= holdout_cutoff are the test set); tier->conversion mapping is learned on
train and applied to test. Duplicates are excluded (they are merged into their master lead).
"""
import json
import os
from collections import defaultdict

from .io_utils import load_tables, read_csv


def auc(pos, neg):
    if not pos or not neg:
        return float("nan")
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    ranks, i = {}, 0
    # average ranks for ties
    vals = [v for v, _ in allv]
    rank_sum = 0.0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[i]:
            j += 1
        avg = (i + j) / 2 + 1
        rank_sum += avg * sum(lab for _, lab in allv[i:j + 1])
        i = j + 1
    return (rank_sum - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def evaluate(out):
    T = load_tables(out)
    labels = {r["lead_id"]: r for r in read_csv(os.path.join(out, "ground_truth", "lead_labels.csv"))}
    anomalies = read_csv(os.path.join(out, "ground_truth", "anomalies.csv"))
    initial = {s["lead_id"]: s for s in T["LeadScore"] if s["trigger"] == "initial"}
    latest = {}
    for s in sorted(T["LeadScore"], key=lambda s: s["scored_at"]):
        latest[s["lead_id"]] = s
    rules = {r["rule_id"]: r for r in T["ScoreRule"]}
    cat_pts = defaultdict(lambda: defaultdict(int))
    for c in T["LeadScoreComponent"]:
        cat_pts[c["score_id"]][rules[c["rule_id"]]["category"]] += int(c["points"])

    rows = [dict(lead=l, score=int(initial[l]["total_score"]), tier=initial[l]["tier"], y=int(lab["converted"]), split=lab["holdout_split"],
                 blocker=lab["hidden_blocker"], score_latest=int(latest[l]["total_score"]), sid=initial[l]["score_id"])
            for l, lab in labels.items() if lab["is_duplicate"] == "0" and l in initial]
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]

    def A(rs, key="score"):
        return auc([r[key] for r in rs if r["y"]], [r[key] for r in rs if not r["y"]])

    rate = lambda rs: sum(r["y"] for r in rs) / len(rs) if rs else float("nan")
    tier_rate_train = {t: rate([r for r in train if r["tier"] == t]) for t in "ABCD"}
    tier_rate_test = {t: rate([r for r in test if r["tier"] == t]) for t in "ABCD"}
    k = max(1, len(test) // 10)
    top = sorted(test, key=lambda r: (-r["score"], r["lead"]))[:k]
    base = rate(test)
    by_cat = {}
    for cat in ("fit", "intent", "engagement"):
        for r in test:
            r[cat] = cat_pts[r["sid"]].get(cat, 0)
        by_cat[cat] = A(test, cat)
    deciles = []
    srt = sorted(test, key=lambda r: (r["score"], r["lead"]))
    for d in range(10):
        chunk = srt[d * len(srt) // 10:(d + 1) * len(srt) // 10]
        if chunk:
            deciles.append(dict(decile=d + 1, n=len(chunk), score_min=chunk[0]["score"], score_max=chunk[-1]["score"], conversion_rate=round(rate(chunk), 4)))
    hs = [r for r in rows if r["tier"] == "A" and not r["y"]]
    blk = defaultdict(int)
    for r in hs:
        blk[r["blocker"] or "none"] += 1
    leak_ids = {a["related_ids"].split(";")[0] for a in anomalies if a["issue_type"] == "score_uses_post_conversion_event"}
    leak = [r for r in rows if r["lead"] in leak_ids]
    rep = dict(
        n_scored_leads=len(rows), n_train=len(train), n_test=len(test), overall_conversion_rate=round(rate(rows), 4),
        test_conversion_rate=round(base, 4), auc_train=round(A(train), 4), auc_test_heldout=round(A(test), 4),
        auc_test_if_latest_score_used=round(A([dict(r, score=r["score_latest"]) for r in test]), 4),
        auc_by_score_category_test={k: round(v, 4) for k, v in by_cat.items()},
        tier_conversion_rate_train={k: round(v, 4) for k, v in tier_rate_train.items()},
        tier_conversion_rate_test={k: round(v, 4) for k, v in tier_rate_test.items()},
        tier_share_test={t: round(sum(r["tier"] == t for r in test) / len(test), 4) for t in "ABCD"},
        top_decile_precision_test=round(rate(top), 4), top_decile_lift_test=round(rate(top) / base, 2) if base else None,
        score_deciles_test=deciles, high_score_non_converters=len(hs), high_score_non_converters_by_hidden_blocker=dict(blk),
        leakage_demo=dict(leaked_rescore_leads=len(leak),
                          mean_initial_score=round(sum(r["score"] for r in leak) / len(leak), 1) if leak else None,
                          mean_leaked_latest_score=round(sum(r["score_latest"] for r in leak) / len(leak), 1) if leak else None,
                          note="'latest score' includes post-conversion events and must not be used for evaluation"))
    with open(os.path.join(out, "evaluation_report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    with open(os.path.join(out, "evaluation_report.md"), "w") as f:
        f.write(render_md(rep))
    return rep


def render_md(r):
    L = ["# Evaluation on held-out outcomes", "",
         "Features: `LeadScore.trigger = 'initial'` only. Labels: `ground_truth/lead_labels.csv`. Split: temporal (train = leads created before the holdout cutoff, test = after). Duplicates excluded.", "",
         f"- Scored non-duplicate leads: {r['n_scored_leads']:,} (train {r['n_train']:,} / test {r['n_test']:,})",
         f"- Conversion rate: overall {r['overall_conversion_rate']:.1%}, test {r['test_conversion_rate']:.1%}",
         f"- **AUC held-out test: {r['auc_test_heldout']}** (train {r['auc_train']})",
         f"- Top-decile precision (test): {r['top_decile_precision_test']:.1%}, lift {r['top_decile_lift_test']}x",
         f"- AUC by score category (test): {r['auc_by_score_category_test']}", "",
         "## Conversion rate by tier", "", "| tier | share of test | train rate | test rate |", "|---|---|---|---|"]
    L += [f"| {t} | {r['tier_share_test'][t]:.1%} | {r['tier_conversion_rate_train'][t]:.1%} | {r['tier_conversion_rate_test'][t]:.1%} |" for t in "ABCD"]
    L += ["", "## Score deciles (test)", "", "| decile | n | score range | conversion rate |", "|---|---|---|---|"]
    L += [f"| {d['decile']} | {d['n']} | {d['score_min']}-{d['score_max']} | {d['conversion_rate']:.1%} |" for d in r["score_deciles_test"]]
    L += ["", "## High-score non-converters", "",
          f"{r['high_score_non_converters']} tier-A leads did not convert. By hidden blocker (ground truth only, invisible to the score): {r['high_score_non_converters_by_hidden_blocker']}", "",
          "## Leakage demonstration", "",
          f"AUC on test using the *latest* score (includes post-conversion rescores) = {r['auc_test_if_latest_score_used']} vs {r['auc_test_heldout']} using the initial score. "
          f"For the {r['leakage_demo']['leaked_rescore_leads']} injected leaked-score leads the mean score rises from {r['leakage_demo']['mean_initial_score']} to {r['leakage_demo']['mean_leaked_latest_score']}."]
    return "\n".join(L) + "\n"
