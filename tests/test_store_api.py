import json, re, shutil, subprocess, urllib.error, urllib.request
from collections import defaultdict
import pytest
from leadgen import server as srv
from leadgen.store import Store, LEAD_ID_RE


def get(base, path, method="GET"):
    req = urllib.request.Request(base + path, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def jget(base, path):
    s, h, b = get(base, path)
    return s, json.loads(b)


# ----------------------------------------------------------------- store (no HTTP)
def test_store_missing_dataset_has_helpful_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="python -m leadgen generate"):
        Store(str(tmp_path))


def test_overview_matches_configuration_and_reconciles(store, ds):
    o, c = store.overview, ds["cfg"]
    assert (o["counts"]["leads"], o["counts"]["contacts"], o["counts"]["companies"], o["counts"]["opportunities"]) == (c.n_leads, c.n_contacts, c.n_companies, c.n_opportunities)
    assert o["opp_status"]["open"] + o["opp_status"]["won"] + o["opp_status"]["lost"] == o["counts"]["opportunities"]
    f = {x["label"]: x["value"] for x in o["funnel"]}
    assert f["Master leads (after dedupe)"] + o["duplicates"] == f["All leads"] == c.n_leads
    assert sum(o["status"].values()) == c.n_leads and sum(o["tiers"].values()) == f["Scored"]


def test_query_leads_filter_sort_page(store):
    r = store.query_leads(tier="A", size=5)
    assert r["total"] > 0 and all(x["tier"] == "A" for x in r["rows"]) and len(r["rows"]) <= 5
    s = store.query_leads(sort="score", direction="desc", size=50)["rows"]
    scores = [x["score"] for x in s if x["score"] is not None]
    assert scores == sorted(scores, reverse=True)
    first = store.query_leads(size=7, page=1)["rows"][0]["lead_id"]
    assert store.query_leads(q=first.lower())["rows"][0]["lead_id"] == first            # case-insensitive id search
    assert store.query_leads(q="zzz-no-such-thing")["total"] == 0
    assert store.query_leads(size=1000)["size"] == 100                                    # page size is capped
    d = store.query_leads(flag="duplicate")
    assert d["total"] == store.overview["duplicates"] and all(x["duplicate_of"] for x in d["rows"])


def test_truth_is_hidden_unless_requested(store):
    assert "truth" not in store.query_leads(size=3)["rows"][0]
    assert "truth" in store.query_leads(size=3, truth=True)["rows"][0]
    lid = store.rows[0]["lead_id"]
    assert "truth" not in store.lead_detail(lid) and "truth" in store.lead_detail(lid, truth=True)
    assert store.query_leads(flag="has_anomaly")["total"] == store.overview["counts"]["leads"]   # truth-only filter ignored without truth


def test_live_record_checks_find_exactly_the_labelled_leads(store):
    """The UI's per-record checks are independent detectors: their failures must equal the ground truth labels."""
    want = defaultdict(set)
    for a in store.anoms:
        want[a["issue_type"]].add(a["lead_id"])
    fails = defaultdict(set)
    for r in store.rows:
        for c in store.lead_detail(r["lead_id"])["checks"]:
            if c["status"] == "fail":
                fails[c["name"]].add(r["lead_id"])
    assert fails["Routed to a rep covering territory × product"] == want["lead_assigned_outside_territory"]
    assert fails["Scores use only pre-conversion data"] == want["score_uses_post_conversion_event"]
    assert fails["Every outbound contact had consent"] == want["opted_out_lead_contacted"]
    assert fails["Stage history is continuous"] == want["stage_history_gap"]
    assert fails["Not a duplicate"] == want["duplicate_lead"]
    assert not fails["Score reproducible from source rows"]


def test_lead_detail_shape(store):
    lid = next(r["lead_id"] for r in store.rows if r["opp_id"] and not r["duplicate_of"])
    d = store.lead_detail(lid)
    assert d["opportunity"]["stages"] and d["scores"][0]["components"] and d["activities"] and d["consent"]
    assert sum(c["points"] for c in d["scores"][0]["components"]) == int(d["scores"][0]["raw_score"])
    assert store.lead_detail("LEAD-0000-000000") is None


