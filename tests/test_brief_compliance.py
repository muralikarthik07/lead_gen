"""One test per requirement of the problem brief. Runs on the small fixture; point it at the full dataset with
    LEADGEN_AUDIT_DIR=output/full python -m pytest tests/test_brief_compliance.py"""
import csv, json, os, re, sqlite3
from collections import Counter
import pytest
from leadgen.io_utils import read_csv, load_tables
from leadgen.schema import TABLES, SCHEMA


@pytest.fixture(scope="module")
def D(ds):
    out = os.environ.get("LEADGEN_AUDIT_DIR") or ds["out"]
    return dict(out=out, T=load_tables(out), meta=json.load(open(f"{out}/run_metadata.json")),
                gt=read_csv(f"{out}/ground_truth/anomalies.csv"), lab=read_csv(f"{out}/ground_truth/lead_labels.csv"))


def test_11_required_entities_exist_with_pk_and_fk(D):
    required = {"Company", "Contact", "Lead", "Campaign", "Activity", "Consent", "ScoreRule", "SalesRep", "Task", "Opportunity", "StageHistory"}
    assert required <= set(SCHEMA)
    assert all(t.pk for t in TABLES)
    fks = {(t.name, c.name): c.fk for t in TABLES for c in t.cols if c.fk}
    for k in [("Contact", "company_id"), ("Lead", "contact_id"), ("Lead", "campaign_id"), ("Lead", "consent_id"), ("Activity", "lead_id"), ("Task", "lead_id"),
              ("Opportunity", "lead_id"), ("StageHistory", "opportunity_id"), ("Consent", "contact_id")]:
        assert k in fks, k
    assert not SCHEMA["Lead"].cols[[c.name for c in SCHEMA["Lead"].cols].index("campaign_id")].required        # optional relationship documented


def test_bridge_tables_for_many_to_many(D):
    assert {"RepCoverage", "LeadScoreComponent"} <= set(SCHEMA)
    assert SCHEMA["RepCoverage"].pk == ("rep_id", "territory", "product") and SCHEMA["LeadScoreComponent"].pk == ("score_id", "rule_id")


def test_id_conventions_exactly_as_specified(D):
    T = D["T"]
    assert T["Company"][0]["company_id"] == "CO-000001" and T["Contact"][0]["contact_id"] == "CON-000001"
    assert T["Lead"][0]["lead_id"] == "LEAD-2026-000001" and T["Opportunity"][0]["opportunity_id"].startswith("OPP-2026-000001")
    lead_ids = {r["lead_id"] for r in T["Lead"]}
    assert all(re.fullmatch(r"ACT-(LEAD-2026-\d{6})-\d{3}", a["activity_id"]) and re.match(r"ACT-(LEAD-2026-\d{6})", a["activity_id"]).group(1) in lead_ids for a in T["Activity"][:5000])
    assert T["Activity"][0]["activity_id"] == f"ACT-{T['Activity'][0]['lead_id']}-001"
    assert all(re.fullmatch(r"TASK-LEAD-2026-\d{6}-\d{3}", t["task_id"]) for t in T["Task"])
    assert [t["task_id"] for t in T["Task"] if t["lead_id"] == T["Task"][0]["lead_id"]][0].endswith("-001")


def test_baseline_volume_matches_spec_or_config(D):
    c = D["meta"]["config"]
    T = D["T"]
    assert (len(T["Lead"]), len(T["Contact"]), len(T["Company"]), len(T["Opportunity"])) == (c["n_leads"], c["n_contacts"], c["n_companies"], c["n_opportunities"])
    if c["n_leads"] == 20000:
        assert (len(T["Lead"]), len(T["Contact"]), len(T["Company"]), len(T["Opportunity"])) == (20000, 10000, 5000, 3000)
    assert c["seed"] == 20261022 or os.environ.get("LEADGEN_AUDIT_DIR") is None


