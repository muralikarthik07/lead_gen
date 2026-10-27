from leadgen import scoring
from leadgen.logic import ConsentIndex, dedupe_contacts, dedupe_leads, normalize_email, derive_lead_status


def test_normalize_email():
    assert normalize_email(" Jane.Doe+promo@ACME.example ") == "jane.doe@acme.example"


def test_tier_boundaries():
    assert [scoring.tier_for(x) for x in (0, 24, 25, 39, 40, 54, 55, 100)] == list("DDCCBBAA")


def test_rule_versions_effective_dated():
    rules = scoring.build_rule_rows()
    assert {r["rule_version"] for r in scoring.active_rules(rules, "2026-03-01T00:00:00")} == {1}
    assert {r["rule_version"] for r in scoring.active_rules(rules, "2026-06-01T00:00:00")} == {2}


def test_score_hand_computed_and_clamped():
    rules = scoring.build_rule_rows()
    f = {"employee_band": "1000+", "industry_target": 1, "seniority": "c_level", "free_email": 0, "source": "referral",
         "demo_requests": 1, "pricing_visits": 3, "email_clicks": 9, "web_visits": 20, "recent_inbound_7d": 1, "no_inbound_activity": 0}
    r = scoring.score_lead(f, rules, "2026-03-01T00:00:00")   # v1: 15+10+10+12+20+10+10+10+5 = 102
    assert r["raw"] == 102 and r["total"] == 100 and r["tier"] == "A"


def test_features_ignore_future_activity():
    acts = [dict(activity_type="demo_request", direction="inbound", occurred_at="2026-03-10T00:00:00")]
    co, ct, ld = dict(employee_band="1-10", industry="Retail"), dict(seniority="individual", email_type="free"), dict(source="paid_search")
    assert scoring.extract_features(co, ct, ld, acts, "2026-03-05T00:00:00")["demo_requests"] == 0
    assert scoring.extract_features(co, ct, ld, acts, "2026-03-11T00:00:00")["demo_requests"] == 1


def test_consent_index_half_open_periods():
    ci = ConsentIndex([dict(contact_id="c", channel="email", status="opt_in", effective_from="2026-01-01T00:00:00", effective_to="2026-02-01T00:00:00"),
                       dict(contact_id="c", channel="email", status="opt_out", effective_from="2026-02-01T00:00:00", effective_to=None)])
    assert ci.has_consent("c", "email", "2026-01-31T23:59:59") and not ci.has_consent("c", "email", "2026-02-01T00:00:00")
    assert not ci.has_consent("c", "phone", "2026-01-15T00:00:00")


def test_dedupe_contacts_and_leads():
    cs = [dict(contact_id="CON-1", email="a@x.example", created_at="2026-01-01T00:00:00"),
          dict(contact_id="CON-2", email="A+t@X.example", created_at="2026-02-01T00:00:00")]
    cd = dedupe_contacts(cs)
    assert cd == {"CON-2": "CON-1"}
    ls = [dict(lead_id="L1", contact_id="CON-1", product_interest="Platform", created_at="2026-01-01T00:00:00"),
          dict(lead_id="L2", contact_id="CON-2", product_interest="Platform", created_at="2026-02-15T00:00:00"),
          dict(lead_id="L3", contact_id="CON-1", product_interest="Platform", created_at="2026-06-01T00:00:00"),
          dict(lead_id="L4", contact_id="CON-1", product_interest="Security", created_at="2026-01-05T00:00:00")]
    assert dedupe_leads(ls, cd, 90) == {"L2": "L1"}


def test_status_precedence():
    a = dict(as_of="2026-10-22T00:00:00", stale_days=45, tier="A", has_completed_task=True, has_rep_touch=True)
    assert derive_lead_status(True, True, True, "2026-10-21T00:00:00", **a) == "Duplicate"
    assert derive_lead_status(False, True, True, "2026-10-21T00:00:00", **a) == "Converted"
    assert derive_lead_status(False, False, True, "2026-10-21T00:00:00", **a) == "Disqualified"
    assert derive_lead_status(False, False, False, "2026-01-01T00:00:00", **a) == "Stale"
    assert derive_lead_status(False, False, False, "2026-10-21T00:00:00", **a) == "Qualified"
