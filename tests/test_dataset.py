import csv, hashlib, json, os, shutil
import pytest
from leadgen import validate
from leadgen.cli import build
from leadgen.config import Config
from leadgen.io_utils import read_csv


def test_volumes_match_config(ds):
    rc, c = ds["summary"]["row_counts"], ds["cfg"]
    assert (rc["Lead"], rc["Contact"], rc["Company"], rc["Opportunity"]) == (c.n_leads, c.n_contacts, c.n_companies, c.n_opportunities)


def test_all_invariants_and_detectors_pass(ds):
    s = ds["summary"]
    assert s["overall"] == "PASS", [c for c in s["checks"] if c["status"] != "PASS"] + [d for d in s["detectors"] if d["status"] != "PASS"]


def test_all_required_edge_cases_present_and_labelled(ds):
    kinds = {d["issue_type"]: d["expected"] for d in ds["summary"]["detectors"]}
    for k in ("opted_out_lead_contacted", "score_uses_post_conversion_event", "lead_assigned_outside_territory",
              "duplicate_creates_duplicate_opportunity", "stage_history_gap", "duplicate_contact", "duplicate_lead"):
        assert kinds.get(k, 0) > 0, k


def test_dataset_has_optouts_stale_and_high_score_nonconverters(ds):
    out = ds["out"]
    assert any(r["status"] == "opt_out" for r in read_csv(f"{out}/csv/consent.csv"))
    assert any(r["status"] == "Stale" for r in read_csv(f"{out}/csv/lead.csv"))
    assert any(r["is_high_score_non_converter"] == "1" for r in read_csv(f"{out}/ground_truth/lead_labels.csv"))


def test_no_ground_truth_in_input_tables(ds):
    for f in os.listdir(f"{ds['out']}/csv"):
        hdr = open(f"{ds['out']}/csv/{f}").readline().strip().split(",")
        assert not set(hdr) & validate.FORBIDDEN_FEATURE_COLUMNS, f


def test_evaluation_is_heldout_and_informative(ds):
    e = ds["eval"]
    assert e["n_test"] > 0 and e["n_train"] > 0 and e["auc_test_heldout"] > 0.6
    assert e["tier_conversion_rate_train"]["A"] > e["tier_conversion_rate_train"]["D"]


def test_sql_seed_loads_with_fk_enforcement(ds):
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.executescript(open(f"{ds['out']}/sql/seed.sql").read())
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    assert con.execute("SELECT COUNT(*) FROM Lead").fetchone()[0] == ds["cfg"].n_leads


def test_reproducible_same_seed_and_different_seed_differs(tmp_path):
    cfg = Config.scaled(0.03)
    m = []
    for i in (1, 2):
        build(cfg, str(tmp_path / f"r{i}"))
        m.append(json.load(open(tmp_path / f"r{i}" / "MANIFEST.json"))["files"])
    assert m[0] == m[1]
    build(Config.scaled(0.03, seed=1), str(tmp_path / "r3"))
    m3 = json.load(open(tmp_path / "r3" / "MANIFEST.json"))["files"]
    assert m3["csv/lead.csv"]["sha256"] != m[0]["csv/lead.csv"]["sha256"]


# ---- mutation tests: the validator must FAIL when data is corrupted (proves checks are not vacuous)
def _mutate(ds, tmp_path, table, fn):
    dst = str(tmp_path / ("m%d" % len(os.listdir(tmp_path))))
    shutil.copytree(ds["out"], dst)
    p = f"{dst}/csv/{table}.csv"
    rows = read_csv(p)
    fn(rows)
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    return validate.validate(dst)


def _failed(s):
    return [c["name"] for c in s["checks"] if c["status"] == "FAIL"] + [d["issue_type"] for d in s["detectors"] if d["status"] == "FAIL"]


def test_mutation_orphan_foreign_key(ds, tmp_path):
    s = _mutate(ds, tmp_path, "task", lambda r: r[0].update(lead_id="LEAD-2026-999999"))
    assert s["overall"] == "FAIL" and _failed(s)


def test_mutation_duplicate_primary_key(ds, tmp_path):
    s = _mutate(ds, tmp_path, "company", lambda r: r[1].update(company_id=r[0]["company_id"]))
    assert _failed(s)


def test_mutation_tampered_score_breaks_reproducibility(ds, tmp_path):
    s = _mutate(ds, tmp_path, "lead_score", lambda r: r[0].update(raw_score="99", total_score="99", tier="A"))
    assert any("reproducible" in n or "raw ==" in n for n in _failed(s))


def test_mutation_unlabelled_opted_out_contact_is_detected(ds, tmp_path):
    out = ds["out"]
    gt = {g["record_id"] for g in read_csv(f"{out}/ground_truth/anomalies.csv") if g["issue_type"] == "opted_out_lead_contacted"}
    optout = next(c for c in read_csv(f"{out}/csv/consent.csv") if c["channel"] == "email" and c["status"] == "opt_out")
    lead = next(l for l in read_csv(f"{out}/csv/lead.csv") if l["contact_id"] == optout["contact_id"])

    def f(rows):
        a = next(x for x in rows if x["lead_id"] == lead["lead_id"] and x["activity_type"] == "form_submit")
        a.update(activity_type="email_outbound", direction="outbound", channel="email", occurred_at=optout["effective_from"])
        f.id = a["activity_id"]
    s = _mutate(ds, tmp_path, "activity", f)
    d = next(d for d in s["detectors"] if d["issue_type"] == "opted_out_lead_contacted")
    assert d["status"] == "FAIL" and d["unexpected"] >= 1 and s["overall"] == "FAIL"


def test_mutation_bad_enum_and_date_order(ds, tmp_path):
    s = _mutate(ds, tmp_path, "opportunity", lambda r: r[0].update(status="maybe"))
    assert any("Opportunity: required/type/enum" in n for n in _failed(s))
    s = _mutate(ds, tmp_path, "task", lambda r: r[0].update(due_at="2000-01-01T00:00:00"))
    assert any("Task due" in n for n in _failed(s))