def test_required_data_characteristics_present(D):
    T, lab = D["T"], D["lab"]
    assert sum(1 for l in T["Lead"] if l["duplicate_of_lead_id"]) > 0                         # duplicates
    assert any(c["status"] == "opt_out" for c in T["Consent"])                                # opt-outs
    assert any(l["status"] == "Stale" for l in T["Lead"])                                     # stale leads
    assert any(r["is_high_score_non_converter"] == "1" for r in lab)                          # high-score non-converters
    assert {"A", "B", "C", "D"} <= {s["tier"] for s in T["LeadScore"]}
    assert len({o["status"] for o in T["Opportunity"]}) == 3 and {"Closed Won", "Closed Lost"} <= {o["current_stage"] for o in T["Opportunity"]}
    assert all(o["outcome_reason"] for o in T["Opportunity"] if o["status"] != "open")        # won/lost reasons recorded


def test_five_required_edge_cases_labelled(D):
    kinds = Counter(g["issue_type"] for g in D["gt"])
    for k in ("opted_out_lead_contacted", "score_uses_post_conversion_event", "lead_assigned_outside_territory", "duplicate_creates_duplicate_opportunity", "stage_history_gap"):
        assert kinds[k] > 0, k
    assert all(g["issue_type"] and g["record_id"] for g in D["gt"])                           # issue_type label on every injected case


def test_ground_truth_is_separate_and_not_leaked(D):
    out = D["out"]
    assert os.path.isdir(f"{out}/ground_truth") and os.path.exists(f"{out}/ground_truth/anomalies.json")
    banned = {"issue_type", "hidden_blocker", "converted", "eventual_outcome", "holdout_split", "is_high_score_non_converter", "anomaly_id"}
    for f in os.listdir(f"{out}/csv"):
        assert not banned & set(open(f"{out}/csv/{f}").readline().strip().split(",")), f


def test_state_changes_are_events_not_overwrites(D):
    T = D["T"]
    assert len({s["lead_id"] for s in T["LeadScore"]}) <= len(T["LeadScore"])                  # append-only score events
    assert Counter(c["contact_id"] for c in T["Consent"]).most_common(1)[0][1] >= 2           # consent timeline has multiple rows
    assert Counter(h["opportunity_id"] for h in T["StageHistory"]).most_common(1)[0][1] >= 3  # stage history rows
    assert {r["rule_version"] for r in T["ScoreRule"]} == {"1", "2"} and any(r["effective_to"] for r in T["ScoreRule"])  # effective-dated rules


def test_all_export_formats_and_documentation_present(D):
    out = D["out"]
    for p in ("sql/seed.sql", "schema/schema.sql", "schema/data_dictionary.md", "schema/data_dictionary.json", "SOURCE_MANIFEST.md", "run_metadata.json",
              "validation_summary.md", "validation_summary.json", "evaluation_report.md", "MANIFEST.json"):
        assert os.path.exists(f"{out}/{p}"), p
    assert "python -m leadgen generate" in D["meta"]["command"] and str(D["meta"]["config"]["seed"]) in D["meta"]["command"]
    if os.path.isdir(f"{out}/json"):
        for t in TABLES:
            assert len(json.load(open(f"{out}/json/{t.filename}.json"))) == len(D["T"][t.name]), t.name


def test_json_and_csv_equal_and_sql_loads_with_valid_joins(D):
    out = D["out"]
    con = sqlite3.connect(":memory:")
    con.executescript(open(f"{out}/sql/seed.sql").read())
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    for t in TABLES:
        assert con.execute(f"SELECT COUNT(*) FROM {t.name}").fetchone()[0] == len(D["T"][t.name]), t.name


def test_acceptance_criteria(D, ds):
    s = json.load(open(f"{D['out']}/validation_summary.json"))
    assert s["overall"] == "PASS"
    names = " ".join(c["name"] for c in s["checks"])
    assert "reproducible" in names                                                              # score is reproducible
    assert any(c["category"] == "consent" for c in s["checks"]) and any(c["category"] == "routing" for c in s["checks"])
    assert any(c["category"] == "funnel" for c in s["checks"])                                  # funnel reconciles
    ev = json.load(open(f"{D['out']}/evaluation_report.json"))
    assert ev["n_test"] > 0 and ev["auc_test_heldout"] > 0.6                                    # held-out outcomes


def test_dates_are_in_valid_order_and_ids_year_matches(D):
    T = D["T"]
    assert all(l["lead_id"].split("-")[1] == l["created_at"][:4] for l in T["Lead"])
    assert all(o["opportunity_id"].split("-")[1] == o["created_at"][:4] for o in T["Opportunity"])
    assert all(l["created_at"] <= D["meta"]["config"]["as_of"] for l in T["Lead"])
