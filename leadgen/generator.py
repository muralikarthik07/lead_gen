"""Deterministic generator. Phases (parents first, then dependents/events):

 1 campaigns -> 2 companies/people/leads (IDs assigned in created_at order) -> 3 consent timelines
 -> 4 dedupe -> 5 reps + routing -> 6 pre-window activities, scoring, tasks -> 7 outcome model (opportunities,
 stage history) -> 8 post-window activities -> 9 labelled edge-case injection -> 10 derived statuses + emit.
Every phase draws from its own seeded random.Random, so phases are independent and reproducible.
"""
import math
import random
from collections import defaultdict
from datetime import datetime, timedelta
from types import SimpleNamespace as NS

from . import reference as ref
from . import scoring
from .logic import ConsentIndex, dedupe_contacts, dedupe_leads, derive_lead_status, normalize_email
from .util import fmt, parse, poisson, rand_time, sigmoid, gumbel

TIER_PLAN = {"A": [("call", 1, "high"), ("email", 3, "high"), ("demo", 7, "medium")],
             "B": [("call", 3, "medium"), ("email", 6, "medium")],
             "C": [("email", 7, "low")], "D": []}
TASK_ACTIVITY = {"call": "call_outbound", "email": "email_outbound", "demo": "demo_delivered"}
TASK_CONSENT = {"call": "phone", "email": "email", "demo": "email"}
SENIORITY_RANK = {k: v[2] for k, v in ref.SENIORITY.items()}


