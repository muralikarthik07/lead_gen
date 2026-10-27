"""Read-only query layer over an exported dataset directory. No HTTP here, so it is unit-testable.

Ground truth (ground_truth/*) is kept in separate structures and only returned when `truth=True` is requested,
mirroring the rule that labels never leak into input features."""
import csv
import json
import os
import re
from collections import Counter, defaultdict

from . import reference as ref
from . import scoring
from . import schema
from .io_utils import read_csv
from .logic import ConsentIndex

SORTABLE = {"created": "created", "score": "score", "company": "company", "status": "status", "lead_id": "lead_id", "amount": "amount"}
LEAD_ID_RE = re.compile(r"(LEAD-\d{4}-\d{6})")


def _page(rows, page, size):
    size = max(1, min(int(size or 25), 100))
    page = max(1, int(page or 1))
    total = len(rows)
    return dict(total=total, page=page, size=size, pages=max(1, -(-total // size)), rows=rows[(page - 1) * size: page * size])


class Store:
    def __init__(self, out):
        self.out = out
        p = lambda *a: os.path.join(out, *a)
        if not os.path.exists(p("csv", "lead.csv")):
            raise FileNotFoundError(f"No dataset in {out!r}. Run: python -m leadgen generate --out {out}")
        self.meta = json.load(open(p("run_metadata.json")))
        self.cfg = self.meta["config"]
        self.as_of = self.cfg["as_of"]
        t = {n: read_csv(p("csv", n + ".csv")) for n in (
            "company", "contact", "campaign", "sales_rep", "rep_coverage", "consent", "lead", "task", "score_rule",
            "lead_score", "lead_score_component", "opportunity", "stage_history")}
        self.t = t
        self.company = {r["company_id"]: r for r in t["company"]}
        self.contact = {r["contact_id"]: r for r in t["contact"]}
        self.campaign = {r["campaign_id"]: r for r in t["campaign"]}
        self.rep = {r["rep_id"]: r for r in t["sales_rep"]}
        self.rules = {r["rule_id"]: r for r in t["score_rule"]}
        self.cover = {(r["rep_id"], r["territory"], r["product"]) for r in t["rep_coverage"]}
        self.cidx = ConsentIndex(t["consent"])
        self.consent_by_contact = defaultdict(list)
        for r in t["consent"]:
            self.consent_by_contact[r["contact_id"]].append(r)
        self.lead = {r["lead_id"]: r for r in t["lead"]}
        self.leads_by_contact = defaultdict(list)
        for r in t["lead"]:
            self.leads_by_contact[r["contact_id"]].append(r["lead_id"])
        self.dup_children = defaultdict(list)
        for r in t["lead"]:
            if r["duplicate_of_lead_id"]:
                self.dup_children[r["duplicate_of_lead_id"]].append(r["lead_id"])
        self.scores = defaultdict(list)
        for r in sorted(t["lead_score"], key=lambda r: r["scored_at"]):
            self.scores[r["lead_id"]].append(r)
        self.comps = defaultdict(list)
        for r in t["lead_score_component"]:
            self.comps[r["score_id"]].append(r)
        self.tasks = defaultdict(list)
        for r in t["task"]:
            self.tasks[r["lead_id"]].append(r)
        self.opp = {r["opportunity_id"]: r for r in t["opportunity"]}
        self.opp_by_lead = {r["lead_id"]: r for r in t["opportunity"]}
        self.stages = defaultdict(list)
        for r in sorted(t["stage_history"], key=lambda r: (r["opportunity_id"], int(r["seq"]))):
            self.stages[r["opportunity_id"]].append(r)
        # activities are the biggest table: keep compact tuples grouped by lead
        self.acts = defaultdict(list)
        self.n_acts = 0
        with open(p("csv", "activity.csv"), newline="", encoding="utf-8") as f:
            rd = csv.reader(f)
            next(rd)
            for r in rd:
                self.acts[r[1]].append(r)
                self.n_acts += 1
        # ground truth (separate)
        gp = p("ground_truth")
        self.labels = {r["lead_id"]: r for r in read_csv(os.path.join(gp, "lead_labels.csv"))}
        self.anoms = read_csv(os.path.join(gp, "anomalies.csv"))
        self.anoms_by_lead = defaultdict(list)
        for a in self.anoms:
            a["lead_id"] = self._lead_of(a)
            if a["lead_id"]:
                self.anoms_by_lead[a["lead_id"]].append(a["issue_type"])
        self._build_rows()
        self._build_overview()

    # ----------------------------------------------------------------- helpers
    def _lead_of(self, a):
        rid = a["record_id"]
        if rid in self.lead:
            return rid
        if rid in self.opp:
            return self.opp[rid]["lead_id"]
        if rid in self.contact:
            ls = self.leads_by_contact.get(rid)
            return ls[0] if ls else None
        m = LEAD_ID_RE.search(rid)
        return m.group(1) if m else None

    def _initial(self, lead_id):
        for s in self.scores.get(lead_id, ()):
            if s["trigger"] == "initial":
                return s
        return None

    def _optout(self, contact_id):
        return self.cidx.opted_out_everywhere(contact_id, self.as_of)

    def _build_rows(self):
        self.rows = []
        for l in self.t["lead"]:
            c, ct = self.company[l["company_id"]], self.contact[l["contact_id"]]
            s, o = self._initial(l["lead_id"]), self.opp_by_lead.get(l["lead_id"])
            self.rows.append(dict(
                lead_id=l["lead_id"], company=c["company_name"], company_id=c["company_id"], contact=f"{ct['first_name']} {ct['last_name']}",
                contact_id=ct["contact_id"], email=ct["email"], source=l["source"], product=l["product_interest"], territory=l["territory"],
                created=l["created_at"][:10], tier=s["tier"] if s else None, score=int(s["total_score"]) if s else None, status=l["status"],
                rep_id=l["assigned_rep_id"], rep=self.rep[l["assigned_rep_id"]]["rep_name"], opp_id=o["opportunity_id"] if o else None,
                opp_status=o["status"] if o else None, opp_stage=o["current_stage"] if o else None,
                amount=float(o["amount_usd"]) if o else None, duplicate_of=l["duplicate_of_lead_id"] or None,
                opted_out=self._optout(l["contact_id"]), n_acts=len(self.acts.get(l["lead_id"], ()))))
        self.row_by_id = {r["lead_id"]: r for r in self.rows}

    def _build_overview(self):
        L, O = self.t["lead"], self.t["opportunity"]
        dup = sum(1 for l in L if l["duplicate_of_lead_id"])
        done = {t["lead_id"] for t in self.t["task"] if t["status"] == "completed"}
        st = Counter(o["status"] for o in O)
        stage = Counter(o["current_stage"] for o in O)
        money = defaultdict(float)
        for o in O:
            money[o["status"]] += float(o["amount_usd"])
        init = [s for s in self.t["lead_score"] if s["trigger"] == "initial"]
        by_src = defaultdict(lambda: [0, 0])
        for r in self.rows:
            if r["duplicate_of"]:
                continue
            by_src[r["source"]][0] += 1
            by_src[r["source"]][1] += r["opp_id"] is not None
        months = Counter(l["created_at"][:7] for l in L)
        omonths = Counter(o["created_at"][:7] for o in O)
        keys = sorted(set(months) | set(omonths))
        closed = st["won"] + st["lost"]
        self.overview = dict(
            as_of=self.as_of, seed=self.cfg["seed"],
            counts=dict(companies=len(self.t["company"]), contacts=len(self.t["contact"]), leads=len(L), opportunities=len(O),
                        activities=self.n_acts, tasks=len(self.t["task"]), consents=len(self.t["consent"]), reps=len(self.t["sales_rep"])),
            funnel=[dict(label="All leads", value=len(L)), dict(label="Master leads (after dedupe)", value=len(L) - dup),
                    dict(label="Scored", value=len(init)), dict(label="Follow-up completed", value=len(done)),
                    dict(label="Opportunities", value=len(O)), dict(label="Won", value=st["won"])],
            duplicates=dup, status=dict(Counter(l["status"] for l in L)), tiers=dict(sorted(Counter(s["tier"] for s in init).items())),
            sources=[dict(source=k, leads=v[0], converted=v[1], rate=v[1] / v[0] if v[0] else 0) for k, v in sorted(by_src.items())],
            territories=dict(Counter(l["territory"] for l in L)), products=dict(Counter(l["product_interest"] for l in L)),
            monthly=[dict(month=k, leads=months[k], opportunities=omonths[k]) for k in keys],
            opp_status=dict(st), opp_stage=dict(stage), opp_value={k: round(v, 2) for k, v in money.items()},
            win_rate=st["won"] / closed if closed else None,
            tasks=dict(Counter(t["status"] for t in self.t["task"])),
            consent=dict(opted_out_contacts=sum(1 for c in self.contact if self._optout(c)),
                         opt_out_events=sum(1 for c in self.t["consent"] if c["status"] == "opt_out")))

    # ------------------------------------------------------------------ queries
    def query_leads(self, q="", tier="", status="", source="", territory="", product="", flag="", sort="created", direction="desc",
                    page=1, size=25, truth=False):
        rows = self.rows
        ql = q.strip().lower()
        if ql:
            rows = [r for r in rows if ql in r["lead_id"].lower() or ql in r["company"].lower() or ql in r["contact"].lower() or ql in r["email"].lower()]
        for key, val in (("tier", tier), ("status", status), ("source", source), ("territory", territory), ("product", product)):
            if val:
                rows = [r for r in rows if r[key] == val]
        if flag == "duplicate":
            rows = [r for r in rows if r["duplicate_of"]]
        elif flag == "opted_out":
            rows = [r for r in rows if r["opted_out"]]
        elif flag == "has_opportunity":
            rows = [r for r in rows if r["opp_id"]]
        elif flag == "high_score_non_converter" and truth:
            rows = [r for r in rows if self.labels[r["lead_id"]]["is_high_score_non_converter"] == "1"]
        elif flag == "has_anomaly" and truth:
            rows = [r for r in rows if r["lead_id"] in self.anoms_by_lead]
        key = SORTABLE.get(sort, "created")
        rev = direction != "asc"
        rows = sorted(rows, key=lambda r: ((r[key] is None), r[key] if r[key] is not None else 0, r["lead_id"]), reverse=rev)
        if rev:   # keep None values last when descending
            rows = [r for r in rows if r[key] is not None] + [r for r in rows if r[key] is None]
        out = _page(rows, page, size)
        if truth:
            out["rows"] = [dict(r, truth=dict(converted=self.labels[r["lead_id"]]["converted"] == "1", blocker=self.labels[r["lead_id"]]["hidden_blocker"] or None,
                                                anomalies=self.anoms_by_lead.get(r["lead_id"], []))) for r in out["rows"]]
        return out

    def lead_detail(self, lead_id, truth=False):
        l = self.lead.get(lead_id)
        if not l:
            return None
        c, ct = self.company[l["company_id"]], self.contact[l["contact_id"]]
        acts = [dict(activity_id=a[0], activity_type=a[2], direction=a[3], channel=a[4], occurred_at=a[5], rep_id=a[6] or None, task_id=a[7] or None)
                for a in self.acts.get(lead_id, ())]
        for a in acts:
            need = ref.ACTIVITY_TYPES[a["activity_type"]][2]
            a["consent_ok"] = True if not need else self.cidx.has_consent(l["contact_id"], need, a["occurred_at"])
        scores = []
        for s in self.scores.get(lead_id, ()):
            comps = [dict(rule_id=x["rule_id"], description=self.rules[x["rule_id"]]["description"], category=self.rules[x["rule_id"]]["category"],
                          units=int(x["units"]), points=int(x["points"])) for x in self.comps[s["score_id"]]]
            comps.sort(key=lambda x: -abs(x["points"]))
            scores.append(dict(s, components=comps))
        o = self.opp_by_lead.get(lead_id)
        opp = None
        if o:
            opp = dict(o, stages=self.stages[o["opportunity_id"]])
        checks = self._checks(l, c, ct, acts, scores, opp)
        d = dict(lead=l, company=c, contact=ct, rep=self.rep[l["assigned_rep_id"]], campaign=self.campaign.get(l["campaign_id"]),
                 consent=self.consent_by_contact[l["contact_id"]], scores=scores, activities=acts, tasks=self.tasks.get(lead_id, []),
                 opportunity=opp, duplicate_of=l["duplicate_of_lead_id"] or None, duplicates=self.dup_children.get(lead_id, []),
                 other_leads=[x for x in self.leads_by_contact[l["contact_id"]] if x != lead_id], checks=checks, row=self.row_by_id[lead_id])
        if truth:
            lab = self.labels[lead_id]
            d["truth"] = dict(labels=lab, anomalies=[a for a in self.anoms if a["lead_id"] == lead_id])
        return d

    def _checks(self, l, c, ct, acts, scores, opp):
        out = []
        t = lambda name, ok, detail="": out.append(dict(name=name, status="pass" if ok else "fail", detail=detail))
        bad = []
        for s in scores:
            feat = scoring.extract_features(c, ct, l, [dict(activity_type=a["activity_type"], direction=a["direction"], occurred_at=a["occurred_at"]) for a in acts], s["scored_at"])
            res = scoring.score_lead(feat, self.t["score_rule"], s["scored_at"])
            if res["raw"] != int(s["raw_score"]):
                bad.append(s["score_id"])
        t("Score reproducible from source rows", not bad and bool(scores) or not scores, "recomputed every score from activities up to its timestamp" if scores else "duplicate leads are not scored")
        if opp and scores:
            late = [s["score_id"] for s in scores if s["scored_at"] >= opp["created_at"]]
            t("Scores use only pre-conversion data", not late, f"{', '.join(late)} computed after the opportunity was created" if late else "every score precedes the opportunity")
        ok = (l["assigned_rep_id"], l["territory"], l["product_interest"]) in self.cover
        t("Routed to a rep covering territory × product", ok, f"{l['assigned_rep_id']} for {l['territory']} / {l['product_interest']}")
        viol = [a for a in acts if not a["consent_ok"]]
        t("Every outbound contact had consent", not viol, f"{len(viol)} outbound activity without active consent" if viol else "all outbound activity covered by an opt-in period")
        if opp:
            h = self.stages[opp["opportunity_id"]]
            gap = [int(r["seq"]) for r in h] != list(range(1, len(h) + 1)) or any(b["from_stage"] != a["to_stage"] for a, b in zip(h, h[1:]))
            t("Stage history is continuous", not gap, "missing a transition event" if gap else f"{len(h)} consecutive events")
        if l["duplicate_of_lead_id"]:
            t("Not a duplicate", False, f"duplicate of {l['duplicate_of_lead_id']}" + (" yet it has its own opportunity" if opp else ""))
        return out

    def query_opps(self, stage="", status="", product="", page=1, size=25, sort="created", direction="desc"):
        rows = [r for r in self.rows if r["opp_id"]]
        if stage:
            rows = [r for r in rows if r["opp_stage"] == stage]
        if status:
            rows = [r for r in rows if r["opp_status"] == status]
        if product:
            rows = [r for r in rows if r["product"] == product]
        key = "amount" if sort == "amount" else "created"
        rows = sorted(rows, key=lambda r: (r[key], r["opp_id"]), reverse=direction != "asc")
        out = _page(rows, page, size)
        stages = []
        for s in ref.STAGES:
            ops = [o for o in self.t["opportunity"] if o["current_stage"] == s]
            stages.append(dict(stage=s, count=len(ops), amount=round(sum(float(o["amount_usd"]) for o in ops), 2)))
        out["stages"] = stages
        return out

    def anomalies(self):
        c = Counter(a["issue_type"] for a in self.anoms)
        return dict(counts=dict(sorted(c.items())), rows=self.anoms)

    def dictionary(self):
        tables = [dict(name=t.name, pk=list(t.pk), description=t.description, lifecycle=t.lifecycle, rows=len(self.t.get(t.filename, [])) if t.filename != "activity" else self.n_acts,
                       columns=[dict(name=c.name, type=c.type, required=c.required, allowed=[str(a) for a in c.allowed], unit=c.unit, unique=c.unique or (c.name in t.pk and len(t.pk) == 1),
                                     fk=c.fk, pattern=c.pattern, rule=c.rule) for c in t.cols]) for t in schema.TABLES]
        return dict(tables=tables, relationships=[dict(parent=a, child=b, cardinality=c, optionality=d) for a, b, c, d in schema.RELATIONSHIPS],
                    rules=sorted(self.t["score_rule"], key=lambda r: (r["rule_version"], r["rule_id"])), tier_thresholds=scoring.TIER_THRESHOLDS)

    def json_file(self, name):
        p = os.path.join(self.out, name)
        return json.load(open(p)) if os.path.exists(p) else None
