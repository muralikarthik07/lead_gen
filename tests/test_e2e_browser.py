"""Real-browser tests (headless Chromium via Playwright). Skipped automatically if Playwright/Chromium is unavailable:
    pip install playwright && playwright install chromium"""
import pytest

sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # browser binary not installed
            pytest.skip(f"chromium unavailable: {e}")
        yield b
        b.close()


@pytest.fixture()
def page(browser, server):
    ctx = browser.new_context(viewport={"width": 1366, "height": 900})
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.on("response", lambda r: pg.errors.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    pg.base = server
    yield pg
    ctx.close()


def go(pg, h=""):
    pg.goto(pg.base + "/" + h)


def test_dashboard_shows_real_numbers(page, ds):
    go(page)
    page.wait_for_selector(".funnel")
    assert f"{ds['cfg'].n_leads:,}" in page.inner_text(".kpis")
    assert "Conversion funnel" in page.inner_text("#view")
    assert page.title().startswith("Dashboard")
    assert not page.errors


@pytest.mark.parametrize("hash_,heading", [("#/", "Dashboard"), ("#/leads", "Leads"), ("#/pipeline", "Pipeline"), ("#/model", "Scoring model"),
                                           ("#/quality", "Data quality"), ("#/edge-cases", "Edge cases"), ("#/dictionary", "Data dictionary"), ("#/run", "Run & reproduce")])
def test_every_page_renders_without_errors(page, hash_, heading):
    go(page, hash_)
    page.wait_for_selector("#view h1")
    assert page.inner_text("#view h1") == heading
    assert page.get_attribute("#nav a[aria-current='page']", "href") is not None
    assert not page.errors, page.errors


def test_sidebar_navigation_by_click(page):
    go(page)
    page.wait_for_selector(".funnel")
    for name in ("Leads", "Pipeline", "Scoring model", "Data quality"):
        page.click(f"#nav >> text={name}")
        page.wait_for_selector(f"#view h1:text-is('{name}')")
    assert not page.errors


def test_leads_filter_search_sort_paginate(page, ds):
    go(page, "#/leads")
    page.wait_for_selector("tr.click")
    assert page.locator("tr.click").count() == 20
    total = page.inner_text(".pager span")
    page.select_option("#f-tier", "A")
    page.wait_for_function("document.querySelectorAll('tr.click').length>0 && [...document.querySelectorAll('tr.click')].every(r=>r.innerText.includes('Tier A'))")
    assert page.inner_text(".pager span") != total
    page.select_option("#f-tier", "")
    page.fill("#f-q", "zzzz-nothing")
    page.wait_for_selector("td.empty")
    page.click("#f-reset")
    page.wait_for_selector("tr.click")
    page.click("button[data-pg='2']")
    page.wait_for_function("document.querySelector('.pager span').innerText.includes('page 2')")
    page.click("th button[data-sort='score']")
    page.wait_for_function("document.querySelector('th button[data-sort=score]').innerText.includes('▼')")
    assert not page.errors


def test_open_lead_shows_traceable_score_and_checks(page):
    go(page, "#/leads?flag=has_opportunity")
    page.wait_for_selector("tr.click")
    page.click("tr.click td a")
    page.wait_for_selector("#score-card .bar")
    body = page.inner_text("#view")
    for text in ("Record checks", "Score breakdown", "Activity history", "Consent timeline", "Follow-up tasks", "Opportunity"):
        assert text in body, text
    assert page.locator(".ring").count() == 1
    page.click("#tl-card [data-f='outbound']")
    page.wait_for_function("document.querySelectorAll('#tl-card .tl li.in').length===0")
    assert not page.errors


def test_ground_truth_toggle_reveals_and_hides_labels(page):
    go(page, "#/leads")
    page.wait_for_selector("tr.click")
    assert page.get_attribute("#truth", "aria-checked") == "false"
    assert page.locator("th:text-is('Truth')").count() == 0
    page.click("#truth")
    page.wait_for_selector("th:text-is('Truth')")
    assert page.get_attribute("#truth", "aria-checked") == "true"
    page.select_option("#f-flag", "has_anomaly")
    page.wait_for_selector("tr.click .tag.bad")
    page.click("tr.click td a")
    page.wait_for_selector(".truth")
    assert "Ground truth" in page.inner_text(".truth")
    page.click("#truth")
    page.wait_for_selector(".truth", state="detached")
    assert not page.errors


def test_injected_leak_is_flagged_by_live_check(page, store):
    lead = next(a["lead_id"] for a in store.anoms if a["issue_type"] == "score_uses_post_conversion_event")
    go(page, f"#/leads/{lead}")
    page.wait_for_selector("#score-card .bar")
    assert "1 failed" in page.inner_text("#view")
    assert "Scores use only pre-conversion data" in page.inner_text(".checks")
    page.click("#score-card [data-sc='1']")
    assert "leakage" in page.inner_text("#score-card")


def test_global_search_navigates_to_leads(page, store):
    first = store.rows[0]
    go(page)
    page.wait_for_selector(".funnel")
    page.fill("#gq", first["company"].split()[0])
    page.press("#gq", "Enter")
    page.wait_for_selector("tr.click")
    assert "#/leads?q=" in page.url
    assert first["company"].split()[0].lower() in page.inner_text("tbody").lower()


def test_theme_toggle_persists(page):
    go(page)
    page.wait_for_selector(".funnel")
    before = page.evaluate("document.documentElement.dataset.theme")
    page.click("#theme")
    after = page.evaluate("document.documentElement.dataset.theme")
    assert before != after
    page.reload()
    page.wait_for_selector(".funnel")
    assert page.evaluate("document.documentElement.dataset.theme") == after


def test_quality_page_shows_pass_and_can_revalidate(page):
    go(page, "#/quality")
    page.wait_for_selector(".banner")
    assert "PASS" in page.inner_text(".banner")
    page.click("[data-c='leakage']")
    assert page.locator("#qt tbody tr").count() >= 2
    page.fill("#qq", "reproducible")
    assert page.locator("#qt tbody tr").count() == 1
    page.click("#rerun")
    page.wait_for_selector("#rerun:not([disabled])", timeout=30000)
    assert "PASS" in page.inner_text(".banner")


def test_edge_case_cards_filter_table(page, store):
    go(page, "#/edge-cases")
    page.wait_for_selector("[data-t]")
    assert page.locator("[data-t]").count() == 7
    page.click("[data-t='stage_history_gap']")
    n = sum(1 for a in store.anoms if a["issue_type"] == "stage_history_gap")
    page.wait_for_function(f"document.querySelector('#et .pager span').innerText.startsWith('{n} result')")
    assert page.locator("#et tbody tr").first.inner_text().count("stage history gap") >= 1


def test_dictionary_lists_all_tables_and_columns(page):
    go(page, "#/dictionary/Opportunity")
    page.wait_for_selector("table")
    assert page.locator(".tlist a").count() == 14
    assert "opportunity_id" in page.inner_text("#view") and "StageHistory" in page.inner_text("#view")
    page.click(".tlist a:has-text('Consent')")
    page.wait_for_selector("text=effective_to")


def test_pipeline_stage_filter(page):
    go(page, "#/pipeline")
    page.wait_for_selector("#pt tr.click")
    page.click("[data-stage='Closed Won']")
    page.wait_for_function("[...document.querySelectorAll('#pt tbody tr')].every(r=>r.innerText.includes('Closed Won'))")


def test_unknown_route_and_lead_error_states(page):
    go(page, "#/nope")
    page.wait_for_selector("text=Page not found")
    go(page, "#/leads/LEAD-9999-999999")
    page.wait_for_selector("text=Something went wrong")
    assert "lead not found" in page.inner_text("#view")


def test_responsive_no_horizontal_overflow_and_a11y_basics(browser, server):
    ctx = browser.new_context(viewport={"width": 390, "height": 800})
    pg = ctx.new_page()
    for h in ("#/", "#/leads", "#/model", "#/quality"):
        pg.goto(server + "/" + h)
        pg.wait_for_selector("#view h1")
        pg.wait_for_timeout(250)
        assert not pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"), h
    assert pg.get_attribute("#truth", "aria-label")
    assert pg.get_attribute("#theme", "aria-label")
    pg.reload()                                   # fresh load: first Tab stop must be the skip link
    pg.wait_for_selector("#view h1")
    pg.keyboard.press("Tab")
    assert pg.evaluate("document.activeElement.className") == "skip"
    ctx.close()


def test_xss_payload_in_data_is_escaped(page):
    go(page)
    page.wait_for_selector(".funnel")
    assert page.evaluate("esc('<img src=x onerror=window.__x=1>')") == "&lt;img src=x onerror=window.__x=1&gt;"
    page.evaluate("document.querySelector('#view').innerHTML = `<p>${esc('<img src=x onerror=window.__x=1>')}</p>`")
    assert page.evaluate("window.__x") is None


def test_rapid_navigation_never_shows_a_stale_page(page):
    """Regression: a slow earlier page load must not overwrite the page the user navigated to last."""
    go(page)
    page.wait_for_selector(".funnel")
    page.evaluate("location.hash='#/quality'; location.hash='#/model'; location.hash='#/leads'; location.hash='#/run'")
    page.wait_for_selector("#view h1:text-is('Run & reproduce')")
    page.wait_for_timeout(1200)                       # give every slower, earlier request time to finish
    assert page.inner_text("#view h1") == "Run & reproduce" and page.url.endswith("#/run")
    assert page.get_attribute("#nav a[aria-current='page']", "href") == "#/run"
    assert not page.errors, page.errors
