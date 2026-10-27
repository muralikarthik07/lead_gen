"use strict";
/* LeadScope: dependency-free SPA. All data comes from the read-only JSON API (/api/*). Every dynamic value goes through esc(). */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = n => n == null ? "–" : Number(n).toLocaleString("en-US");
const pct = (x, d = 1) => x == null || isNaN(x) ? "–" : (x * 100).toFixed(d) + "%";
const usd = n => n == null ? "–" : "$" + (n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "k" : Math.round(n));
const usdFull = n => n == null ? "–" : "$" + Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 });
const day = s => s ? s.slice(0, 10) : "–";
const dt = s => s ? s.replace("T", " ").slice(0, 16) : "–";
const label = s => String(s ?? "").replace(/_/g, " ");
const cap = s => label(s).replace(/^./, c => c.toUpperCase());
const ls = { get(k, d) { try { return localStorage.getItem("ls." + k) ?? d } catch { return d } }, set(k, v) { try { localStorage.setItem("ls." + k, v) } catch { } } };

const ICONS = {
  dash: '<path d="M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z"/>',
  leads: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
  pipe: '<path d="M3 4h18l-7 8v6l-4 2v-8z"/>',
  model: '<path d="M3 20V10M9 20V4M15 20v-7M21 20V8"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  flag: '<path d="M4 22V4M4 4h13l-2 4 2 4H4"/>',
  book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 19.5V22h16"/>',
  run: '<path d="M5 3l14 9-14 9z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  back: '<path d="M15 18l-6-6 6-6"/>',
};
const icon = (n, s = 18) => `<svg viewBox="0 0 24 24" width="${s}" height="${s}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[n]}</svg>`;
const NAV = [["#/", "Dashboard", "dash"], ["#/leads", "Leads", "leads"], ["#/pipeline", "Pipeline", "pipe"], ["#/model", "Scoring model", "model"],
["#/quality", "Data quality", "check"], ["#/edge-cases", "Edge cases", "flag"], ["#/dictionary", "Data dictionary", "book"], ["#/run", "Run & reproduce", "run"]];