def test_opportunity_query_and_dictionary(store):
    o = store.query_opps(status="won")
    assert o["total"] == store.overview["opp_status"]["won"] and sum(s["count"] for s in o["stages"]) == store.overview["counts"]["opportunities"]
    d = store.dictionary()
    assert len(d["tables"]) == 14 and d["relationships"] and {r["rule_version"] for r in d["rules"]} == {"1", "2"}


def test_rule_descriptions_match_their_points_in_every_version(store):
    for r in store.t["score_rule"]:
        if r["operator"] == "per_unit":
            assert f"({r['points']} each, max {r['cap_units']})" in r["description"]


# ----------------------------------------------------------------------- HTTP
def test_http_basics(server):
    assert jget(server, "/api/health")[1]["status"] == "ok"
    for p in ("/api/overview", "/api/meta", "/api/leads", "/api/opportunities", "/api/validation", "/api/evaluation", "/api/anomalies", "/api/dictionary"):
        s, j = jget(server, p)
        assert s == 200 and j, p
    s, h, b = get(server, "/")
    assert s == 200 and h["Content-Type"].startswith("text/html") and b"LeadScope" in b
    assert h["X-Content-Type-Options"] == "nosniff"
    assert get(server, "/api/leads", "HEAD")[0] == 200


def test_http_errors(server):
    assert jget(server, "/api/nope")[0] == 404
    assert jget(server, "/api/leads/LEAD-9999-999999")[0] == 404
    assert jget(server, "/api/leads?page=abc")[0] == 400
    assert get(server, "/missing.js")[0] == 404
    assert get(server, "/api/revalidate")[0] == 404                                         # POST-only endpoint


def test_http_blocks_path_traversal(server):
    for p in ("/../../../../etc/passwd", "/..%2f..%2f..%2fetc/passwd", "/%2e%2e/%2e%2e/etc/passwd", "/../server.py"):
        s, h, b = get(server, p)
        assert b"root:" not in b and b"def make_handler" not in b, p


def test_http_truth_param_roundtrip(server):
    _, plain = jget(server, "/api/leads?size=2")
    _, truth = jget(server, "/api/leads?size=2&truth=1")
    assert "truth" not in plain["rows"][0] and "truth" in truth["rows"][0]


def test_http_revalidate_reruns_validator(ds, tmp_path):
    out = str(tmp_path / "copy")
    shutil.copytree(ds["out"], out)
    import threading
    h = srv.serve(out, port=0, quiet=True)
    threading.Thread(target=h.serve_forever, daemon=True).start()
    try:
        s, h_, b = get(f"http://127.0.0.1:{h.server_address[1]}", "/api/revalidate", "POST")
        assert s == 200 and json.loads(b)["validation"]["overall"] == "PASS"
    finally:
        h.shutdown()


# -------------------------------------------------------------- frontend files
def test_frontend_is_self_contained_and_wired():
    import os
    web = os.path.join(os.path.dirname(srv.__file__), "web")
    html = open(f"{web}/index.html").read()
    for ref in re.findall(r'(?:src|href)="(/[^"]+)"', html):
        assert os.path.exists(web + ref), ref
    for f in ("index.html", "styles.css", "app.js"):
        txt = open(f"{web}/{f}").read()
        ext = [u for u in re.findall(r"https?://[^\s\"')]+", txt) if "w3.org" not in u]
        assert not ext, (f, ext)                                                              # works offline: no CDN/fonts/analytics
    assert 'lang="en"' in html and 'name="viewport"' in html and 'class="skip"' in html
    assert "aria-live" in html and 'role="switch"' in html


def test_frontend_javascript_syntax():
    if not shutil.which("node"):
        pytest.skip("node not installed")
    import os
    p = os.path.join(os.path.dirname(srv.__file__), "web", "app.js")
    r = subprocess.run(["node", "--check", p], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_frontend_escapes_every_dynamic_value_helper():
    """esc() must neutralise HTML; verified by executing the real function in node."""
    if not shutil.which("node"):
        pytest.skip("node not installed")
    import os
    src = open(os.path.join(os.path.dirname(srv.__file__), "web", "app.js")).read()
    line = next(l for l in src.splitlines() if l.startswith("const esc ="))
    r = subprocess.run(["node", "-e", line + "; console.log(esc('<img src=x onerror=alert(1)>\"&\\''))"], capture_output=True, text=True)
    assert "<" not in r.stdout and "&lt;img" in r.stdout and "&quot;" in r.stdout and "&#39;" in r.stdout
