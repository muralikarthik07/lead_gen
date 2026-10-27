"""Independent validation: reads ONLY the exported CSVs (never generator objects) and re-derives everything.

Two kinds of checks:
  * invariants  - must have zero violations in the whole dataset (PK/FK/enums/dates/arithmetic/lifecycle/reproducibility)
  * detectors   - find the deliberately injected edge cases; their output must equal ground_truth/anomalies.csv exactly
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta

from . import reference as ref
from . import scoring
from .io_utils import load_tables, read_csv
from .logic import ConsentIndex, dedupe_contacts, dedupe_leads, derive_lead_status
from .schema import TABLES, SCHEMA
from .util import fmt, parse

FORBIDDEN_FEATURE_COLUMNS = {"issue_type", "ground_truth", "hidden_blocker", "converted", "eventual_outcome", "holdout_split",
                             "is_anomaly", "is_high_score_non_converter", "anomaly_id"}


def _ok_type(v, typ):
    try:
        if typ == "integer":
            int(v)
        elif typ == "real":
            float(v)
        elif typ == "datetime":
            parse(v)
        elif typ == "date":
            datetime.strptime(v, "%Y-%m-%d")
        elif typ == "bool":
            assert v in ("0", "1")
    except Exception:
        return False
    return True


def validate(out):
    try:
        return _validate(out)
    except (KeyError, ValueError, TypeError) as e:   # corrupted data that breaks a lookup is itself a failure
        summary = dict(overall="FAIL", invariants_passed=0, invariants_total=1, detectors_matching_ground_truth=0, detectors_total=0,
                       funnel={}, row_counts={}, detectors=[], checks=[dict(name=f"validator aborted on structurally invalid data: {e!r}",
                       category="schema", status="FAIL", violations=1, sample=[], note="")])
        with open(os.path.join(out, "validation_summary.json"), "w") as f:
            json.dump(summary, f, indent=1)
        return summary


def _validate(out):
    meta = json.load(open(os.path.join(out, "run_metadata.json")))
    cfg = meta["config"]
    as_of = cfg["as_of"]
    T = load_tables(out)
    gt = read_csv(os.path.join(out, "ground_truth", "anomalies.csv"))
    checks = []

    def add(name, cat, bad, note=""):
        bad = list(bad)
        checks.append(dict(name=name, category=cat, status="PASS" if not bad else "FAIL", violations=len(bad), sample=bad[:5], note=note))

    # ---------------------------------------------------------------- structure
    for t in TABLES:
        rows = T[t.name]
        add(f"{t.name}: primary key unique", "primary_keys", _dups(rows, t.pk))
        for c in t.cols:
            if c.unique and c.name not in t.pk:
                add(f"{t.name}.{c.name}: unique", "primary_keys", _dups(rows, (c.name,)))
        bad = []
        for r in rows:
            for c in t.cols:
                v = r[c.name]
                if v == "":
                    if c.required:
                        bad.append(f"{r[t.pk[0]]}.{c.name} missing")
                    continue
                if not _ok_type(v, c.type):
                    bad.append(f"{r[t.pk[0]]}.{c.name}={v!r} bad {c.type}")
                elif c.allowed and v not in [str(a) for a in c.allowed]:
                    bad.append(f"{r[t.pk[0]]}.{c.name}={v!r} not allowed")
                elif c.pattern and not re.match(c.pattern, v):
                    bad.append(f"{r[t.pk[0]]}.{c.name}={v!r} bad pattern")
        add(f"{t.name}: required/type/enum/pattern", "schema", bad)
    # contiguous zero-padded counters for master IDs
    for tbl, col, pre, w in (("Company", "company_id", "CO-", 6), ("Contact", "contact_id", "CON-", 6), ("Consent", "consent_id", "CNS-", 6)):
        want = [f"{pre}{i:0{w}d}" for i in range(1, len(T[tbl]) + 1)]
        add(f"{tbl}: IDs contiguous & zero-padded", "primary_keys", [] if [r[col] for r in T[tbl]] == want else ["gap or disorder"])

    # ------------------------------------------------------------ foreign keys
    ids = {t.name: {r[t.pk[0]] for r in T[t.name]} if len(t.pk) == 1 else None for t in TABLES}
    for t in TABLES:
        for c in t.cols:
            if c.fk:
                ptab, pcol = c.fk.split(".")
                pset = {r[pcol] for r in T[ptab]}
                add(f"FK {t.name}.{c.name} -> {c.fk}", "foreign_keys", [r[c.name] for r in T[t.name] if r[c.name] and r[c.name] not in pset])
    cov_pk = {(r["rep_id"], r["territory"], r["product"]) for r in T["RepCoverage"]}

    # ------------------------------------------------------------ lookups
    C = {r["company_id"]: r for r in T["Company"]}
    CON = {r["contact_id"]: r for r in T["Contact"]}
    CAMP = {r["campaign_id"]: r for r in T["Campaign"]}
    REP = {r["rep_id"]: r for r in T["SalesRep"]}
    L = {r["lead_id"]: r for r in T["Lead"]}
    OPP = {r["opportunity_id"]: r for r in T["Opportunity"]}
    OPP_BY_LEAD = {r["lead_id"]: r for r in T["Opportunity"]}
    TASK = {r["task_id"]: r for r in T["Task"]}
    acts_by_lead = defaultdict(list)
    for a in T["Activity"]:
        acts_by_lead[a["lead_id"]].append(a)
    cidx = ConsentIndex(T["Consent"])
    sh_by_opp = defaultdict(list)
    for r in T["StageHistory"]:
        sh_by_opp[r["opportunity_id"]].append(r)
    for v in sh_by_opp.values():
        v.sort(key=lambda r: int(r["seq"]))

    # ------------------------------------------------------ date ordering
    add("Contact.created_at >= Company.created_at", "date_ordering", [r["contact_id"] for r in T["Contact"] if r["created_at"] < C[r["company_id"]]["created_at"]])
    first = {}
    for l in T["Lead"]:
        first[l["contact_id"]] = min(first.get(l["contact_id"], l["created_at"]), l["created_at"])
    add("Contact.created_at == created_at of the contact's first lead; every contact has a lead", "date_ordering",
        [c for c, r in CON.items() if first.get(c) != r["created_at"]])
    add("Lead.company_id == Contact.company_id", "referential_semantics", [r["lead_id"] for r in T["Lead"] if r["company_id"] != CON[r["contact_id"]]["company_id"]])
    add("Lead.territory == Company.territory", "derived_values", [r["lead_id"] for r in T["Lead"] if r["territory"] != C[r["company_id"]]["territory"]])
    add("Lead within campaign window and channel == source", "date_ordering", [
        r["lead_id"] for r in T["Lead"] if r["campaign_id"] and not (CAMP[r["campaign_id"]]["start_date"] <= r["created_at"][:10] <= CAMP[r["campaign_id"]]["end_date"]
                                                                       and CAMP[r["campaign_id"]]["channel"] == r["source"])])
    add("Lead.routed_at >= created_at", "date_ordering", [r["lead_id"] for r in T["Lead"] if r["routed_at"] and r["routed_at"] < r["created_at"]])
    add("Activity.occurred_at >= Lead.created_at", "date_ordering", [a["activity_id"] for a in T["Activity"] if a["occurred_at"] < L[a["lead_id"]]["created_at"]])
    add("Activity direction/channel match type", "schema", [a["activity_id"] for a in T["Activity"]
                                                           if ref.ACTIVITY_TYPES[a["activity_type"]][:2] != (a["direction"], a["channel"])])
    add("Activity IDs sequential & time-ordered per lead", "primary_keys", [
        l for l, acts in acts_by_lead.items()
        if [a["activity_id"] for a in acts] != [f"ACT-{l}-{i:03d}" for i in range(1, len(acts) + 1)]
        or [a["occurred_at"] for a in acts] != sorted(a["occurred_at"] for a in acts)])
    add("Task due >= created, completed >= created, status/cancel_reason consistent", "date_ordering", [
        t["task_id"] for t in T["Task"]
        if t["due_at"] < t["created_at"] or (t["completed_at"] and t["completed_at"] < t["created_at"])
        or (t["status"] == "completed") != bool(t["completed_at"]) or (t["status"] == "cancelled") != bool(t["cancel_reason"])
        or (t["status"] == "overdue" and t["due_at"] >= as_of) or t["rep_id"] != L[t["lead_id"]]["assigned_rep_id"]])
    sc0 = {r["lead_id"]: r for r in T["LeadScore"] if r["trigger"] == "initial"}
    add("Opportunity.created_at > initial score time; >= lead.created_at", "date_ordering", [
        o["opportunity_id"] for o in T["Opportunity"] if o["created_at"] < L[o["lead_id"]]["created_at"]
        or (o["lead_id"] in sc0 and o["created_at"] <= sc0[o["lead_id"]]["scored_at"])])
    add("Opportunity company/contact/rep consistent with lead", "referential_semantics", [
        o["opportunity_id"] for o in T["Opportunity"] if o["company_id"] != L[o["lead_id"]]["company_id"]
        or o["contact_id"] != L[o["lead_id"]]["contact_id"] or o["rep_id"] != L[o["lead_id"]]["assigned_rep_id"]
        or o["product"] != L[o["lead_id"]]["product_interest"]])
    bad = []
    for c in T["Consent"]:
        if c["effective_to"] and c["effective_to"] <= c["effective_from"]:
            bad.append(c["consent_id"])
    per = defaultdict(list)
    for c in T["Consent"]:
        per[(c["contact_id"], c["channel"])].append(c)
    for k, v in per.items():
        v.sort(key=lambda x: x["effective_from"])
        for a, b in zip(v, v[1:]):
            if a["effective_to"] != b["effective_from"] or a["status"] == b["status"]:
                bad.append(f"{k}")
        if v[-1]["effective_to"]:
            bad.append(f"{k} last period closed")
    add("Consent timelines contiguous, non-overlapping, alternating", "lifecycle", bad)
    add("Lead.consent_id is the email consent period in force at created_at", "referential_semantics", [
        r["lead_id"] for r in T["Lead"] if (cidx.period_at(r["contact_id"], "email", r["created_at"]) or {}).get("consent_id") != r["consent_id"]])
    add("Campaign dates ordered", "date_ordering", [r["campaign_id"] for r in T["Campaign"] if r["end_date"] < r["start_date"]])

    # ---------------------------------------------------- arithmetic / derived
    add("Company.employee_band == band_of(employee_count)", "derived_values", [r["company_id"] for r in T["Company"] if ref.band_of(int(r["employee_count"])) != r["employee_band"]])
    add("Company.territory == territory(country)", "derived_values", [r["company_id"] for r in T["Company"] if ref.COUNTRIES[r["country"]][0] != r["territory"]])
    add("Company revenue / amounts positive", "derived_values", [r["company_id"] for r in T["Company"] if float(r["annual_revenue_usd"]) <= 0]
        + [r["opportunity_id"] for r in T["Opportunity"] if float(r["amount_usd"]) <= 0])
    add("ScoreRule description states its own points/cap (per-unit rules)", "derived_values", [
        r["rule_id"] for r in T["ScoreRule"] if r["operator"] == "per_unit" and f"({r['points']} each, max {r['cap_units']})" not in r["description"]])
    comps_by_score = defaultdict(list)
    for r in T["LeadScoreComponent"]:
        comps_by_score[r["score_id"]].append(r)
    rules = {r["rule_id"]: r for r in T["ScoreRule"]}
    add("Component points == rule.points x units", "arithmetic", [
        f"{c['score_id']}/{c['rule_id']}" for c in T["LeadScoreComponent"] if int(c["points"]) != int(rules[c["rule_id"]]["points"]) * int(c["units"])])
    add("LeadScore raw == sum(components); total == clamp(raw); tier from thresholds", "arithmetic", [
        s["score_id"] for s in T["LeadScore"]
        if int(s["raw_score"]) != sum(int(c["points"]) for c in comps_by_score[s["score_id"]])
        or int(s["total_score"]) != max(0, min(100, int(s["raw_score"]))) or s["tier"] != scoring.tier_for(int(s["total_score"]))])
    bad = []
    for s in T["LeadScore"]:                                     # SCORE REPRODUCIBILITY: recompute from source rows
        l = L[s["lead_id"]]
        feat = scoring.extract_features(C[l["company_id"]], CON[l["contact_id"]], l, acts_by_lead[l["lead_id"]], s["scored_at"])
        res = scoring.score_lead(feat, T["ScoreRule"], s["scored_at"])
        got = sorted((c["rule_id"], int(c["units"]), int(c["points"])) for c in comps_by_score[s["score_id"]])
        if (res["raw"], res["rule_version"], sorted(res["components"])) != (int(s["raw_score"]), int(s["rule_version"]), got):
            bad.append(s["score_id"])
    add("Score is reproducible from source rows (features, rule version, components)", "reproducibility", bad)
    add("Every non-duplicate lead has exactly one initial score; duplicates have none", "derived_values", [
        l for l, r in L.items() if (r["duplicate_of_lead_id"] == "") != (l in sc0)])
    # opportunities vs stage history
    bad_cur, bad_closed = [], []
    for oid, o in OPP.items():
        h = sh_by_opp[oid]
        if not h:
            bad_cur.append(oid)
            continue
        last = h[-1]["to_stage"]
        closed = last in ("Closed Won", "Closed Lost")
        if o["current_stage"] != last or o["status"] != ("won" if last == "Closed Won" else "lost" if last == "Closed Lost" else "open"):
            bad_cur.append(oid)
        if bool(o["closed_at"]) != closed or (closed and o["closed_at"] != h[-1]["changed_at"]) or bool(o["outcome_reason"]) != closed:
            bad_closed.append(oid)
    add("Opportunity.current_stage/status == latest StageHistory", "lifecycle", bad_cur)
    add("Opportunity closed_at/outcome_reason consistent with closing event", "lifecycle", bad_closed)
    bad = []
    for oid, h in sh_by_opp.items():
        if h[0]["from_stage"] or h[0]["to_stage"] != "Qualification" or h[0]["changed_at"] != OPP[oid]["created_at"]:
            bad.append(oid)
        for r in h:
            if r["to_stage"] not in ref.STAGE_EDGES.get(r["from_stage"] or None, set()):
                bad.append(r["stage_history_id"])
        if [r["changed_at"] for r in h] != sorted(r["changed_at"] for r in h):
            bad.append(oid)
    add("StageHistory: valid transitions, starts at Qualification, times non-decreasing", "lifecycle", bad)

    # ------------------------------------------------------------ dedupe
    cd = dedupe_contacts(T["Contact"])
    ld = dedupe_leads(T["Lead"], cd, cfg["dedupe_window_days"])
    add("Dedupe recomputed == stored duplicate_of_contact_id / duplicate_of_lead_id", "duplicates",
        [c for c, r in CON.items() if cd.get(c, "") != r["duplicate_of_contact_id"]] + [l for l, r in L.items() if ld.get(l, "") != r["duplicate_of_lead_id"]])
    from .logic import normalize_email
    add("No two master contacts share a normalised email", "duplicates",
        _dups([{"k": normalize_email(r["email"])} for r in T["Contact"] if not r["duplicate_of_contact_id"]], ("k",)))
    add("Duplicate leads follow master rep", "duplicates", [l for l, r in L.items() if r["duplicate_of_lead_id"] and r["assigned_rep_id"] != L[r["duplicate_of_lead_id"]]["assigned_rep_id"]
                                                          and r["routing_rule"] != "duplicate_follows_master"])

    # ----------------------------------------------- lead status (derived)
    tier = {l: s["tier"] for l, s in sc0.items()}
    done = {t["lead_id"] for t in T["Task"] if t["status"] == "completed"}
    bad = []
    for l, r in L.items():
        acts = acts_by_lead[l]
        want = derive_lead_status(bool(r["duplicate_of_lead_id"]), l in OPP_BY_LEAD, cidx.opted_out_everywhere(r["contact_id"], as_of),
                                  max(a["occurred_at"] for a in acts), as_of, cfg["stale_days"], tier.get(l), l in done, any(a["rep_id"] for a in acts))
        if want != r["status"]:
            bad.append(l)
    add("Lead.status recomputed from source records", "derived_values", bad)

    # ------------------------ business-rule invariants that hold for ALL rows
    add("Completed/open non-cancelled tasks had consent for their channel at due time", "consent", [
        t["task_id"] for t in T["Task"] if t["status"] != "cancelled"
        and not cidx.has_consent(L[t["lead_id"]]["contact_id"], {"call": "phone", "email": "email", "demo": "email"}[t["task_type"]], t["due_at"])])
    add("Assigned rep is active", "routing", [l for l, r in L.items() if r["assigned_rep_id"] and REP[r["assigned_rep_id"]]["is_active"] != "1"
                                                and not r["duplicate_of_lead_id"]])
    add("Every lead has a rep, routed_at and a form_submit activity", "routing", [
        l for l, r in L.items() if not r["assigned_rep_id"] or not r["routed_at"] or not any(a["activity_type"] == "form_submit" for a in acts_by_lead[l])])
    add("Initial score uses only pre-conversion data (initial scored_at < opp.created_at)", "leakage", [
        s["score_id"] for s in sc0.values() if s["lead_id"] in OPP_BY_LEAD and s["scored_at"] >= OPP_BY_LEAD[s["lead_id"]]["created_at"]])
    leaked = [c for t in TABLES for c in t.col_names if c in FORBIDDEN_FEATURE_COLUMNS]
    add("No ground-truth/label columns in input tables", "leakage", leaked)
    add("Ground truth lives in separate files", "leakage", [] if os.path.exists(os.path.join(out, "ground_truth", "anomalies.csv")) else ["missing"])

    # ---------------------------------------------- funnel reconciliation
    n_lead, n_dup = len(L), sum(1 for r in L.values() if r["duplicate_of_lead_id"])
    n_opp = len(OPP)
    n_opp_master = sum(1 for o in OPP.values() if not L[o["lead_id"]]["duplicate_of_lead_id"])
    st = defaultdict(int)
    for o in OPP.values():
        st[o["status"]] += 1
    funnel = dict(leads=n_lead, duplicate_leads=n_dup, master_leads=n_lead - n_dup, scored_leads=len(sc0),
                  leads_with_tasks=len({t["lead_id"] for t in T["Task"]}), leads_with_completed_task=len(done),
                  opportunities=n_opp, opps_from_master_leads=n_opp_master, opps_from_duplicate_leads=n_opp - n_opp_master,
                  open=st["open"], won=st["won"], lost=st["lost"], leads_status_converted=sum(1 for r in L.values() if r["status"] == "Converted"))
    add("Funnel: master+duplicate leads == leads; scored == master leads", "funnel", [] if n_lead - n_dup == len(sc0) else ["scored != master"])
    add("Funnel: opps from master + from duplicates == opportunities; open+won+lost == opportunities", "funnel",
        [] if (n_opp_master + (n_opp - n_opp_master) == n_opp and st["open"] + st["won"] + st["lost"] == n_opp and len(sh_by_opp) == n_opp) else ["mismatch"])
    add("Funnel: leads with status Converted == opportunities from master leads", "funnel", [] if funnel["leads_status_converted"] == n_opp_master else ["mismatch"])
    add("Volumes match configuration", "funnel", [k for k, a, b in (("leads", n_lead, cfg["n_leads"]), ("contacts", len(CON), cfg["n_contacts"]),
                                                                       ("companies", len(C), cfg["n_companies"]), ("opportunities", n_opp, cfg["n_opportunities"])) if a != b])

    # ------------------------------------------------------- detectors vs GT
    det = {}
    det["opted_out_lead_contacted"] = {a["activity_id"] for l, acts in acts_by_lead.items() for a in acts
                                         if ref.ACTIVITY_TYPES[a["activity_type"]][2]
                                         and not cidx.has_consent(L[l]["contact_id"], ref.ACTIVITY_TYPES[a["activity_type"]][2], a["occurred_at"])}
    det["score_uses_post_conversion_event"] = {s["score_id"] for s in T["LeadScore"] if s["lead_id"] in OPP_BY_LEAD and s["scored_at"] > OPP_BY_LEAD[s["lead_id"]]["created_at"]}
    det["lead_assigned_outside_territory"] = {l for l, r in L.items() if r["assigned_rep_id"] and (r["assigned_rep_id"], r["territory"], r["product_interest"]) not in cov_pk}
    det["duplicate_creates_duplicate_opportunity"] = {o["opportunity_id"] for o in OPP.values() if L[o["lead_id"]]["duplicate_of_lead_id"]}
    gaps = set()
    for oid, h in sh_by_opp.items():
        if [int(r["seq"]) for r in h] != list(range(1, len(h) + 1)) or any(b["from_stage"] != a["to_stage"] for a, b in zip(h, h[1:])):
            gaps.add(oid)
    det["stage_history_gap"] = gaps
    det["duplicate_contact"] = set(cd)
    det["duplicate_lead"] = set(ld)
    exp = defaultdict(set)
    for g in gt:
        exp[g["issue_type"]].add(g["record_id"])
    detectors = []
    for k in sorted(set(det) | set(exp)):
        e, d = exp[k], det.get(k, set())
        detectors.append(dict(issue_type=k, expected=len(e), detected=len(d), missing=len(e - d), unexpected=len(d - e),
                              status="PASS" if e == d else "FAIL", sample_unexpected=sorted(d - e)[:3], sample_missing=sorted(e - d)[:3]))
    inv_ok = all(c["status"] == "PASS" for c in checks)
    det_ok = all(d["status"] == "PASS" for d in detectors)
    summary = dict(overall="PASS" if inv_ok and det_ok else "FAIL", invariants_passed=sum(c["status"] == "PASS" for c in checks),
                   invariants_total=len(checks), detectors_matching_ground_truth=sum(d["status"] == "PASS" for d in detectors),
                   detectors_total=len(detectors), funnel=funnel, checks=checks, detectors=detectors,
                   row_counts={t.name: len(T[t.name]) for t in TABLES})
    with open(os.path.join(out, "validation_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    with open(os.path.join(out, "validation_summary.md"), "w") as f:
        f.write(render_md(summary))
    return summary


def _dups(rows, cols):
    seen, bad = set(), []
    for r in rows:
        k = tuple(r[c] for c in cols)
        if k in seen:
            bad.append(k)
        seen.add(k)
    return bad


def render_md(s):
    L = [f"# Validation summary: **{s['overall']}**", "",
         f"Invariants: {s['invariants_passed']}/{s['invariants_total']} pass. Injected-anomaly detectors matching ground truth: "
         f"{s['detectors_matching_ground_truth']}/{s['detectors_total']}.", "", "## Row counts", ""]
    L += [f"- {k}: {v:,}" for k, v in s["row_counts"].items()]
    L += ["", "## Funnel reconciliation", ""] + [f"- {k}: {v:,}" for k, v in s["funnel"].items()]
    L += ["", "## Injected edge cases: detector output vs ground truth", "", "| issue_type | expected | detected | missing | unexpected | status |", "|---|---|---|---|---|---|"]
    L += [f"| {d['issue_type']} | {d['expected']} | {d['detected']} | {d['missing']} | {d['unexpected']} | {d['status']} |" for d in s["detectors"]]
    L += ["", "## Invariant checks", "", "| category | check | violations | status |", "|---|---|---|---|"]
    L += [f"| {c['category']} | {c['name']} | {c['violations']} | {c['status']} |" for c in s["checks"]]
    return "\n".join(L) + "\n"