/* ---------- API ---------- */
const cache = {};
let seq = 0;                                   // incremented on every route change
const STALE = new Promise(() => { });          // never settles: halts an obsolete async view silently (no stale overwrite, no console noise)
async function api(path, opts) {
  const t = seq;
  const r = await fetch("/api/" + path, opts);
  const j = await r.json().catch(() => ({}));
  if (t !== seq) return STALE;
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
async function cached(k, p) {
  const t = seq, v = await (cache[k] || (cache[k] = api(p).catch(e => { delete cache[k]; throw e; })));
  return t !== seq ? STALE : v;
}
const truthQ = () => state.truth ? "&truth=1" : "";
const state = { truth: ls.get("truth", "0") === "1" };
let AS_OF = "2026-10-22T00:00:00";

/* ---------- UI helpers ---------- */
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("on"), 1800); }
const pill = (text, cls) => `<span class="pill ${cls || ""}">${esc(label(text))}</span>`;
const tierPill = t => t ? pill("Tier " + t, "tier-" + t) : `<span class="muted">–</span>`;
const stPill = s => pill(s, "st-" + String(s).toLowerCase());
const oPill = s => s ? pill(s, "os-" + s) : `<span class="muted">–</span>`;
const card = (title, body, o = {}) => `<section class="card ${o.cls || ""}"><header><h2>${title}</h2>${o.sub ? `<span class="sub">${o.sub}</span>` : ""}${o.actions || ""}</header>${body}</section>`;
const kpi = (l, v, d) => `<div class="card kpi"><div class="l">${esc(l)}</div><div class="v">${v}</div>${d ? `<div class="d">${d}</div>` : ""}</div>`;
const head = (t, lede, right = "") => `<div class="page-head"><div><h1>${esc(t)}</h1>${lede ? `<p class="lede">${lede}</p>` : ""}</div>${right}</div>`;
const skeleton = () => `<div class="skel"></div><div class="skel"></div><div class="skel" style="height:240px"></div>`;
function bars(items, o = {}) {
  const max = o.max || Math.max(...items.map(i => i.v), 1e-9), f = o.fmt || num;
  return `<div class="bars">${items.map(i => `<div class="bar"><span class="n" title="${esc(i.n)}">${esc(i.n)}</span><span class="t"><span class="f" style="width:${Math.max(0, i.v / max * 100)}%;${i.c ? `--bc:${i.c}` : ""}"></span></span><span class="v">${f(i.v)}</span></div>`).join("")}</div>`;
}
const TIERC = { A: "var(--tA)", B: "var(--tB)", C: "var(--tC)", D: "var(--tD)" };
const PALETTE = ["#6366f1", "#12a150", "#c27803", "#d92d3a", "#0ea5e9", "#a855f7", "#76809a"];
function donut(items) {
  const tot = items.reduce((a, b) => a + b.v, 0) || 1; let off = 0; const R = 42, C = 2 * Math.PI * R;
  const arcs = items.map((i, k) => { const len = i.v / tot * C, s = `<circle r="${R}" cx="60" cy="60" fill="none" stroke="${PALETTE[k % PALETTE.length]}" stroke-width="18" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-off}" transform="rotate(-90 60 60)"><title>${esc(label(i.n))}: ${num(i.v)}</title></circle>`; off += len; return s; }).join("");
  return `<div class="donut"><svg viewBox="0 0 120 120" width="150" height="150" role="img" aria-label="Donut chart">${arcs}<text x="60" y="58" text-anchor="middle" font-size="16" font-weight="700" fill="currentColor">${num(tot)}</text><text x="60" y="72" text-anchor="middle" font-size="8" fill="var(--mu)">total</text></svg>
  <div class="legend">${items.map((i, k) => `<div><span><span class="sw" style="background:${PALETTE[k % PALETTE.length]}"></span>${esc(cap(i.n))}</span><b>${num(i.v)} <span class="muted">(${pct(i.v / tot, 0)})</span></b></div>`).join("")}</div></div>`;
}
function columns(groups, series, o = {}) { // groups: [{x, vals:[..]}]; series: [{name,color}]
  const nice = v => { const e = 10 ** Math.floor(Math.log10(v)), f = v / e; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * e; };
  const W = 620, H = 230, L = 50, B = 28, T = 10, max = nice(Math.max(...groups.flatMap(g => g.vals), 1e-9)), n = groups.length, gw = (W - L) / n, bw = Math.min(26, gw / (series.length + 1));
  const fmt = o.fmt || num, tick = o.tick || (o.fmt ? o.fmt : v => v >= 1000 ? +(v / 1000).toFixed(1) + "k" : Math.round(v));
  const grid = [0, .2, .4, .6, .8, 1].map(f => { const y = T + (H - B - T) * (1 - f); return `<line x1="${L}" x2="${W}" y1="${y}" y2="${y}" stroke="var(--line)"/><text x="${L - 6}" y="${y + 4}" text-anchor="end">${tick(max * f)}</text>`; }).join("");
  const bs = groups.map((g, i) => g.vals.map((v, k) => { const h = (H - B - T) * v / max, x = L + i * gw + gw / 2 - bw * series.length / 2 + k * bw; return `<rect x="${x}" y="${H - B - h}" width="${bw - 3}" height="${Math.max(h, 0)}" rx="3" fill="${series[k].color}"><title>${esc(g.x)} · ${esc(series[k].name)}: ${fmt(v)}</title></rect>`; }).join("") + `<text x="${L + i * gw + gw / 2}" y="${H - 8}" text-anchor="middle">${esc(g.x)}</text>`).join("");
  const lg = series.length > 1 ? `<div class="legend" style="display:flex;gap:16px;margin-top:6px">${series.map(s => `<span><span class="sw" style="background:${s.color}"></span>${esc(s.name)}</span>`).join("")}</div>` : "";
  return `<svg class="cols" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.aria || "Column chart")}">${grid}${bs}</svg>${lg}`;
}
function ring(score, tier) {
  const R = 42, C = 2 * Math.PI * R, v = score == null ? 0 : score / 100;
  return `<div class="ring" role="img" aria-label="Score ${score ?? "none"} of 100"><svg viewBox="0 0 100 100" width="96" height="96"><circle cx="50" cy="50" r="${R}" fill="none" stroke="var(--surface2)" stroke-width="9"/><circle cx="50" cy="50" r="${R}" fill="none" stroke="${TIERC[tier] || "var(--mu)"}" stroke-width="9" stroke-linecap="round" stroke-dasharray="${v * C} ${C}" transform="rotate(-90 50 50)"/></svg><b>${score ?? "–"}</b></div>`;
}
function table(cols, rows, o = {}) {
  return `<div class="tbl-wrap"><table><thead><tr>${cols.map(c => `<th scope="col" ${c.num ? 'class="num"' : ""}>${c.sort ? `<button data-sort="${c.sort}" aria-label="Sort by ${esc(c.h)}">${esc(c.h)} ${o.sort === c.sort ? (o.dir === "asc" ? "▲" : "▼") : ""}</button>` : esc(c.h)}</th>`).join("")}</tr></thead>
  <tbody>${rows.length ? rows.map(r => `<tr${r.href ? ` class="click" data-href="${esc(r.href)}"` : ""}>${r.cells.map((c, i) => `<td ${cols[i].num ? 'class="num"' : ""}>${c}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${cols.length}" class="empty">${o.empty || "No results"}</td></tr>`}</tbody></table></div>`;
}
const pager = (p, id = "pg") => `<div class="pager"><span>${num(p.total)} result${p.total === 1 ? "" : "s"} · page ${p.page} of ${p.pages}</span><div><button class="btn" data-pg="${p.page - 1}" ${p.page <= 1 ? "disabled" : ""}>← Previous</button><button class="btn" data-pg="${p.page + 1}" ${p.page >= p.pages ? "disabled" : ""}>Next →</button></div></div>`;
function wireRows(root) { $$("tr.click", root).forEach(tr => tr.addEventListener("click", e => { if (e.target.closest("a,button")) return; location.hash = tr.dataset.href; })); }
function copyBtn(text) { return `<button class="btn" data-copy="${esc(text)}" aria-label="Copy command">Copy</button>`; }
document.addEventListener("click", e => { const b = e.target.closest("[data-copy]"); if (b) { navigator.clipboard?.writeText(b.dataset.copy).then(() => toast("Copied to clipboard"), () => toast("Copy failed")); } });
const leadLink = id => `<a class="mono" href="#/leads/${esc(id)}">${esc(id)}</a>`;

/* ======================= VIEWS ======================= */
const V = $("#view");

async function dashboard() {
  const o = await cached("overview", "overview"), c = o.counts, f = o.funnel;
  const stOrder = ["Converted", "Qualified", "Working", "New", "Stale", "Disqualified", "Duplicate"];
  const status = stOrder.filter(k => o.status[k]).map(k => ({ n: k, v: o.status[k] }));
  V.innerHTML = head("Dashboard", `Synthetic lead-to-opportunity dataset as of <b>${esc(day(o.as_of))}</b>. Everything here is computed from the exported files.`) +
    `<div class="kpis">${kpi("Leads", num(c.leads), `${num(o.duplicates)} duplicates merged`)}${kpi("Opportunities", num(c.opportunities), `${num(o.opp_status.open || 0)} still open`)}
    ${kpi("Win rate (closed)", pct(o.win_rate), `${num(o.opp_status.won)} won · ${num(o.opp_status.lost)} lost`)}${kpi("Won value", usd(o.opp_value.won), "closed-won amount")}
    ${kpi("Activities", num(c.activities), `${num(c.tasks)} follow-up tasks`)}${kpi("Opted-out contacts", num(o.consent.opted_out_contacts), `${num(o.consent.opt_out_events)} opt-out events`)}</div>` +
    card("Conversion funnel", `<div class="funnel">${f.map((s, i) => `<div class="row"><span>${esc(s.label)}</span><span class="t"><span class="f" style="display:block;width:${s.value / f[0].value * 100}%"></span></span><span class="v"><b>${num(s.value)}</b>${i ? `<small>${pct(s.value / f[i - 1].value, 0)} of previous</small>` : `<small>start</small>`}</span></div>`).join("")}</div>`, { sub: "reconciles: master + duplicates = leads; open + won + lost = opportunities", cls: "" }) +
    `<div class="grid g2" style="margin-top:16px">` +
    card("Leads and opportunities by month", columns(o.monthly.map(m => ({ x: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][+m.month.slice(5) - 1], vals: [m.leads, m.opportunities] })), [{ name: "Leads created", color: "#6366f1" }, { name: "Opportunities created", color: "#12a150" }], { aria: "Leads and opportunities per month" })) +
    card("Lead status", donut(status), { sub: "derived snapshot" }) +
    card("Score tiers", bars(Object.entries(o.tiers).map(([k, v]) => ({ n: "Tier " + k, v, c: TIERC[k] }))), { sub: "initial score, 14 days after creation" }) +
    card("Conversion by source", bars(o.sources.sort((a, b) => b.rate - a.rate).map(s => ({ n: label(s.source), v: s.rate })), { fmt: v => pct(v), max: Math.max(...o.sources.map(s => s.rate)) }), { sub: "non-duplicate leads → opportunity" }) +
    card("Leads by territory", bars(Object.entries(o.territories).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ n: k, v })))) +
    card("Follow-up tasks", bars(Object.entries(o.tasks).map(([k, v]) => ({ n: cap(k), v })), {}), { sub: "consent-gated; cancelled = no consent" }) + `</div>`;
}

const LQ = { q: "", tier: "", status: "", source: "", territory: "", product: "", flag: "", sort: "created", dir: "desc", page: 1 };
async function leads(m, params) {
  const o = await cached("overview", "overview");
  for (const k of Object.keys(LQ)) if (params.has(k)) LQ[k] = k === "page" ? +params.get(k) : params.get(k);
  const opt = (arr, cur, all) => `<option value="">${all}</option>` + arr.map(x => `<option value="${esc(x)}" ${cur === x ? "selected" : ""}>${esc(label(x))}</option>`).join("");
  const flags = [["", "All leads"], ["duplicate", "Duplicates"], ["opted_out", "Opted out"], ["has_opportunity", "Has opportunity"], ...(state.truth ? [["high_score_non_converter", "High-score non-converters (truth)"], ["has_anomaly", "Injected edge cases (truth)"]] : [])];
  V.innerHTML = head("Leads", "Search, filter and open any lead to see exactly why it scored the way it did.") +
    `<div class="filters" role="group" aria-label="Lead filters"><input class="f" type="search" id="f-q" placeholder="Search id, company, name, email" aria-label="Search leads" value="${esc(LQ.q)}" style="min-width:240px">
    <select id="f-tier" aria-label="Tier">${opt(["A", "B", "C", "D"], LQ.tier, "All tiers")}</select>
    <select id="f-status" aria-label="Status">${opt(["New", "Working", "Qualified", "Converted", "Disqualified", "Duplicate", "Stale"], LQ.status, "All statuses")}</select>
    <select id="f-source" aria-label="Source">${opt(o.sources.map(s => s.source), LQ.source, "All sources")}</select>
    <select id="f-territory" aria-label="Territory">${opt(Object.keys(o.territories).sort(), LQ.territory, "All territories")}</select>
    <select id="f-product" aria-label="Product">${opt(Object.keys(o.products).sort(), LQ.product, "All products")}</select>
    <select id="f-flag" aria-label="Special filter">${flags.map(([v, t]) => `<option value="${v}" ${LQ.flag === v ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>
    <button class="btn" id="f-reset">Reset</button></div><div id="lt"></div>`;
  const bind = (id, key) => $(id).addEventListener("change", e => { LQ[key] = e.target.value; LQ.page = 1; load(); });
  [["#f-tier", "tier"], ["#f-status", "status"], ["#f-source", "source"], ["#f-territory", "territory"], ["#f-product", "product"], ["#f-flag", "flag"]].forEach(a => bind(...a));
  let t; $("#f-q").addEventListener("input", e => { clearTimeout(t); t = setTimeout(() => { LQ.q = e.target.value; LQ.page = 1; load(); }, 250); });
  $("#f-reset").addEventListener("click", () => { Object.assign(LQ, { q: "", tier: "", status: "", source: "", territory: "", product: "", flag: "", sort: "created", dir: "desc", page: 1 }); leads(m, new URLSearchParams()); });
  await load();
  async function load() {
    const box = $("#lt"); if (!box) return;
    const qs = new URLSearchParams({ ...LQ, size: 20 }); if (state.truth) qs.set("truth", "1");
    const r = await api("leads?" + qs);
    const cols = [{ h: "Lead", sort: "lead_id" }, { h: "Company · contact", sort: "company" }, { h: "Source" }, { h: "Territory" }, { h: "Score", sort: "score" }, { h: "Status", sort: "status" }, { h: "Opportunity" }, ...(state.truth ? [] : [{ h: "Rep" }]), { h: "Created", sort: "created" }];
    if (state.truth) cols.push({ h: "Truth" });
    const rows = r.rows.map(x => ({
      href: "#/leads/" + x.lead_id, cells: [leadLink(x.lead_id), `<b>${esc(x.company)}</b><div class="muted sm">${esc(x.contact)} · ${esc(x.email)}</div>`, esc(label(x.source)) + `<div class="muted sm">${esc(x.product)}</div>`, esc(x.territory),
      x.tier ? `${tierPill(x.tier)} <b>${x.score}</b>` : `<span class="muted sm">merged</span>`, stPill(x.status), x.opp_id ? `${oPill(x.opp_status)}<div class="muted sm">${esc(x.opp_stage)} · ${usd(x.amount)}</div>` : `<span class="muted">–</span>`, ...(state.truth ? [] : [`<span class="sm">${esc(x.rep)}</span>`]), day(x.created),
      ...(state.truth ? [`${x.truth.converted ? '<span class="tag">converted</span> ' : ""}${x.truth.blocker ? `<span class="tag warn">${esc(label(x.truth.blocker))}</span> ` : ""}${x.truth.anomalies.map(a => `<span class="tag bad">${esc(label(a))}</span>`).join(" ")}`] : [])]
    }));
    box.innerHTML = table(cols, rows, { sort: LQ.sort, dir: LQ.dir, empty: "No leads match these filters." }) + pager(r);
    wireRows(box);
    $$("[data-sort]", box).forEach(b => b.addEventListener("click", () => { const k = b.dataset.sort; LQ.dir = LQ.sort === k && LQ.dir === "desc" ? "asc" : "desc"; LQ.sort = k; load(); }));
    $$("[data-pg]", box).forEach(b => b.addEventListener("click", () => { LQ.page = +b.dataset.pg; load(); box.scrollIntoView({ block: "start" }); }));
  }
}

const ACT_ICON = { form_submit: "Form submitted", web_visit: "Web visit", pricing_page_visit: "Pricing page visit", content_download: "Content download", demo_request: "Demo requested", email_open: "Email opened", email_click: "Email link clicked", email_outbound: "Email sent", call_outbound: "Call made", demo_delivered: "Demo delivered", proposal_sent: "Proposal sent", meeting: "Meeting held" };
async function leadDetail(m) {
  const id = decodeURIComponent(m[1]);
  const d = await api(`leads/${encodeURIComponent(id)}?${truthQ().slice(1)}`);
  const l = d.lead, c = d.company, ct = d.contact, r = d.row, o = d.opportunity;
  const failed = d.checks.filter(x => x.status === "fail").length;
  const checks = `<ul class="checks">${d.checks.map(x => `<li style="--c:var(--${x.status === "pass" ? "ok" : "bad"})"><span class="ic" aria-hidden="true">${x.status === "pass" ? "✓" : "✕"}</span><div><b>${esc(x.name)}</b> <span class="sr" style="position:absolute;left:-9999px">${x.status === "pass" ? "passed" : "failed"}</span><div class="muted sm">${esc(x.detail)}</div></div></li>`).join("")}</ul>`;
  const truth = d.truth ? `<div class="truth"><h3>Ground truth (separate from input data, never a feature)</h3><div class="facts"><div><dt>Converted</dt><dd>${d.truth.labels.converted === "1" ? "Yes" : "No"}</dd></div><div><dt>Eventual outcome</dt><dd>${esc(d.truth.labels.eventual_outcome)}</dd></div><div><dt>Hidden blocker</dt><dd>${esc(label(d.truth.labels.hidden_blocker || "none"))}</dd></div><div><dt>Split</dt><dd>${esc(d.truth.labels.holdout_split)}</dd></div><div><dt>High-score non-converter</dt><dd>${d.truth.labels.is_high_score_non_converter === "1" ? "Yes" : "No"}</dd></div></div>
  ${d.truth.anomalies.length ? `<h3 style="margin-top:12px">Injected edge cases on this lead</h3><ul class="checks">${d.truth.anomalies.map(a => `<li style="--c:var(--warn)"><span class="ic">!</span><div><b>${esc(label(a.issue_type))}</b> <span class="mono muted">${esc(a.record_id)}</span><div class="muted sm">${esc(a.description)}</div></div></li>`).join("")}</ul>` : `<p class="muted sm" style="margin-bottom:0">No injected edge case on this lead.</p>`}</div>` : "";
  V.innerHTML = `<a class="crumb" href="#/leads">${icon("back", 16)} All leads</a>` + truth +
    `<section class="card" style="margin-bottom:16px"><div style="display:flex;gap:20px;align-items:center;flex-wrap:wrap">${ring(r.score, r.tier)}<div style="flex:1;min-width:220px"><h1 class="mono" style="font-size:20px">${esc(l.lead_id)}</h1><div style="margin:6px 0">${stPill(l.status)} ${r.tier ? tierPill(r.tier) : ""} ${d.duplicate_of ? `<span class="tag warn">duplicate of ${esc(d.duplicate_of)}</span>` : ""} ${r.opted_out ? '<span class="tag bad">opted out</span>' : ""}</div><div class="muted">${esc(c.company_name)} · ${esc(ct.first_name)} ${esc(ct.last_name)} (${esc(label(ct.seniority))}) · ${esc(ct.email)}</div></div></div>
    <dl class="facts" style="margin:18px 0 0"><div><dt>Source</dt><dd>${esc(label(l.source))}</dd></div><div><dt>Campaign</dt><dd>${esc(d.campaign ? d.campaign.campaign_name : "None (organic)")}</dd></div><div><dt>Product</dt><dd>${esc(l.product_interest)}</dd></div><div><dt>Territory</dt><dd>${esc(l.territory)}</dd></div><div><dt>Rep</dt><dd>${esc(d.rep.rep_name)} <span class="muted sm">${esc(d.rep.rep_id)}</span></dd></div><div><dt>Created</dt><dd>${dt(l.created_at)}</dd></div><div><dt>Company size</dt><dd>${esc(c.employee_band)} · ${esc(c.industry)}</dd></div><div><dt>Activities</dt><dd>${num(d.activities.length)}</dd></div></dl></section>` +
    `<div class="grid g2">` + card("Record checks", checks, { sub: failed ? `<span class="pill fail">${failed} failed</span>` : `<span class="pill pass">all passed</span>` }) + `<div id="score-card"></div></div>` +
    (o ? `<div style="margin-top:16px">${oppCard(d)}</div>` : "") +
    `<div class="grid g2" style="margin-top:16px">${card("Follow-up tasks", table([{ h: "Task" }, { h: "Due" }, { h: "Status" }], d.tasks.map(t => ({ cells: [`${esc(cap(t.task_type))} <span class="muted sm">${esc(t.priority)}</span>`, day(t.due_at), `${pill(t.status, t.status === "completed" ? "pass" : t.status === "cancelled" ? "fail" : "st-new")}${t.cancel_reason ? ` <span class="muted sm">${esc(label(t.cancel_reason))}</span>` : ""}`] })), { empty: "No tasks (tier D, or a merged duplicate)." }))}${card("Consent timeline", consentCard(d.consent))}</div>` +
    `<div style="margin-top:16px" id="tl-card"></div>` +
    (d.duplicates.length || d.other_leads.length ? `<div style="margin-top:16px">${card("Related leads", `${d.duplicates.length ? `<p>Duplicates of this lead: ${d.duplicates.map(leadLink).join(", ")}</p>` : ""}${d.other_leads.length ? `<p>Other leads from the same contact: ${d.other_leads.map(leadLink).join(", ")}</p>` : ""}`)}</div>` : "");
  scoreCard(d, d.scores.length ? 0 : -1); timeline(d, "all");
}
function oppCard(d) {
  const o = d.opportunity, reached = new Set(o.stages.map(s => s.to_stage)), at = Object.fromEntries(o.stages.map(s => [s.to_stage, s.changed_at]));
  const order = ["Qualification", "Discovery", "Proposal", "Negotiation"], last = o.current_stage, closed = o.status !== "open";
  const idx = Math.max(...[...reached].map(s => order.indexOf(s)));
  const steps = order.map((s, i) => { const miss = !reached.has(s) && (i < idx || closed && i < 3 && o.status === "won"); return `<div class="step ${reached.has(s) ? "done" : miss ? "missing" : ""}"><b>${s}</b>${reached.has(s) ? day(at[s]) : miss ? "event missing" : "not reached"}</div>`; }).join("") +
    `<div class="step ${o.status === "won" ? "done" : o.status === "lost" ? "lost" : ""}"><b>${closed ? "Closed " + cap(o.status) : "Open"}</b>${closed ? day(o.closed_at) : esc(last)}</div>`;
  return card(`Opportunity <span class="mono">${esc(o.opportunity_id)}</span>`, `<div class="steps">${steps}</div><p class="muted sm" style="margin:12px 0 0">${oPill(o.status)} ${usdFull(o.amount_usd)} · ${esc(o.product)}${o.outcome_reason ? ` · reason: <b>${esc(label(o.outcome_reason))}</b>` : ""} · ${o.stages.length} stage-history events (append-only)</p>`);
}
function consentCard(rows) {
  if (!rows.length) return '<p class="muted">No consent records.</p>';
  const t0 = Math.min(...rows.map(r => +new Date(r.effective_from))), t1 = +new Date(AS_OF), span = Math.max(t1 - t0, 1);
  return ["email", "phone"].map(ch => { const rs = rows.filter(r => r.channel === ch).sort((a, b) => a.effective_from.localeCompare(b.effective_from)); if (!rs.length) return `<div class="sm"><b>${cap(ch)}</b> <span class="muted">no consent ever recorded → no outbound contact allowed</span></div>`;
    return `<div class="sm"><b>${cap(ch)}</b></div><div class="seg" role="img" aria-label="${ch} consent timeline">${rs.map(r => { const a = +new Date(r.effective_from), b = r.effective_to ? +new Date(r.effective_to) : t1; return `<i class="${r.status}" style="width:${Math.max((b - a) / span * 100, 1.5)}%" title="${esc(r.status)} ${day(r.effective_from)} → ${r.effective_to ? day(r.effective_to) : "now"}"></i>`; }).join("")}</div>
    <div class="sm muted" style="margin-bottom:8px">${rs.map(r => `${r.status === "opt_in" ? "✓ opt-in" : "✕ opt-out"} ${day(r.effective_from)} (${esc(label(r.capture_method))})`).join(" → ")}</div>`; }).join("");
}
function scoreCard(d, i) {
  const box = $("#score-card"); if (!box) return;
  if (i < 0) { box.innerHTML = card("Score breakdown", '<p class="muted">Duplicate leads are merged into their master and are not scored.</p>'); return; }
  const s = d.scores[i], opp = d.opportunity, post = opp && s.scored_at >= opp.created_at;
  const groups = ["fit", "intent", "engagement"].map(cat => { const cs = s.components.filter(x => x.category === cat); return { cat, cs, tot: cs.reduce((a, b) => a + b.points, 0) }; });
  const max = Math.max(...s.components.map(x => Math.abs(x.points)), 1);
  const tabs = d.scores.length > 1 ? `<div style="display:flex;gap:6px;margin-bottom:10px">${d.scores.map((x, k) => `<button class="chip" data-sc="${k}" aria-pressed="${k === i}">${esc(cap(x.trigger))} · ${day(x.scored_at)}</button>`).join("")}</div>` : "";
  box.innerHTML = card("Score breakdown", tabs + (post ? `<p class="tag bad" style="display:block;margin-bottom:10px">Computed after the opportunity existed: uses post-conversion events (leakage)</p>` : "") +
    `<p class="muted sm" style="margin-top:0">Rule set v${esc(s.rule_version)} · scored ${dt(s.scored_at)} · raw ${s.raw_score} → <b>${s.total_score}</b> (${tierPill(s.tier)})</p>` +
    groups.map(g => `<h3 style="margin-top:12px">${cap(g.cat)} <span class="muted">${g.tot > 0 ? "+" : ""}${g.tot}</span></h3>` + (g.cs.length ? `<div class="bars wrap">${g.cs.map(x => `<div class="bar"><span class="n" title="${esc(x.description)}">${esc(x.description)}${x.units > 1 ? " ×" + x.units : ""}</span><span class="t"><span class="f" style="width:${Math.abs(x.points) / max * 100}%;--bc:${x.points < 0 ? "var(--bad)" : "var(--ac)"}"></span></span><span class="v" style="color:var(--${x.points < 0 ? "bad" : "ok"})">${x.points > 0 ? "+" : ""}${x.points}</span></div>`).join("")}</div>` : '<p class="muted sm">No rule matched.</p>')).join(""), { sub: "every point traces to a ScoreRule" });
  $$("[data-sc]", box).forEach(b => b.addEventListener("click", () => scoreCard(d, +b.dataset.sc)));
}
function timeline(d, filt, all) {
  const box = $("#tl-card"); if (!box) return;
  let acts = d.activities.filter(a => filt === "all" || a.direction === filt); const total = acts.length; if (!all) acts = acts.slice(0, 40);
  box.innerHTML = card("Activity history", `<div style="display:flex;gap:6px;margin-bottom:14px">${["all", "inbound", "outbound"].map(f => `<button class="chip" data-f="${f}" aria-pressed="${f === filt}">${cap(f)}</button>`).join("")}</div>
    <ol class="tl">${acts.map(a => `<li class="${!a.consent_ok ? "bad" : a.direction === "outbound" ? "out" : "in"}"><b>${esc(ACT_ICON[a.activity_type] || label(a.activity_type))}</b> <span class="muted sm">${esc(a.direction)} · ${esc(a.channel)}</span>${a.rep_id ? ` <span class="muted sm">by ${esc(a.rep_id)}</span>` : ""}${!a.consent_ok ? ' <span class="tag bad">no active consent</span>' : ""}<time>${dt(a.occurred_at)} · ${esc(a.activity_id)}</time></li>`).join("") || '<li class="muted">No activity.</li>'}</ol>
    ${total > acts.length ? `<button class="btn" id="tl-all" style="margin-top:12px">Show all ${num(total)}</button>` : ""}`, { sub: `${num(total)} events · green inbound, indigo outbound, red = outbound without consent` });
  $$("[data-f]", box).forEach(b => b.addEventListener("click", () => timeline(d, b.dataset.f))); $("#tl-all", box)?.addEventListener("click", () => timeline(d, filt, true));
}

async function pipeline(m, params) {
  const st = { stage: params.get("stage") || "", status: params.get("status") || "", page: 1 };
  V.innerHTML = head("Pipeline", "Opportunities by current stage. Stage history is append-only, so every transition is traceable.") + `<div id="pstages" class="kpis"></div><div class="filters"><select id="p-status" aria-label="Status"><option value="">All statuses</option><option value="open">Open</option><option value="won">Won</option><option value="lost">Lost</option></select><select id="p-prod" aria-label="Product"><option value="">All products</option>${["Platform", "Analytics", "Automation", "Security"].map(p => `<option>${p}</option>`).join("")}</select></div><div id="pt"></div>`;
  $("#p-status").value = st.status; st.product = "";
  $("#p-status").addEventListener("change", e => { st.status = e.target.value; st.stage = ""; st.page = 1; load(); }); $("#p-prod").addEventListener("change", e => { st.product = e.target.value; st.page = 1; load(); });
  await load();
  async function load() {
    const r = await api("opportunities?" + new URLSearchParams({ ...st, size: 15 }));
    $("#pstages").innerHTML = r.stages.map(s => `<button class="card kpi" data-stage="${esc(s.stage)}" style="text-align:left;cursor:pointer;font:inherit;color:inherit;${st.stage === s.stage ? "border-color:var(--ac)" : ""}" aria-pressed="${st.stage === s.stage}"><div class="l">${esc(s.stage)}</div><div class="v">${num(s.count)}</div><div class="d">${usd(s.amount)}</div></button>`).join("");
    $$("[data-stage]").forEach(b => b.addEventListener("click", () => { st.stage = st.stage === b.dataset.stage ? "" : b.dataset.stage; st.page = 1; load(); }));
    const box = $("#pt");
    box.innerHTML = table([{ h: "Opportunity" }, { h: "Lead" }, { h: "Company" }, { h: "Product" }, { h: "Amount", num: 1 }, { h: "Stage" }, { h: "Status" }, { h: "Rep" }, { h: "Created" }],
      r.rows.map(x => ({ href: "#/leads/" + x.lead_id, cells: [`<span class="mono">${esc(x.opp_id)}</span>`, leadLink(x.lead_id), esc(x.company), esc(x.product), usdFull(x.amount), esc(x.opp_stage), oPill(x.opp_status), `<span class="sm">${esc(x.rep)}</span>`, day(x.created)] })), { empty: "No opportunities match." }) + pager(r);
    wireRows(box); $$("[data-pg]", box).forEach(b => b.addEventListener("click", () => { st.page = +b.dataset.pg; load(); }));
  }
}

async function model() {
  const [e, dict] = await Promise.all([cached("evaluation", "evaluation"), cached("dictionary", "dictionary")]);
  const t = e.tier_conversion_rate_test, tr = e.tier_conversion_rate_train;
  const ver = +(ls.get("rulever", "2"));
  const rules = dict.rules.filter(r => +r.rule_version === ver);
  V.innerHTML = head("Scoring model", "A transparent, versioned, rule-based score evaluated on <b>held-out</b> leads: trained on early leads, tested on later ones. Labels come from the separate ground-truth files.") +
    `<div class="kpis">${kpi("Held-out AUC", e.auc_test_heldout, `train ${e.auc_train}`)}${kpi("Top-decile lift", e.top_decile_lift_test + "×", `precision ${pct(e.top_decile_precision_test)}`)}${kpi("Test leads", num(e.n_test), `${num(e.n_train)} train`)}${kpi("Test conversion", pct(e.test_conversion_rate), `overall ${pct(e.overall_conversion_rate)}`)}</div>
    <div class="grid g2">${card("Conversion rate by score decile (test)", columns(e.score_deciles_test.map(d => ({ x: "D" + d.decile, vals: [d.conversion_rate] })), [{ name: "Conversion rate", color: "#6366f1" }], { fmt: v => pct(v, 0), aria: "Conversion rate by score decile" }), { sub: "monotone rise = the score ranks leads usefully" })}
    ${card("Tier calibration", table([{ h: "Tier" }, { h: "Share", num: 1 }, { h: "Train rate", num: 1 }, { h: "Test rate", num: 1 }], ["A", "B", "C", "D"].map(k => ({ cells: [tierPill(k), pct(e.tier_share_test[k]), pct(tr[k]), `<b>${pct(t[k])}</b>`] }))) + `<h3 style="margin-top:16px">AUC by score category (test)</h3>` + bars(Object.entries(e.auc_by_score_category_test).map(([k, v]) => ({ n: cap(k), v })), { max: 1, fmt: v => v.toFixed(3) }))}
    ${card("Why high scores sometimes don't convert", `<p style="margin-top:0">${num(e.high_score_non_converters)} tier-A leads never converted. The score cannot see <i>hidden blockers</i>; the ground truth records them:</p>` + bars(Object.entries(e.high_score_non_converters_by_hidden_blocker).map(([k, v]) => ({ n: k === "none" ? "No blocker (chance)" : cap(k), v }))), { sub: "ground truth" })}
    ${card("Leakage guard", `<p style="margin-top:0">Evaluation uses only <code>trigger = initial</code> scores. ${num(e.leakage_demo.leaked_rescore_leads)} leads carry an injected rescore that counts post-conversion events (mean score ${e.leakage_demo.mean_initial_score} → ${e.leakage_demo.mean_leaked_latest_score}). Using the latest score would change test AUC from <b>${e.auc_test_heldout}</b> to <b>${e.auc_test_if_latest_score_used}</b>.</p>`)}</div>` +
    `<div style="margin-top:16px">${card("Scoring rules", `<div style="display:flex;gap:6px;margin-bottom:12px">${[1, 2].map(v => `<button class="chip" data-v="${v}" aria-pressed="${v === ver}">Rule set v${v}</button>`).join("")}</div><p class="muted sm" style="margin-top:0">Effective ${day(rules[0].effective_from)} → ${rules[0].effective_to ? day(rules[0].effective_to) + " (exclusive)" : "open-ended"}. Tiers: ${dict.tier_thresholds.map(([t, n]) => `${t} ≥ ${n}`).join(" · ")}. Score is clamped to 0–100.</p>` +
      table([{ h: "Rule" }, { h: "Category" }, { h: "Condition" }, { h: "Points", num: 1 }], rules.map(r => ({ cells: [esc(r.description), esc(cap(r.category)), `<span class="mono">${esc(r.feature)} ${r.operator === "eq" ? "=" : r.operator === "gte" ? "≥" : "per unit"} ${r.operator === "per_unit" ? "(max " + esc(r.cap_units) + ")" : esc(r.value)}</span>`, `<b style="color:var(--${+r.points < 0 ? "bad" : "ok"})">${+r.points > 0 ? "+" : ""}${esc(r.points)}</b>`] }))))}</div>`;
  $$("[data-v]").forEach(b => b.addEventListener("click", () => { ls.set("rulever", b.dataset.v); model(); }));
}

async function quality() {
  const v = await api("validation"), ok = v.overall === "PASS", cats = [...new Set(v.checks.map(c => c.category))];
  let cat = "", q = "";
  const render = () => {
    const rows = v.checks.filter(c => (!cat || c.category === cat) && c.name.toLowerCase().includes(q));
    $("#qt").innerHTML = table([{ h: "Category" }, { h: "Check" }, { h: "Violations", num: 1 }, { h: "Result" }], rows.map(c => ({ cells: [`<span class="tag">${esc(label(c.category))}</span>`, esc(c.name), num(c.violations), pill(c.status, c.status === "PASS" ? "pass" : "fail")] })));
  };
  V.innerHTML = head("Data quality", "Independent validator: reads only the exported CSVs, then re-derives scores, duplicates, statuses and consent from source rows.", `<button class="btn primary" id="rerun">Re-run validation</button>`) +
    `<div class="banner" style="--c:var(--${ok ? "ok" : "bad"})"><div class="big">${ok ? "✓ PASS" : "✕ FAIL"}</div><div><b>${v.invariants_passed}/${v.invariants_total}</b> invariants hold · <b>${v.detectors_matching_ground_truth}/${v.detectors_total}</b> injected edge cases detected exactly as labelled</div></div>
    <div class="grid">${card("Injected edge cases: detector vs ground truth", table([{ h: "Edge case" }, { h: "Expected", num: 1 }, { h: "Detected", num: 1 }, { h: "Missing", num: 1 }, { h: "Extra", num: 1 }, { h: "Result" }], v.detectors.map(d => ({ cells: [esc(cap(d.issue_type)), num(d.expected), num(d.detected), num(d.missing), num(d.unexpected), pill(d.status, d.status === "PASS" ? "pass" : "fail")] }))), { sub: "must match exactly" })}
    ${card("Funnel reconciliation", `<dl class="facts">${Object.entries(v.funnel).map(([k, x]) => `<div><dt>${esc(label(k))}</dt><dd>${num(x)}</dd></div>`).join("")}</dl>`)}</div>
    <div style="margin-top:16px">${card("Invariant checks", `<div class="filters"><input class="f" id="qq" type="search" placeholder="Filter checks" aria-label="Filter checks"><span id="cats"></span></div><div id="qt"></div>`, { sub: "zero violations required" })}</div>`;
  $("#cats").innerHTML = [["", "All"], ...cats.map(c => [c, cap(c)])].map(([k, t]) => `<button class="chip" data-c="${esc(k)}" aria-pressed="${k === ""}">${esc(t)}</button>`).join(" ");
  $$("[data-c]").forEach(b => b.addEventListener("click", () => { cat = b.dataset.c; $$("[data-c]").forEach(x => x.setAttribute("aria-pressed", x === b)); render(); }));
  $("#qq").addEventListener("input", e => { q = e.target.value.toLowerCase(); render(); }); render();
  $("#rerun").addEventListener("click", async e => { e.target.disabled = true; e.target.textContent = "Validating…"; try { await api("revalidate", { method: "POST" }); delete cache.evaluation; toast("Validation re-run complete"); } catch (er) { toast("Failed: " + er.message); } quality(); });
}

const EDGE = {
  opted_out_lead_contacted: ["Opted-out lead contacted", "An outbound email was sent after the contact withdrew consent.", "Outbound activity with no active opt-in at its timestamp."],
  score_uses_post_conversion_event: ["Score uses post-conversion event", "A late rescore counted activity that happened after the opportunity was created (target leakage).", "LeadScore.scored_at later than Opportunity.created_at."],
  lead_assigned_outside_territory: ["Lead assigned outside territory", "The lead was routed to a rep who does not cover its territory × product.", "Assigned rep missing from RepCoverage for that territory and product."],
  duplicate_creates_duplicate_opportunity: ["Duplicate creates duplicate opportunity", "A duplicate lead produced its own opportunity although its master already converted.", "Opportunity whose lead is flagged as a duplicate."],
  stage_history_gap: ["Stage history has gaps", "One transition event is missing from an opportunity's history.", "Sequence numbers not consecutive, or from_stage ≠ previous to_stage."],
  duplicate_contact: ["Duplicate contact", "Same person entered twice with a different email spelling.", "Same normalised email (lower-case, +tag removed)."],
  duplicate_lead: ["Duplicate lead", "Same person and product within 90 days of an earlier lead.", "Same master contact + product within the dedupe window."],
};
async function edgeCases(m, params) {
  const a = await api("anomalies"); let type = params.get("type") || "", page = 1; const per = 15;
  V.innerHTML = head("Edge cases", "Deliberately injected, <b>labelled</b> exceptions. They are recorded in <code>ground_truth/anomalies.csv</code>; baseline rows are never silently corrupted.") +
    `<div class="grid g3">${Object.entries(a.counts).map(([k, n]) => { const e = EDGE[k] || [cap(k), "", ""]; return `<button class="card" data-t="${esc(k)}" aria-pressed="${type === k}" style="text-align:left;font:inherit;color:inherit;cursor:pointer;${type === k ? "border-color:var(--ac)" : ""}"><div class="kpi"><div class="v">${num(n)}</div></div><h3 style="margin:6px 0 4px">${esc(e[0])}</h3><div class="muted sm">${esc(e[1])}</div><div class="sm" style="margin-top:8px"><b>Detected by:</b> ${esc(e[2])}</div></button>`; }).join("")}</div><div style="margin-top:16px" id="et"></div>`;
  const draw = () => {
    const rows = a.rows.filter(r => !type || r.issue_type === type), pages = Math.max(1, Math.ceil(rows.length / per)); page = Math.min(page, pages);
    $("#et").innerHTML = card(type ? esc((EDGE[type] || [cap(type)])[0]) : "All labelled edge cases", table([{ h: "Label" }, { h: "Type" }, { h: "Record" }, { h: "Lead" }, { h: "Description" }], rows.slice((page - 1) * per, page * per).map(r => ({ cells: [`<span class="mono muted">${esc(r.anomaly_id)}</span>`, `<span class="tag">${esc(label(r.issue_type))}</span>`, `<span class="mono">${esc(r.record_id)}</span>`, r.lead_id ? leadLink(r.lead_id) : "–", `<span class="sm">${esc(r.description)}</span>`] }))) +
      pager({ total: rows.length, page, pages }), { sub: "click a card above to filter" });
    $$("[data-pg]", $("#et")).forEach(b => b.addEventListener("click", () => { page = +b.dataset.pg; draw(); }));
  };
  $$("[data-t]").forEach(b => b.addEventListener("click", () => { type = type === b.dataset.t ? "" : b.dataset.t; page = 1; $$("[data-t]").forEach(x => { const on = x.dataset.t === type; x.setAttribute("aria-pressed", on); x.style.borderColor = on ? "var(--ac)" : ""; }); draw(); }));
  draw();
}

async function dictionary(m) {
  const d = await cached("dictionary", "dictionary"), name = m[1] ? decodeURIComponent(m[1]) : d.tables[0].name, t = d.tables.find(x => x.name === name) || d.tables[0];
  const rel = d.relationships.filter(r => r.parent === t.name || r.child === t.name);
  V.innerHTML = head("Data dictionary", "Generated from a single schema definition that also produces the SQL DDL and drives the validator.") +
    `<div class="split"><nav class="card tlist" aria-label="Tables" style="padding:8px">${d.tables.map(x => `<a href="#/dictionary/${esc(x.name)}" ${x.name === t.name ? 'aria-current="true"' : ""}><span>${esc(x.name)}</span><span class="muted sm">${num(x.rows)}</span></a>`).join("")}</nav>
    <div>${card(esc(t.name), `<p style="margin-top:0">${esc(t.description)}</p>${t.lifecycle ? `<p class="sm"><b>Lifecycle:</b> ${esc(t.lifecycle)}</p>` : ""}<p class="sm"><b>Primary key:</b> <span class="mono">${esc(t.pk.join(", "))}</span> · ${num(t.rows)} rows</p>` +
      table([{ h: "Field" }, { h: "Type" }, { h: "Req" }, { h: "Allowed / pattern" }, { h: "FK" }, { h: "Rule" }], t.columns.map(c => ({ cells: [`<span class="mono">${esc(c.name)}</span>${c.unique ? ' <span class="tag">unique</span>' : ""}`, esc(c.type) + (c.unit ? `<div class="muted sm">${esc(c.unit)}</div>` : ""), c.required ? "Yes" : "No", `<span class="sm">${c.allowed.length ? esc(c.allowed.join(", ")) : c.pattern ? `<span class="mono">${esc(c.pattern)}</span>` : ""}</span>`, c.fk ? `<a class="mono sm" href="#/dictionary/${esc(c.fk.split(".")[0])}">${esc(c.fk)}</a>` : "", `<span class="sm muted">${esc(c.rule)}</span>`] }))))}
    <div style="margin-top:16px">${card("Relationships", table([{ h: "Parent" }, { h: "Child" }, { h: "Cardinality" }, { h: "Optionality" }], rel.map(r => ({ cells: [esc(r.parent), esc(r.child), `<b>${esc(r.cardinality)}</b>`, `<span class="sm">${esc(r.optionality)}</span>`] }))))}</div></div></div>`;
}

async function run() {
  const [meta, v] = await Promise.all([api("meta"), cached("overview", "overview")]), cfg = meta.config, files = meta.manifest ? Object.entries(meta.manifest.files) : [];
  const cmds = [["Generate the full dataset", "python -m leadgen generate --out output/full"], ["Same generator, starter volumes", "python -m leadgen generate --scale 0.05 --out data/starter"], ["Prove reproducibility (2 runs, same seed)", "python -m leadgen repro --scale 1.0"], ["Run the tests", "python -m pytest -q"], ["Open this UI on the full dataset", "python -m leadgen serve --dir output/full"]];
  V.innerHTML = head("Run & reproduce", "Everything is generated from a fixed seed. The same seed gives byte-identical files; the manifest records row counts and SHA-256 checksums.") +
    `<div class="grid g2">${card("Commands", cmds.map(([t, c]) => `<div class="muted sm">${esc(t)}</div><div class="cmdrow"><pre class="cmd">${esc(c)}</pre>${copyBtn(c)}</div>`).join(""))}
    ${card("Run configuration", `<dl class="facts" style="grid-template-columns:repeat(2,1fr)"><div><dt>Seed</dt><dd>${esc(cfg.seed)}</dd></div><div><dt>As-of date</dt><dd>${esc(day(cfg.as_of))}</dd></div><div><dt>Leads / contacts</dt><dd>${num(cfg.n_leads)} / ${num(cfg.n_contacts)}</dd></div><div><dt>Companies / opps</dt><dd>${num(cfg.n_companies)} / ${num(cfg.n_opportunities)}</dd></div><div><dt>Score window</dt><dd>${esc(cfg.score_window_days)} days</dd></div><div><dt>Holdout cutoff</dt><dd>${esc(day(cfg.holdout_cutoff))}</dd></div><div><dt>Stale after</dt><dd>${esc(cfg.stale_days)} days</dd></div><div><dt>Dedupe window</dt><dd>${esc(cfg.dedupe_window_days)} days</dd></div></dl><p class="muted sm">Generator command: <span class="mono">${esc(meta.command)}</span></p>`)}</div>
    <div style="margin-top:16px">${card("Manifest: row counts and checksums", table([{ h: "File" }, { h: "Rows", num: 1 }, { h: "Size", num: 1 }, { h: "SHA-256" }], files.map(([f, i]) => ({ cells: [`<span class="mono">${esc(f)}</span>`, i.rows == null ? "–" : num(i.rows), (i.bytes / 1024 / 1024 >= 1 ? (i.bytes / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(i.bytes / 1024)) + " KB"), `<span class="mono muted">${esc(i.sha256.slice(0, 20))}…</span>`] })), { empty: "No manifest found." }), { sub: "run twice with the same seed → identical" })}</div>`;
}

/* ---------- router & chrome ---------- */
const ROUTES = [[/^#\/leads\/(.+)$/, leadDetail, "Lead"], [/^#\/leads/, leads, "Leads"], [/^#\/pipeline/, pipeline, "Pipeline"], [/^#\/model/, model, "Scoring model"], [/^#\/quality/, quality, "Data quality"],
[/^#\/edge-cases/, edgeCases, "Edge cases"], [/^#\/dictionary(?:\/([^?]+))?/, dictionary, "Data dictionary"], [/^#\/run/, run, "Run & reproduce"], [/^#\/?$/, dashboard, "Dashboard"]];
let firstRoute = true;
async function route() {
  seq++;
  const h = location.hash || "#/", [path, qs] = h.split("?"), params = new URLSearchParams(qs || "");
  const hit = ROUTES.map(([re, fn, t]) => [re.exec(path), fn, t]).find(x => x[0]);
  $$("#nav a").forEach(a => { const base = a.getAttribute("href"); a.toggleAttribute("aria-current", base === "#/" ? path === "#/" || path === "#" : path.startsWith(base)); if (a.hasAttribute("aria-current")) a.setAttribute("aria-current", "page"); });
  V.innerHTML = skeleton(); window.scrollTo(0, 0);
  if (!hit) { V.innerHTML = `<div class="empty"><h1>Page not found</h1><p><a href="#/">Back to dashboard</a></p></div>`; return; }
  document.title = `${hit[2]} · LeadScope`;
  try { await hit[1](hit[0], params); }
  catch (e) { V.innerHTML = `<div class="card empty"><h2>Something went wrong</h2><p>${esc(e.message)}</p><button class="btn primary" onclick="route()">Retry</button></div>`; }
  if (!firstRoute) V.focus({ preventScroll: true });   // keep the skip link first in tab order on initial load
  firstRoute = false;
}
function setTheme(t) { document.documentElement.dataset.theme = t; ls.set("theme", t); $("#theme").innerHTML = icon(t === "dark" ? "sun" : "moon"); }
function setTruth(on) { state.truth = on; ls.set("truth", on ? "1" : "0"); $("#truth").setAttribute("aria-checked", on); }
(async function init() {
  $("#nav").innerHTML = NAV.map(([h, t, i]) => `<a href="${h}">${icon(i)}<span>${t}</span></a>`).join("");
  const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  setTheme(dark ? "dark" : "light"); setTruth(state.truth);
  $("#theme").addEventListener("click", () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
  $("#truth").addEventListener("click", () => { setTruth(!state.truth); toast(state.truth ? "Ground-truth labels visible" : "Ground-truth labels hidden"); route(); });
  $("#gsearch").addEventListener("submit", e => { e.preventDefault(); const q = $("#gq").value.trim(); LQ.q = q; LQ.page = 1; location.hash = "#/leads?q=" + encodeURIComponent(q); if (location.hash === "#/leads?q=" + encodeURIComponent(q)) route(); });
  window.addEventListener("hashchange", route);
  try { const o = await cached("overview", "overview"); AS_OF = o.as_of; $("#dataset").innerHTML = `<b>${num(o.counts.leads)}</b> leads · seed <b>${esc(o.seed)}</b><br>as of ${esc(day(o.as_of))}`; } catch { }
  route();
})();
