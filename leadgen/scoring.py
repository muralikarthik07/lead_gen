"""Transparent, versioned, effective-dated lead scoring. Pure functions over plain dict rows."""
from datetime import timedelta
from . import reference as ref
from .util import fmt, parse

TIER_THRESHOLDS = (("A", 55), ("B", 40), ("C", 25), ("D", 0))
V1_FROM, V2_FROM = "2026-01-01T00:00:00", "2026-06-01T00:00:00"

# key, category, feature, operator, value, points, cap_units, description
RULE_SPECS = [
    ("band_1000", "fit", "employee_band", "eq", "1000+", 15, None, "Company has 1000+ employees"),
    ("band_201", "fit", "employee_band", "eq", "201-1000", 10, None, "Company has 201-1000 employees"),
    ("band_51", "fit", "employee_band", "eq", "51-200", 6, None, "Company has 51-200 employees"),
    ("band_11", "fit", "employee_band", "eq", "11-50", 3, None, "Company has 11-50 employees"),
    ("target_industry", "fit", "industry_target", "eq", "1", 10, None, "Company is in a target industry"),
    ("sen_c", "fit", "seniority", "eq", "c_level", 10, None, "Contact is C-level"),
    ("sen_vp", "fit", "seniority", "eq", "vp", 10, None, "Contact is VP"),
    ("sen_dir", "fit", "seniority", "eq", "director", 7, None, "Contact is Director"),
    ("sen_mgr", "fit", "seniority", "eq", "manager", 4, None, "Contact is Manager"),
    ("free_email", "fit", "free_email", "eq", "1", -8, None, "Contact uses a free-mail address"),
    ("src_referral", "intent", "source", "eq", "referral", 12, None, "Source: referral"),
    ("src_partner", "intent", "source", "eq", "partner", 8, None, "Source: partner"),
    ("src_webinar", "intent", "source", "eq", "webinar", 6, None, "Source: webinar"),
    ("src_trade_show", "intent", "source", "eq", "trade_show", 6, None, "Source: trade show"),
    ("src_paid", "intent", "source", "eq", "paid_search", 5, None, "Source: paid search"),
    ("src_organic", "intent", "source", "eq", "organic_search", 4, None, "Source: organic search"),
    ("src_content", "intent", "source", "eq", "content_download", 2, None, "Source: content syndication"),
    ("demo_request", "intent", "demo_requests", "gte", "1", 20, None, "Requested a demo"),
    ("pricing_visits", "intent", "pricing_visits", "per_unit", "1", 5, 2, "Pricing page visits ({p} each, max {c})"),
    ("email_clicks", "engagement", "email_clicks", "per_unit", "1", 2, 5, "Email clicks ({p} each, max {c})"),
    ("web_visits", "engagement", "web_visits", "per_unit", "1", 1, 10, "Web visits ({p} each, max {c})"),
    ("recent_inbound", "engagement", "recent_inbound_7d", "eq", "1", 5, None, "Inbound engagement in the 7 days before scoring"),
    ("no_inbound", "engagement", "no_inbound_activity", "eq", "1", -5, None, "No inbound engagement at all"),
]
V2_OVERRIDES = {"demo_request": {"points": 25}, "email_clicks": {"points": 3, "cap": 4},
                "free_email": {"points": -10}, "web_visits": {"cap": 8}}


def build_rule_rows():
    rows = []
    for ver, eff_from, eff_to in ((1, V1_FROM, V2_FROM), (2, V2_FROM, None)):
        for i, (key, cat, feat, op, val, pts, cap, desc) in enumerate(RULE_SPECS, 1):
            ov = V2_OVERRIDES.get(key, {}) if ver == 2 else {}
            p_, c_ = ov.get("points", pts), ov.get("cap", cap)
            rows.append(dict(rule_id=f"SR-v{ver}-{i:03d}", rule_version=ver, category=cat, feature=feat, operator=op,
                             value=val, points=p_, cap_units=c_, effective_from=eff_from, effective_to=eff_to,
                             description=desc.format(p=p_, c=c_)))
    return rows


def tier_for(score):
    for t, th in TIER_THRESHOLDS:
        if score >= th:
            return t
    return "D"


def extract_features(company, contact, lead, acts, t):
    """Features known at time t. `acts`: dicts with activity_type, direction, occurred_at (ISO str).
    Only activities with occurred_at <= t are used -> no look-ahead / post-conversion leakage."""
    cut7 = fmt(parse(t) - timedelta(days=7))
    clicks = visits = pricing = demo = n_inbound = recent = 0
    for a in acts:
        if a["direction"] != "inbound" or a["occurred_at"] > t or a["activity_type"] == "form_submit":
            continue
        n_inbound += 1
        ty = a["activity_type"]
        clicks += ty == "email_click"
        visits += ty == "web_visit"
        pricing += ty == "pricing_page_visit"
        demo += ty == "demo_request"
        if a["occurred_at"] > cut7:
            recent = 1
    return {"employee_band": company["employee_band"], "industry_target": int(company["industry"] in ref.TARGET_INDUSTRIES),
            "seniority": contact["seniority"], "free_email": int(contact["email_type"] == "free"), "source": lead["source"],
            "demo_requests": demo, "pricing_visits": pricing, "email_clicks": clicks, "web_visits": visits,
            "recent_inbound_7d": recent, "no_inbound_activity": int(n_inbound == 0)}


def active_rules(rules, t):
    return [r for r in rules if r["effective_from"] <= t and (not r["effective_to"] or t < r["effective_to"])]


def score_lead(features, rules, t):
    comps, raw, version = [], 0, None
    for r in active_rules(rules, t):
        version = int(r["rule_version"])
        v = features[r["feature"]]
        if r["operator"] == "eq":
            units = int(str(v) == str(r["value"]))
        elif r["operator"] == "gte":
            units = int(float(v) >= float(r["value"]))
        else:
            cap = r["cap_units"]
            units = min(int(v), int(cap)) if cap not in (None, "") else int(v)
        if units:
            pts = int(r["points"]) * units
            comps.append((r["rule_id"], units, pts))
            raw += pts
    total = max(0, min(100, raw))
    return {"rule_version": version, "components": comps, "raw": raw, "total": total, "tier": tier_for(total)}