class Generator:
    def __init__(self, cfg):
        self.cfg = cfg
        self.as_of, self.as_of_s = parse(cfg.as_of), cfg.as_of
        self.start, self.end = parse(cfg.lead_start), parse(cfg.lead_end)
        self.anoms = []          # labelled edge cases (resolved to IDs at emit time)
        self.acts_all = []

    def rng(self, name):
        return random.Random(f"{self.cfg.seed}|{name}")   # str seeds are hash-randomisation safe

    # ------------------------------------------------------------------ run
    def run(self):
        self._campaigns()
        self._entities()
        self._consents()
        self._dedupe()
        self._reps_and_routing()
        self._prewindow_scoring_tasks()
        self._conversion()
        self._post_activities()
        self._inject_anomalies()
        return self._emit()

    # ------------------------------------------------------------ 1 campaigns
    def _campaigns(self):
        r = self.rng("campaigns")
        raw = []
        for src in ref.SOURCES:
            if src == "organic_search":
                continue
            s = datetime(2025, 12, 1)
            while s < datetime(2026, 11, 1):
                e = s + timedelta(days=r.randint(45, 90) - 1)
                focus = None if r.random() < 0.35 else r.choice(ref.PRODUCTS)
                raw.append(NS(channel=src, focus=focus, start=s, end=e, budget=r.randrange(5000, 80001, 500)))
                s = e + timedelta(days=1) - timedelta(days=r.randint(0, 15))
        raw.sort(key=lambda c: (c.start, c.channel))
        self.camp_by_src = defaultdict(list)
        self.campaign_rows = []
        for i, c in enumerate(raw, 1):
            c.id = f"CMP-{i:03d}"
            status = "planned" if c.start > self.as_of else ("completed" if c.end + timedelta(days=1) <= self.as_of else "active")
            self.campaign_rows.append(dict(
                campaign_id=c.id, campaign_name=f"{ref.SOURCE_LABEL[c.channel]} | {c.focus or 'All Products'} | {c.start:%b %Y}",
                channel=c.channel, product_focus=c.focus, start_date=c.start.strftime("%Y-%m-%d"),
                end_date=c.end.strftime("%Y-%m-%d"), budget_usd=float(c.budget), status=status))
            self.camp_by_src[c.channel].append(c)

    # ------------------------------------------------- 2 companies/people/leads
    def _entities(self):
        cfg, r = self.cfg, self.rng("entities")
        n_cl = round(cfg.n_contacts * cfg.dup_contact_rate)
        n_people = cfg.n_contacts - n_cl
        assert cfg.n_leads >= cfg.n_contacts >= cfg.n_companies and n_people >= cfg.n_companies, "volumes must satisfy leads>=contacts>=companies"

        # -- companies
        ind = list(ref.INDUSTRIES)
        cc = list(ref.COUNTRIES)
        comps, combos = [], len(ref.CO_PREFIX) * len(ref.CO_NOUN) * len(ref.CO_SUFFIX)
        order = list(range(combos))
        r.shuffle(order)
        for i in range(cfg.n_companies):
            k, cycle = order[i % combos], i // combos
            a, b, c = k % len(ref.CO_PREFIX), (k // len(ref.CO_PREFIX)) % len(ref.CO_NOUN), k // (len(ref.CO_PREFIX) * len(ref.CO_NOUN))
            name = f"{ref.CO_PREFIX[a]} {ref.CO_NOUN[b]} {ref.CO_SUFFIX[c]}" + (f" {cycle + 1}" if cycle else "")
            band = r.choices(ref.BANDS, weights=[x[3] for x in ref.BANDS])[0]
            lo, hi = band[1], band[2]
            if band[0] == "1000+":
                emp = int(1001 + min(49000, r.lognormvariate(6.5, 1.0)))
            else:
                emp = min(hi, max(lo, int(math.exp(r.uniform(math.log(lo), math.log(hi + 0.999))))))
            rev = max(50000, round(emp * r.lognormvariate(math.log(140000), 0.5), -3))
            country = r.choices(cc, weights=[ref.COUNTRIES[x][1] for x in cc])[0]
            comps.append(NS(seq=i, name=name, domain="".join(ch for ch in name.lower() if ch.isalnum()) + ".example",
                            industry=r.choices(ind, weights=[ref.INDUSTRIES[x][0] for x in ind])[0], band=band[0], emp=emp,
                            rev=float(rev), country=country, territory=ref.COUNTRIES[country][0], people=[]))

        # -- people (excluding clones) and lead counts (cap 4 leads/person)
        sen = list(ref.SENIORITY)
        people = []
        for i in range(n_people):
            s = r.choices(sen, weights=[ref.SENIORITY[x][1] for x in sen])[0]
            people.append(NS(seq=i, first=r.choice(ref.FIRST), last=r.choice(ref.LAST), seniority=s,
                             title=r.choice(ref.SENIORITY[s][0]), free=r.random() < cfg.free_email_rate,
                             has_phone=r.random() < 0.70, leads=[], is_clone=False, master=None))
        idx = list(range(n_people))
        r.shuffle(idx)
        for ci, pi in enumerate(idx[:cfg.n_companies]):
            people[pi].company = comps[ci]
        rest = idx[cfg.n_companies:]
        w = [(ref.BAND_LABELS.index(c.band) + 1) * r.lognormvariate(0, .5) for c in comps]
        for pi, c in zip(rest, r.choices(comps, weights=w, k=len(rest))):
            people[pi].company = c
        used_emails = set()
        for p in people:
            local = f"{p.first}.{p.last}".lower()
            dom = ref.FREE_EMAIL_DOMAIN if p.free else p.company.domain
            email, n = f"{local}@{dom}", 1
            while email in used_emails:
                n += 1
                email = f"{local}{n}@{dom}"
            used_emails.add(email)
            p.email = email
            p.phone = f"+{ref.COUNTRIES[p.company.country][2]}-555-{r.randint(0, 9999):04d}" if p.has_phone else None
            p.company.people.append(p)

        counts = [1] * n_people
        weights = [r.lognormvariate(0, 1.0) for _ in range(n_people)]
        remaining = cfg.n_leads - cfg.n_contacts
        while remaining > 0:
            for i in r.choices(range(n_people), weights=weights, k=remaining):
                if counts[i] < 4 and remaining > 0:
                    counts[i] += 1
                    remaining -= 1

        # -- leads. Same-product leads for one person are >= 95 days apart so natural data has no duplicates
        leads = []
        pw = ref.PRODUCT_WEIGHT
        for p in people:
            times = sorted(rand_time(r, self.start, self.end) for _ in range(counts[p.seq]))
            for t in times:
                allowed = [pr for pr in ref.PRODUCTS if all(not (l.product == pr and (t - l.created).days < 95) for l in p.leads)]
                lead = NS(person=p, created=t, product=r.choices(allowed, weights=[pw[x] for x in allowed])[0],
                          source=r.choices(ref.SOURCES, weights=ref.SOURCE_WEIGHT)[0], acts=[], is_dup=False,
                          dup_truth_master=None, dups=[], seq=len(leads))
                p.leads.append(lead)
                leads.append(lead)

        # -- injected duplicate contacts (+ one duplicate lead each): ground truth for the dedupe step
        elig = [p for p in people if p.leads[0].created <= self.end - timedelta(days=61)]
        r.shuffle(elig)
        assert len(elig) >= n_cl
        for mp in elig[:n_cl]:
            ml = mp.leads[0]
            local, dom = mp.email.split("@")
            variant = r.choice([f"{local.title()}@{dom}", f"{local}+promo@{dom}", f"{local}@{dom.upper()}"])
            cl = NS(seq=len(people), first=mp.first, last=mp.last, seniority=mp.seniority, title=mp.title, free=mp.free,
                    has_phone=r.random() < 0.5, leads=[], is_clone=True, master=mp, company=mp.company, email=variant,
                    phone=mp.phone if r.random() < 0.5 else None)
            mp.company.people.append(cl)
            people.append(cl)
            lead = NS(person=cl, created=ml.created + timedelta(seconds=int(r.uniform(1, 60) * 86400)), product=ml.product,
                      source=r.choices(ref.SOURCES, weights=ref.SOURCE_WEIGHT)[0], acts=[], is_dup=True,
                      dup_truth_master=ml, dups=[], seq=len(leads))
            cl.leads.append(lead)
            leads.append(lead)
            ml.dups.append(lead)

        # -- IDs in created_at order (immutable, zero-padded)
        leads.sort(key=lambda l: (l.created, l.seq))
        yc = defaultdict(int)
        for l in leads:
            yc[l.created.year] += 1
            l.id = f"LEAD-{l.created.year}-{yc[l.created.year]:06d}"
        people.sort(key=lambda p: (p.leads[0].created, p.seq))
        for i, p in enumerate(people, 1):
            p.id, p.created = f"CON-{i:06d}", p.leads[0].created
            p.leads.sort(key=lambda l: l.created)
        for c in comps:
            c.created = min(p.created for p in c.people) - timedelta(seconds=int(r.uniform(1, 730) * 86400))
        comps.sort(key=lambda c: (c.created, c.seq))
        for i, c in enumerate(comps, 1):
            c.id = f"CO-{i:06d}"
        self.companies, self.people, self.leads = comps, people, leads
        self.lead_by_id = {l.id: l for l in leads}

        # -- rows (the objects keep a reference so later phases can fill derived columns)
        for c in comps:
            c.row = dict(company_id=c.id, company_name=c.name, domain=c.domain, industry=c.industry, employee_count=c.emp,
                         employee_band=c.band, annual_revenue_usd=c.rev, country=c.country, territory=c.territory,
                         created_at=fmt(c.created))
        for p in people:
            p.row = dict(contact_id=p.id, company_id=p.company.id, first_name=p.first, last_name=p.last, email=p.email,
                         email_type="free" if p.free else "corporate", phone=p.phone, job_title=p.title,
                         seniority=p.seniority, created_at=fmt(p.created), duplicate_of_contact_id=None)
        rc = self.rng("lead_campaign")
        for l in leads:
            camp = None
            if l.source != "organic_search":
                cov = [c for c in self.camp_by_src[l.source] if c.start <= l.created < c.end + timedelta(days=1)]
                pref = [c for c in cov if c.focus in (None, l.product)] or cov
                camp = rc.choice(pref)
            l.row = dict(lead_id=l.id, contact_id=l.person.id, company_id=l.person.company.id,
                         campaign_id=camp.id if camp else None, consent_id=None, source=l.source, product_interest=l.product,
                         territory=l.person.company.territory, created_at=fmt(l.created), assigned_rep_id=None,
                         routed_at=None, routing_rule=None, status=None, duplicate_of_lead_id=None)
            l.person_row, l.company_row = l.person.row, l.person.company.row
            l.contact_id = l.person.id

    # ----------------------------------------------------------- 3 consent
    def _consents(self):
        cfg, r = self.cfg, self.rng("consent")
        rows = []
        for p in self.people:
            t0 = p.leads[0].created
            method = ref.CONSENT_METHOD.get(p.leads[0].source, "web_form")
            ev = {"email": [(t0, "opt_in", method)]}
            t_out = None
            if r.random() < cfg.optout_email_rate:
                t = (t0 + timedelta(seconds=int(r.uniform(5, 150) * 86400)))
                if t < self.as_of:
                    t_out = t
                    ev["email"].append((t_out, "opt_out", "user_request"))
                    for l in p.leads:                          # a later lead may re-opt-in via a new form
                        if l.created > t_out:
                            if r.random() < 0.5:
                                ev["email"].append((l.created, "opt_in", "web_form"))
                            break
            if p.has_phone and r.random() < 0.6:
                ev["phone"] = [(t0, "opt_in", "sales_call")]
                if t_out and r.random() < 0.4:
                    ev["phone"].append((t_out, "opt_out", "user_request"))
                elif r.random() < cfg.optout_phone_rate:
                    t = t0 + timedelta(seconds=int(r.uniform(5, 150) * 86400))
                    if t < self.as_of:
                        ev["phone"].append((t, "opt_out", "user_request"))
            for ch, evs in ev.items():
                evs.sort()
                for i, (t, st, m) in enumerate(evs):
                    rows.append(dict(contact_id=p.id, channel=ch, status=st, effective_from=fmt(t),
                                     effective_to=fmt(evs[i + 1][0]) if i + 1 < len(evs) else None, capture_method=m))
        rows.sort(key=lambda x: (x["effective_from"], x["contact_id"], x["channel"]))
        for i, x in enumerate(rows, 1):
            x["consent_id"] = f"CNS-{i:06d}"
        self.consent_rows = rows
        self.cidx = ConsentIndex(rows)
        for l in self.leads:
            l.row["consent_id"] = self.cidx.period_at(l.person.id, "email", l.row["created_at"])["consent_id"]

    def consent(self, lead, channel, t):
        return self.cidx.has_consent(lead.person.id, channel, fmt(t))

    # ----------------------------------------------------------- 4 dedupe
    def _dedupe(self):
        cd = dedupe_contacts([p.row for p in self.people])
        ld = dedupe_leads([l.row for l in self.leads], cd, self.cfg.dedupe_window_days)
        truth_c = {p.id: p.master.id for p in self.people if p.is_clone}
        truth_l = {l.id: l.dup_truth_master.id for l in self.leads if l.dup_truth_master}
        assert cd == truth_c and ld == truth_l, "dedupe output differs from injected duplicate ground truth"
        self.contact_by_id = {p.id: p for p in self.people}
        for p in self.people:
            p.row["duplicate_of_contact_id"] = cd.get(p.id)
        for l in self.leads:
            l.row["duplicate_of_lead_id"] = ld.get(l.id)
            l.is_dup = l.id in ld
            if l.is_dup:
                self.anoms.append(dict(issue_type="duplicate_lead", table="Lead", ref=l, related=[ld[l.id]],
                                       description="Lead duplicates master lead (same normalised email + product within 90 days)"))
        for p in self.people:
            if p.id in cd:
                self.anoms.append(dict(issue_type="duplicate_contact", table="Contact", ref=p, related=[cd[p.id]],
                                       description="Contact duplicates master contact (same normalised email)"))

    # ------------------------------------------------- 5 reps and routing
    def _reps_and_routing(self):
        r = self.rng("reps")
        reps, n = [], 0
        for terr in ref.TERRITORIES:
            k = ref.REPS_PER_TERRITORY[terr]
            inactive = k - 1 if r.random() < 0.5 else -1          # at most one inactive rep per territory
            trep = []
            for j in range(k):
                n += 1
                hire = datetime(2026, 1, 1) - timedelta(days=r.randint(90, 2900))
                rep = NS(id=f"REP-{n:03d}", name=f"{r.choice(ref.FIRST)} {r.choice(ref.LAST)}", territory=terr, hire=hire,
                         active=j != inactive, products=set())
                months = (self.as_of - hire).days / 30.4
                rep.resp = 0.60 + 0.35 * min(1.0, months / 60.0)  # responsiveness (hidden driver of follow-up/win)
                trep.append(rep)
            for i, prod in enumerate(ref.PRODUCTS):
                for off in range(3 if k >= 5 else 2):
                    trep[(i + off) % k].products.add(prod)
            reps += trep
        self.reps, self.rep_by_id = reps, {x.id: x for x in reps}
        self.rep_rows = [dict(rep_id=x.id, rep_name=x.name, territory=x.territory, hire_date=x.hire.strftime("%Y-%m-%d"),
                              is_active=int(x.active)) for x in reps]
        self.coverage_rows = [dict(rep_id=x.id, territory=x.territory, product=p, effective_from="2026-01-01T00:00:00",
                                   effective_to=None) for x in reps for p in ref.PRODUCTS if p in x.products]
        cover = defaultdict(list)
        for x in reps:
            for p in x.products:
                cover[(x.territory, p)].append(x)
        self.cover = cover
        load = defaultdict(int)
        rr = self.rng("routing")
        for l in self.leads:                                      # time order => stable least-loaded balancing
            if l.is_dup:
                l.rep = self.lead_by_id[l.row["duplicate_of_lead_id"]].rep
                rule = "duplicate_follows_master"
            else:
                el = sorted([x for x in cover[(l.person.company.territory, l.product)] if x.active], key=lambda x: (load[x.id], x.id))
                l.rep = el[0]
                load[l.rep.id] += 1
                rule = "territory_product_least_loaded"
            l.row.update(assigned_rep_id=l.rep.id, routing_rule=rule,
                         routed_at=fmt(l.created + timedelta(minutes=rr.randint(1, 30))))
        # labelled edge case: lead assigned outside territory (done before tasks/opps so everything downstream is consistent)
        cands = [l for l in self.leads if not l.is_dup and not l.dups]
        for l in rr.sample(cands, min(self.cfg.n_anom_outside_territory, len(cands))):
            wrong = sorted([x for x in self.reps if x.active and (x.territory != l.row["territory"]) and l.product in x.products],
                           key=lambda x: x.id)
            l.rep = rr.choice(wrong)
            l.row["assigned_rep_id"] = l.rep.id
            self.anoms.append(dict(issue_type="lead_assigned_outside_territory", table="Lead", ref=l, related=[l.rep.id],
                                   description=f"Lead territory {l.row['territory']} routed to rep in {l.rep.territory}"))

    # ------------------------------------------------------- activity helper
    def _act(self, lead, typ, t, rep=None, task=None):
        d, ch, _ = ref.ACTIVITY_TYPES[typ]
        a = NS(type=typ, direction=d, channel=ch, t=t.replace(microsecond=0), rep=rep, task=task, order=len(lead.acts), id=None)
        lead.acts.append(a)
        return a

    def _acts_view(self, lead, upto=None):
        return [dict(activity_type=a.type, direction=a.direction, occurred_at=fmt(a.t)) for a in lead.acts
                if upto is None or a.t <= upto]

    # --------------------------------- 6 pre-window activities, scores, tasks
    def _prewindow_scoring_tasks(self):
        cfg, r = self.cfg, self.rng("prewindow")
        self.rule_rows = scoring.build_rule_rows()
        self.score_rows, self.comp_rows, self.task_rows, self.tasks = [], [], [], []
        W = timedelta(days=cfg.score_window_days)
        bl = [None] + list(ref.BLOCKERS)
        bw = [1 - cfg.blocker_rate, cfg.blocker_rate * .4, cfg.blocker_rate * .35, cfg.blocker_rate * .25]
        rt = self.rng("tasks")
        for l in self.leads:
            c, w = l.created, l.created + W
            ib = ref.SOURCE_INTENT[l.source]
            l.interest = i = r.betavariate(2 + 4 * ib, 2 + 4 * (1 - ib))
            l.blocker = r.choices(bl, weights=bw)[0]
            self._act(l, "form_submit", c)
            for k, t in enumerate([c + timedelta(minutes=r.randint(5, 120)), c + timedelta(days=3, hours=r.randint(0, 8)),
                                   c + timedelta(days=8, hours=r.randint(0, 8))]):
                if self.consent(l, "email", t):
                    self._act(l, "email_outbound", t)
                    if r.random() < .25 + .4 * i:
                        self._act(l, "email_open", t + timedelta(minutes=r.randint(2, 600)))
                    if r.random() < .08 + .3 * i:
                        self._act(l, "email_click", t + timedelta(minutes=r.randint(5, 900)))
            wts = [.62, .13 + .1 * i, .20]
            for _ in range(poisson(r, 1.2 + 5 * i)):
                self._act(l, r.choices(["web_visit", "pricing_page_visit", "content_download"], weights=wts)[0],
                          c + timedelta(seconds=int(r.uniform(600, W.total_seconds() - 60))))
            if r.random() < .03 + .35 * i * i:
                self._act(l, "demo_request", c + timedelta(seconds=int(r.uniform(3600, W.total_seconds() - 60))))
            if l.is_dup:
                continue                                           # duplicates are merged: not scored, no tasks
            # ---- initial score (point-in-time, uses only activities <= scored_at)
            l.scored = w
            l.feat = scoring.extract_features(l.company_row, l.person_row, l.row, self._acts_view(l, w), fmt(w))
            res = scoring.score_lead(l.feat, self.rule_rows, fmt(w))
            l.score = res
            l.score_id = f"SCR-{l.id}-01"
            self.score_rows.append(dict(score_id=l.score_id, lead_id=l.id, scored_at=fmt(w), rule_version=res["rule_version"],
                                        raw_score=res["raw"], total_score=res["total"], tier=res["tier"], trigger="initial"))
            self.comp_rows += [dict(score_id=l.score_id, rule_id=rid, units=u, points=p) for rid, u, p in res["components"]]
            # ---- follow-up tasks from tier (consent-gated)
            for n, (ttype, days, prio) in enumerate(TIER_PLAN[res["tier"]], 1):
                due = w + timedelta(days=days)
                status, reason, done = "open", None, None
                if not self.consent(l, TASK_CONSENT[ttype], due):
                    if ttype == "call" and self.consent(l, "email", due):
                        ttype = "email"                            # documented fallback: no phone consent -> email task
                    else:
                        status, reason = "cancelled", "no_consent"
                if status != "cancelled":
                    if rt.random() < l.rep.resp:
                        done = w + (due - w) * rt.uniform(.4, 1.0)
                        if rt.random() < .3:
                            done += timedelta(days=rt.expovariate(1 / 1.5))
                        done = done.replace(microsecond=0)
                    if done and not self.consent(l, TASK_CONSENT[ttype], done):
                        status, reason, done = "cancelled", "opted_out", None
                    elif done and done <= self.as_of:
                        status = "completed"
                    else:
                        done, status = None, ("overdue" if due < self.as_of else "open")
                t = NS(id=f"TASK-{l.id}-{n:03d}", lead=l, type=ttype, due=due, done=done)
                self.tasks.append(t)
                self.task_rows.append(dict(task_id=t.id, lead_id=l.id, rep_id=l.rep.id, task_type=ttype, priority=prio,
                                           created_at=fmt(w), due_at=fmt(due), completed_at=fmt(done) if done else None,
                                           status=status, cancel_reason=reason))
                if status == "completed":
                    self._act(l, TASK_ACTIVITY[ttype], done, rep=l.rep.id, task=t)

    # ------------------------------------------------------ 7 outcome model
    @staticmethod
    def _indices(f):
        fit = .4 * ref.BAND_LABELS.index(f["employee_band"]) / 4 + .3 * f["industry_target"] + .3 * SENIORITY_RANK[f["seniority"]]
        intent = .4 * ref.SOURCE_INTENT[f["source"]] + .4 * (f["demo_requests"] > 0) + .2 * min(1, f["pricing_visits"] / 2)
        eng = min(1.0, .15 * f["email_clicks"] + .06 * f["web_visits"] + .2 * f["recent_inbound_7d"])
        return fit, intent, eng

    def _conversion(self):
        """Documented outcome rule: lead converts iff it is among the top-N of
        logit = 3.2*fit + 2.8*intent + 2.2*engagement + 1.5*(rep_responsiveness-0.8) + blocker_penalty + Gumbel noise
        (Plackett-Luce sampling without replacement). Fit/intent/engagement are *hidden* indices computed from the same raw
        facts as the score but with different weights, so the transparent score is informative but imperfect."""
        cfg, r = self.cfg, self.rng("conversion")
        elig = []
        for l in self.leads:
            if l.is_dup:
                continue
            ok = self.cidx.contactable_through(l.person.id, fmt(l.scored), fmt(l.scored + timedelta(days=35)))
            fit, intent, eng = self._indices(l.feat)
            l.fit, l.intent, l.eng = fit, intent, eng
            l.logit = 3.2 * fit + 2.8 * intent + 2.2 * eng + 1.5 * (l.rep.resp - .8) + ref.BLOCKERS.get(l.blocker, 0.0)
            if ok:
                l.noisy = l.logit + gumbel(r)
                elig.append(l)
        ranked = sorted(elig, key=lambda x: (-x.noisy, x.id))
        n_opp, k_cfg = cfg.n_opportunities, cfg.n_anom_dup_opp
        base = ranked[:n_opp - k_cfg]
        self.opps = []
        ro = self.rng("opps")
        for l in base:
            self.opps.append(self._make_opp(l, ro, l.scored + timedelta(days=max(1.0, ro.uniform(1, 35) * (1.3 - l.rep.resp)))))
        # labelled edge case: duplicate lead also gets an opportunity (master + duplicate both converted)
        om = {o.lead.id: o for o in self.opps}
        cands = []
        for l in base:
            for d in l.dups:
                t = max(om[l.id].created + timedelta(days=ro.uniform(1, 20)), d.created + timedelta(days=ro.uniform(1, 5)))
                if t.replace(microsecond=0) <= self.as_of:
                    cands.append((l, d, t.replace(microsecond=0)))
        picked = ro.sample(cands, min(k_cfg, len(cands)))
        for l, d, t in picked:
            d.feat, d.logit, d.fit, d.intent, d.eng, d.blocker, d.rep = l.feat, l.logit, l.fit, l.intent, l.eng, l.blocker, l.rep
            o = self._make_opp(d, ro, t)
            o.master_opp = om[l.id]
            self.opps.append(o)
            self.anoms.append(dict(issue_type="duplicate_creates_duplicate_opportunity", table="Opportunity", ref=o,
                                   related=[d.id, l.id, om[l.id]], description="Opportunity created from a duplicate lead whose master lead also has an opportunity"))
        extra = ranked[n_opp - k_cfg:n_opp - k_cfg + (k_cfg - len(picked))]   # keep total at n_opportunities
        for l in extra:
            self.opps.append(self._make_opp(l, ro, l.scored + timedelta(days=max(1.0, ro.uniform(1, 35) * (1.3 - l.rep.resp)))))
        self.opps.sort(key=lambda o: (o.created, o.lead.id))
        yc = defaultdict(int)
        for o in self.opps:
            yc[o.created.year] += 1
            o.id = f"OPP-{o.created.year}-{yc[o.created.year]:06d}"
        self.opp_by_lead = {o.lead.id: o for o in self.opps}

    def _make_opp(self, l, r, created):
        created = created.replace(microsecond=0)
        co = l.person.company
        amount = max(1000, round(ref.PRODUCT_BASE_AMOUNT[l.product] * ref.BAND_AMOUNT_MULT[co.band] * r.lognormvariate(0, .35) / 500) * 500)
        blk = l.blocker
        win_logit = (-1.6 + 1.4 * l.fit + .8 * l.intent + 1.5 * (l.rep.resp - .8) - .5 * math.log(amount / 30000.0) - (1.2 if blk else 0))
        won = r.random() < sigmoid(win_logit)
        lost_idx = None if won else r.choices([0, 1, 2, 3], weights=[.2, .3, .3, .2])[0]
        if won:                                                    # documented reason rules
            reason = "relationship" if l.source in ("referral", "partner") else "product_fit" if l.fit >= .6 else "price" if amount < 25000 else "features"
        elif blk:
            reason = {"no_budget": "budget", "competitor_incumbent": "competitor", "no_response": "no_decision"}[blk]
        else:
            reason = ["not_a_fit" if l.fit < .45 else "timing", "timing", "price", "price" if amount >= 30000 else "competitor"][lost_idx]
        ev, t, cur = [(1, None, "Qualification", created, "opportunity_created")], created, 0
        while True:
            t = (t + timedelta(days=r.uniform(*ref.STAGE_DAYS[cur]))).replace(microsecond=0)
            if not won and cur == lost_idx:
                ev.append((len(ev) + 1, ref.OPEN_STAGES[cur], "Closed Lost", t, "lost:" + reason))
                break
            if cur == 3:
                ev.append((len(ev) + 1, "Negotiation", "Closed Won", t, "won:" + reason))
                break
            ev.append((len(ev) + 1, ref.OPEN_STAGES[cur], ref.OPEN_STAGES[cur + 1], t, "stage_advanced"))
            cur += 1
        kept = [e for e in ev if e[3] <= self.as_of]
        cur_stage = kept[-1][2]
        closed = cur_stage in ("Closed Won", "Closed Lost")
        return NS(id=None, lead=l, created=created, amount=float(amount), product=l.product, won_eventual=won, reason_eventual=reason,
                  events=kept, current=cur_stage, closed_at=kept[-1][3] if closed else None,
                  status=("won" if cur_stage == "Closed Won" else "lost" if cur_stage == "Closed Lost" else "open"),
                  master_opp=None, sh_rows=None)

    # ------------------------------------------- 8 post-window activities
    def _stream(self, l, a, b, rate, r):
        days = (b - a).total_seconds() / 86400
        if days <= 0:
            return
        for _ in range(min(40, poisson(r, rate * days))):
            t = a + timedelta(seconds=int(r.uniform(0, (b - a).total_seconds())))
            typ = r.choices(["web_visit", "pricing_page_visit", "email_click", "email_open", "demo_request"],
                            weights=[.45, .12 + .1 * l.interest, .18, .2, .05])[0]
            if typ in ("email_click", "email_open") and not self.consent(l, "email", t):
                continue
            self._act(l, typ, t)

    def _post_activities(self):
        r = self.rng("post")
        for l in self.leads:
            if l.is_dup:
                continue
            i, o = l.interest, self.opp_by_lead.get(l.id)
            if o and o.lead is l and o.master_opp is None:
                self._stream(l, l.scored, o.created, .10 + .6 * i, r)
                tq = o.created - timedelta(seconds=int(r.uniform(3600, 12 * 3600)))   # qualification touch before the opp
                for typ, ch in (("call_outbound", "phone"), ("email_outbound", "email")):
                    if self.consent(l, ch, tq):
                        self._act(l, typ, tq, rep=l.rep.id)
                        break
                for (_, _, to, t, _) in o.events[1:]:
                    typ = {"Discovery": "demo_delivered", "Proposal": "proposal_sent", "Negotiation": "meeting"}.get(to, "email_outbound")
                    ta = t - timedelta(minutes=r.randint(10, 600))
                    if ta > o.created and self.consent(l, "email", ta):
                        self._act(l, typ, ta, rep=l.rep.id)
                end = o.closed_at or self.as_of
                self._stream(l, o.created, end, .08 + .3 * i, r)
            else:
                life = float("inf") if r.random() < .20 else r.expovariate(1 / (55 * (.4 + i)))
                end = self.as_of if life == float("inf") else min(self.as_of, l.scored + timedelta(days=life))
                self._stream(l, l.scored, end, .02 + .2 * i, r)

    # ------------------------------------------- 9 labelled edge cases
    def _inject_anomalies(self):
        cfg, r = self.cfg, self.rng("anomalies")
        # (1) opted-out lead contacted: outbound email AFTER an opt-out period began
        cands = []
        for l in self.leads:
            if l.is_dup:
                continue
            for p in self.cidx._p.get((l.person.id, "email"), ()):
                if p["status"] == "opt_out":
                    t0 = max(parse(p["effective_from"]), l.created)
                    t = t0 + timedelta(seconds=int(r.uniform(2, 40) * 86400))
                    end = parse(p["effective_to"]) if p["effective_to"] else self.as_of
                    if t < end and t < self.as_of:
                        cands.append((l, t.replace(microsecond=0), p))
                        break
        for l, t, p in r.sample(cands, min(cfg.n_anom_optout_contacted, len(cands))):
            a = self._act(l, "email_outbound", t, rep=l.rep.id)
            self.anoms.append(dict(issue_type="opted_out_lead_contacted", table="Activity", ref=a, related=[l.id, p["consent_id"]],
                                   description="Outbound email sent while the contact's email consent was opt_out"))
        # (2) score uses post-conversion event: late 'rescore' counting activity after the opportunity was created
        cands = []
        for o in self.opps:
            l = o.lead
            if o.master_opp is not None:
                continue
            post = [a for a in l.acts if a.t > o.created and a.direction == "inbound" and a.t <= self.as_of
                    and a.type in ("web_visit", "pricing_page_visit", "email_click", "demo_request")]
            if post:
                t = max(a.t for a in post)
                res = scoring.score_lead(scoring.extract_features(l.company_row, l.person_row, l.row, self._acts_view(l, t), fmt(t)),
                                         self.rule_rows, fmt(t))
                if res["raw"] > l.score["raw"]:
                    cands.append((l, o, t, res, len(post)))
        for l, o, t, res, npost in r.sample(cands, min(cfg.n_anom_post_conv_score, len(cands))):
            sid = f"SCR-{l.id}-02"
            self.score_rows.append(dict(score_id=sid, lead_id=l.id, scored_at=fmt(t), rule_version=res["rule_version"], raw_score=res["raw"],
                                        total_score=res["total"], tier=res["tier"], trigger="rescore"))
            self.comp_rows += [dict(score_id=sid, rule_id=rid, units=u, points=p) for rid, u, p in res["components"]]
            self.anoms.append(dict(issue_type="score_uses_post_conversion_event", table="LeadScore", ref=NS(id=sid),
                                   related=[l.id, o],
                                   description=f"Rescore at {fmt(t)} counts {npost} activities after opportunity creation; score {l.score['total']} -> {res['total']}"))
        # (3) stage-history gaps are injected after history rows exist (see _emit)

    # --------------------------------------- 10 derived values + emit tables
    def _emit(self):
        cfg = self.cfg
        # activity ids (ACT-<lead-id>-NNN in time order) and rows
        act_rows = []
        for l in self.leads:
            l.acts.sort(key=lambda a: (a.t, a.order))
            for n, a in enumerate(l.acts, 1):
                a.id = f"ACT-{l.id}-{n:03d}"
                act_rows.append(dict(activity_id=a.id, lead_id=l.id, activity_type=a.type, direction=a.direction, channel=a.channel,
                                     occurred_at=fmt(a.t), rep_id=a.rep, task_id=a.task.id if a.task else None))
        opp_rows, sh_rows = [], []
        for o in self.opps:
            l = o.lead
            opp_rows.append(dict(opportunity_id=o.id, lead_id=l.id, company_id=l.person.company.id, contact_id=l.person.id,
                                 rep_id=l.rep.id, product=o.product, amount_usd=o.amount, created_at=fmt(o.created),
                                 current_stage=o.current, status=o.status, closed_at=fmt(o.closed_at) if o.closed_at else None,
                                 outcome_reason=o.reason_eventual if o.status != "open" else None))
            o.sh_rows = [dict(stage_history_id=f"STG-{o.id}-{s:02d}", opportunity_id=o.id, seq=s, from_stage=f, to_stage=to,
                              changed_at=fmt(t), transition_reason=why) for (s, f, to, t, why) in o.events]
        # (3) stage history has gaps: drop one middle transition event (labelled)
        rg = self.rng("gaps")
        cands = [o for o in self.opps if len(o.sh_rows) >= 4]
        for o in rg.sample(cands, min(cfg.n_anom_stage_gap, len(cands))):
            k = rg.randrange(1, len(o.sh_rows) - 1)
            missing = o.sh_rows.pop(k)
            self.anoms.append(dict(issue_type="stage_history_gap", table="Opportunity", ref=o,
                                   related=[missing["stage_history_id"]],
                                   description=f"Missing StageHistory seq {missing['seq']} ({missing['from_stage']} -> {missing['to_stage']})"))
        for o in self.opps:
            sh_rows += o.sh_rows
        # lead status (derived from source records)
        tier_of = {s["lead_id"]: s["tier"] for s in self.score_rows if s["trigger"] == "initial"}
        done_tasks = {r["lead_id"] for r in self.task_rows if r["status"] == "completed"}
        for l in self.leads:
            last = fmt(max(a.t for a in l.acts))
            touch = any(a.rep for a in l.acts)
            l.row["status"] = derive_lead_status(l.is_dup, l.id in self.opp_by_lead,
                                                 self.cidx.opted_out_everywhere(l.person.id, self.as_of_s), last, self.as_of_s,
                                                 cfg.stale_days, tier_of.get(l.id), l.id in done_tasks, touch)
        tables = dict(Company=[c.row for c in self.companies], Contact=[p.row for p in self.people], Campaign=self.campaign_rows,
                      SalesRep=self.rep_rows, RepCoverage=self.coverage_rows, Consent=self.consent_rows,
                      Lead=[l.row for l in self.leads], Task=self.task_rows, Activity=act_rows, ScoreRule=self.rule_rows,
                      LeadScore=self.score_rows, LeadScoreComponent=self.comp_rows, Opportunity=opp_rows, StageHistory=sh_rows)
        return tables, self._ground_truth(tier_of)

    def _ground_truth(self, tier_of):
        cfg = self.cfg
        an = []
        for a in self.anoms:
            ref_id = a["ref"].id
            rel = [x.id if hasattr(x, "id") else x for x in a["related"]]
            an.append(dict(issue_type=a["issue_type"], table=a["table"], record_id=ref_id, related_ids=";".join(rel),
                           description=a["description"]))
        an.sort(key=lambda x: (x["issue_type"], x["record_id"]))
        for i, x in enumerate(an, 1):
            x["anomaly_id"] = f"GT-{i:05d}"
        labels = []
        for l in self.leads:
            o = self.opp_by_lead.get(l.id)
            tier = tier_of.get(l.id)
            conv = int(o is not None)
            labels.append(dict(
                lead_id=l.id, is_duplicate=int(l.is_dup), converted=conv, opportunity_id=o.id if o else None,
                eventual_outcome=("won" if o.won_eventual else "lost") if o else "none",
                observed_status=o.status if o else "none", hidden_blocker=l.blocker, initial_tier=tier,
                is_high_score_non_converter=int(tier == "A" and not conv and not l.is_dup),
                is_stale=int(l.row["status"] == "Stale"),
                holdout_split="test" if l.row["created_at"] >= cfg.holdout_cutoff else "train"))
        return dict(anomalies=an, lead_labels=labels)
