"""Single source of truth: drives the SQL DDL, the data dictionary and the validator."""
from dataclasses import dataclass
from . import reference as ref

LEAD_STATUSES = ("New", "Working", "Qualified", "Converted", "Disqualified", "Duplicate", "Stale")
ROUTING_RULES = ("territory_product_least_loaded", "duplicate_follows_master")
OUTCOME_REASONS = tuple(dict.fromkeys(ref.WIN_REASONS + ref.LOSS_REASONS))
CAMPAIGN_CHANNELS = tuple(s for s in ref.SOURCES if s != "organic_search")
TIERS = ("A", "B", "C", "D")


@dataclass(frozen=True)
class Col:
    name: str
    type: str            # text | integer | real | date | datetime | bool
    required: bool = True
    allowed: tuple = ()
    unit: str = ""
    unique: bool = False
    rule: str = ""
    fk: str = ""         # "Table.column"
    pattern: str = ""


@dataclass(frozen=True)
class Table:
    name: str
    filename: str
    pk: tuple
    cols: tuple
    description: str
    lifecycle: str = ""

    @property
    def col_names(self):
        return [c.name for c in self.cols]


def C(name, type_, req=True, allowed=(), unit="", unique=False, rule="", fk="", pattern=""):
    return Col(name, type_, req, tuple(allowed), unit, unique, rule, fk, pattern)


TABLES = (
    Table("Company", "company", ("company_id",), (
        C("company_id", "text", pattern=r"^CO-\d{6}$", unique=True, rule="CO-000001 sequence by created_at, immutable"),
        C("company_name", "text", unique=True),
        C("domain", "text", unique=True, pattern=r"^[a-z0-9]+\.example$", rule="reserved .example TLD: no real domains"),
        C("industry", "text", allowed=ref.INDUSTRIES),
        C("employee_count", "integer", unit="employees", rule=">= 1"),
        C("employee_band", "text", allowed=ref.BAND_LABELS, rule="derived: must equal band_of(employee_count)"),
        C("annual_revenue_usd", "real", unit="USD", rule="> 0; ~ employees x revenue/employee"),
        C("country", "text", allowed=ref.COUNTRIES, unit="ISO-3166 alpha-2"),
        C("territory", "text", allowed=ref.TERRITORIES, rule="derived from country"),
        C("created_at", "datetime", unit="UTC", rule="<= first contact created_at"),
    ), "Master data: prospect organisations.", "Created once; never deleted."),
    Table("Contact", "contact", ("contact_id",), (
        C("contact_id", "text", pattern=r"^CON-\d{6}$", unique=True),
        C("company_id", "text", fk="Company.company_id"),
        C("first_name", "text"), C("last_name", "text"),
        C("email", "text", rule="syntactically valid; NOT unique across duplicate records (dedupe key = normalised email)"),
        C("email_type", "text", allowed=("corporate", "free")),
        C("phone", "text", req=False, pattern=r"^\+\d{1,3}-555-\d{4}$", rule="fictional 555 numbers only"),
        C("job_title", "text"),
        C("seniority", "text", allowed=tuple(ref.SENIORITY)),
        C("created_at", "datetime", unit="UTC", rule="= created_at of the contact's first lead"),
        C("duplicate_of_contact_id", "text", req=False, fk="Contact.contact_id",
          rule="set by the dedupe step; NULL for master records"),
    ), "Master data: people at companies.", "Duplicate records are kept and linked, never deleted or merged away."),
    Table("Campaign", "campaign", ("campaign_id",), (
        C("campaign_id", "text", pattern=r"^CMP-\d{3}$", unique=True),
        C("campaign_name", "text"),
        C("channel", "text", allowed=CAMPAIGN_CHANNELS, rule="equals the source of leads attributed to it"),
        C("product_focus", "text", req=False, allowed=ref.PRODUCTS, rule="NULL = all products"),
        C("start_date", "date"), C("end_date", "date", rule=">= start_date"),
        C("budget_usd", "real", unit="USD", rule="> 0"),
        C("status", "text", allowed=("planned", "active", "completed"), rule="derived from dates vs as_of"),
    ), "Marketing campaigns that source leads. organic_search leads have no campaign (optional FK).", "planned -> active -> completed (derived)."),
    Table("SalesRep", "sales_rep", ("rep_id",), (
        C("rep_id", "text", pattern=r"^REP-\d{3}$", unique=True),
        C("rep_name", "text"),
        C("territory", "text", allowed=ref.TERRITORIES, rule="home territory"),
        C("hire_date", "date"),
        C("is_active", "bool", rule="inactive reps are never routed new leads"),
    ), "Sales representatives.", ""),
    Table("RepCoverage", "rep_coverage", ("rep_id", "territory", "product"), (
        C("rep_id", "text", fk="SalesRep.rep_id"),
        C("territory", "text", allowed=ref.TERRITORIES),
        C("product", "text", allowed=ref.PRODUCTS),
        C("effective_from", "datetime", unit="UTC"),
        C("effective_to", "datetime", req=False, rule="exclusive upper bound; NULL = open-ended"),
    ), "Bridge table SalesRep N:M (territory x product); the routing rulebook.", ""),
    Table("Consent", "consent", ("consent_id",), (
        C("consent_id", "text", pattern=r"^CNS-\d{6}$", unique=True),
        C("contact_id", "text", fk="Contact.contact_id"),
        C("channel", "text", allowed=("email", "phone")),
        C("status", "text", allowed=("opt_in", "opt_out")),
        C("effective_from", "datetime", unit="UTC"),
        C("effective_to", "datetime", req=False, rule="exclusive upper bound; NULL = current. Periods per (contact, channel) are contiguous and non-overlapping"),
        C("capture_method", "text", allowed=("web_form", "event_badge_scan", "partner_transfer", "sales_call", "user_request")),
    ), "Consent as an append-only timeline per contact and channel. No consent record => no outbound contact.",
        "opt_in -> opt_out -> (optionally) opt_in; each change is a new row, old rows are closed with effective_to."),
    Table("Lead", "lead", ("lead_id",), (
        C("lead_id", "text", pattern=r"^LEAD-\d{4}-\d{6}$", unique=True),
        C("contact_id", "text", fk="Contact.contact_id"),
        C("company_id", "text", fk="Company.company_id", rule="must equal the contact's company_id"),
        C("campaign_id", "text", req=False, fk="Campaign.campaign_id"),
        C("consent_id", "text", fk="Consent.consent_id", rule="the email consent period in force at created_at"),
        C("source", "text", allowed=ref.SOURCES),
        C("product_interest", "text", allowed=ref.PRODUCTS),
        C("territory", "text", allowed=ref.TERRITORIES, rule="derived from company territory"),
        C("created_at", "datetime", unit="UTC", rule="within the campaign window when campaign_id is set"),
        C("assigned_rep_id", "text", req=False, fk="SalesRep.rep_id", rule="rep must cover (territory, product) in RepCoverage and be active"),
        C("routed_at", "datetime", req=False, rule=">= created_at"),
        C("routing_rule", "text", req=False, allowed=ROUTING_RULES),
        C("status", "text", allowed=LEAD_STATUSES,
          rule="DERIVED SNAPSHOT as of as_of; depends on outcomes (e.g. Converted) - NOT a legitimate model feature"),
        C("duplicate_of_lead_id", "text", req=False, fk="Lead.lead_id", rule="set by dedupe step"),
    ), "A marketing/sales inquiry. Core transactional entity.",
        "New -> Working -> Qualified -> Converted; side exits Disqualified / Stale / Duplicate (derived snapshot; history lives in Activity/Task/StageHistory)."),
    Table("Task", "task", ("task_id",), (
        C("task_id", "text", pattern=r"^TASK-LEAD-\d{4}-\d{6}-\d{3}$", unique=True),
        C("lead_id", "text", fk="Lead.lead_id"),
        C("rep_id", "text", fk="SalesRep.rep_id", rule="= lead.assigned_rep_id"),
        C("task_type", "text", allowed=("call", "email", "demo")),
        C("priority", "text", allowed=("high", "medium", "low"), rule="from score tier: A/B high-medium, C low"),
        C("created_at", "datetime", rule="= initial score time"),
        C("due_at", "datetime", rule=">= created_at"),
        C("completed_at", "datetime", req=False, rule=">= created_at; only when status = completed"),
        C("status", "text", allowed=("open", "completed", "overdue", "cancelled")),
        C("cancel_reason", "text", req=False, allowed=("no_consent", "opted_out"), rule="required iff status = cancelled"),
    ), "Follow-up tasks created from score tier. Consent-gated.", "open -> completed | overdue | cancelled (derived at as_of)."),
    Table("Activity", "activity", ("activity_id",), (
        C("activity_id", "text", pattern=r"^ACT-LEAD-\d{4}-\d{6}-\d{3}$", unique=True, rule="ACT-<lead-id>-NNN in time order"),
        C("lead_id", "text", fk="Lead.lead_id"),
        C("activity_type", "text", allowed=tuple(ref.ACTIVITY_TYPES)),
        C("direction", "text", allowed=("inbound", "outbound"), rule="fixed by activity_type"),
        C("channel", "text", allowed=("web", "email", "phone", "video"), rule="fixed by activity_type"),
        C("occurred_at", "datetime", rule=">= lead.created_at"),
        C("rep_id", "text", req=False, fk="SalesRep.rep_id"),
        C("task_id", "text", req=False, fk="Task.task_id"),
    ), "Immutable activity history per lead.", "Append-only."),
    Table("ScoreRule", "score_rule", ("rule_id",), (
        C("rule_id", "text", pattern=r"^SR-v\d-\d{3}$", unique=True),
        C("rule_version", "integer"),
        C("category", "text", allowed=("fit", "intent", "engagement")),
        C("feature", "text"),
        C("operator", "text", allowed=("eq", "gte", "per_unit")),
        C("value", "text", rule="eq: compared as text; gte: numeric threshold; per_unit: unused"),
        C("points", "integer", unit="score points", rule="may be negative"),
        C("cap_units", "integer", req=False, rule="per_unit only: max units counted"),
        C("effective_from", "datetime"),
        C("effective_to", "datetime", req=False, rule="exclusive upper bound"),
        C("description", "text"),
    ), "Transparent, versioned scoring rules (effective-dated).", "v1 superseded by v2 on 2026-06-01; v1 rows are kept."),
    Table("LeadScore", "lead_score", ("score_id",), (
        C("score_id", "text", pattern=r"^SCR-LEAD-\d{4}-\d{6}-\d{2}$", unique=True),
        C("lead_id", "text", fk="Lead.lead_id"),
        C("scored_at", "datetime", rule="score uses only activities with occurred_at <= scored_at"),
        C("rule_version", "integer", rule="version effective at scored_at"),
        C("raw_score", "integer", rule="= sum of component points"),
        C("total_score", "integer", unit="0-100", rule="= clamp(raw_score, 0, 100)"),
        C("tier", "text", allowed=TIERS, rule="A>=55, B>=40, C>=25, else D"),
        C("trigger", "text", allowed=("initial", "rescore"), rule="model evaluation must use trigger = initial"),
    ), "Score events (append-only). One 'initial' score per non-duplicate lead.", ""),
    Table("LeadScoreComponent", "lead_score_component", ("score_id", "rule_id"), (
        C("score_id", "text", fk="LeadScore.score_id"),
        C("rule_id", "text", fk="ScoreRule.rule_id"),
        C("units", "integer", rule=">= 1"),
        C("points", "integer", rule="= rule.points x units"),
    ), "Bridge Lead(Score) N:M ScoreRule: explains every score (traceability).", ""),
    Table("Opportunity", "opportunity", ("opportunity_id",), (
        C("opportunity_id", "text", pattern=r"^OPP-\d{4}-\d{6}$", unique=True),
        C("lead_id", "text", fk="Lead.lead_id", unique=True, rule="at most one opportunity per lead"),
        C("company_id", "text", fk="Company.company_id"),
        C("contact_id", "text", fk="Contact.contact_id"),
        C("rep_id", "text", fk="SalesRep.rep_id"),
        C("product", "text", allowed=ref.PRODUCTS),
        C("amount_usd", "real", unit="USD", rule="> 0"),
        C("created_at", "datetime", rule=">= lead score time"),
        C("current_stage", "text", allowed=ref.STAGES, rule="= to_stage of the latest StageHistory row"),
        C("status", "text", allowed=("open", "won", "lost"), rule="derived from current_stage"),
        C("closed_at", "datetime", req=False, rule="= changed_at of the closing StageHistory row"),
        C("outcome_reason", "text", req=False, allowed=OUTCOME_REASONS, rule="required iff status in (won, lost)"),
    ), "Sales opportunity created from a converted lead.", "Qualification -> Discovery -> Proposal -> Negotiation -> Closed Won | Closed Lost."),
    Table("StageHistory", "stage_history", ("stage_history_id",), (
        C("stage_history_id", "text", pattern=r"^STG-OPP-\d{4}-\d{6}-\d{2}$", unique=True),
        C("opportunity_id", "text", fk="Opportunity.opportunity_id"),
        C("seq", "integer", rule="1..n consecutive per opportunity"),
        C("from_stage", "text", req=False, allowed=ref.STAGES, rule="NULL only for seq 1"),
        C("to_stage", "text", allowed=ref.STAGES),
        C("changed_at", "datetime", rule="non-decreasing within an opportunity"),
        C("transition_reason", "text"),
    ), "Append-only stage-transition events; the opportunity's history is never overwritten.", ""),
)
SCHEMA = {t.name: t for t in TABLES}

RELATIONSHIPS = [
    ("Company", "Contact", "1:N", "required"), ("Company", "Lead", "1:N", "required (denormalised, must match contact's company)"),
    ("Contact", "Lead", "1:N", "required"), ("Contact", "Consent", "1:N", "required (>=1 email timeline)"),
    ("Consent", "Lead", "1:N", "required (consent period in force at capture)"),
    ("Campaign", "Lead", "1:N", "OPTIONAL (organic leads have none)"),
    ("SalesRep", "RepCoverage", "1:N", "required"), ("SalesRep", "Lead", "1:N", "required after routing"),
    ("SalesRep", "Task", "1:N", "required"), ("Lead", "Task", "1:N", "optional (tier D and duplicates get none)"),
    ("Lead", "Activity", "1:N", "required (>=1 form_submit)"), ("Task", "Activity", "1:N", "optional"),
    ("Lead", "LeadScore", "1:N", "optional (duplicates are not scored)"),
    ("LeadScore", "ScoreRule", "N:M", "via LeadScoreComponent bridge"),
    ("Lead", "Opportunity", "1:0..1", "optional"), ("Opportunity", "StageHistory", "1:N", "required"),
    ("Contact", "Contact", "1:N", "optional self-reference (duplicate_of_contact_id)"),
    ("Lead", "Lead", "1:N", "optional self-reference (duplicate_of_lead_id)"),
]

_SQL_T = {"text": "TEXT", "integer": "INTEGER", "real": "REAL", "date": "TEXT", "datetime": "TEXT", "bool": "INTEGER"}


def ddl():
    out = []
    for t in TABLES:
        lines = []
        for c in t.cols:
            s = f"  {c.name} {_SQL_T[c.type]}"
            if c.required:
                s += " NOT NULL"
            if c.unique and c.name not in t.pk:
                s += " UNIQUE"
            if c.allowed:
                s += " CHECK ({} IN ({}))".format(c.name, ", ".join("'%s'" % a for a in c.allowed))
            if c.type == "bool":
                s += f" CHECK ({c.name} IN (0, 1))"
            lines.append(s)
        lines.append(f"  PRIMARY KEY ({', '.join(t.pk)})")
        for c in t.cols:
            if c.fk:
                tb, col = c.fk.split(".")
                lines.append(f"  FOREIGN KEY ({c.name}) REFERENCES {tb}({col})")
        out.append(f"CREATE TABLE {t.name} (\n" + ",\n".join(lines) + "\n);")
    return "\n\n".join(out) + "\n"


def data_dictionary_md():
    L = ["# Data Dictionary", "",
         "_Generated from `leadgen/schema.py` (single source of truth for DDL, this document and the validator)._", "",
         "Conventions: timestamps are naive UTC ISO-8601 (`YYYY-MM-DDTHH:MM:SS`); `effective_to` is an **exclusive** upper bound; "
         "empty CSV cell = NULL; all names/domains/phones are fictional (`.example` TLD, `555` numbers).", "",
         "## Relationships and cardinality", "", "| Parent | Child | Cardinality | Optionality |", "|---|---|---|---|"]
    L += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in RELATIONSHIPS]
    L += ["", "## ID conventions", "",
          "`CO-000001`, `CON-000001`, `LEAD-2026-000001`, `ACT-<lead-id>-001`, `OPP-2026-000001`, `TASK-<lead-id>-001`; "
          "additionally `CMP-001`, `REP-001`, `CNS-000001`, `SR-v1-001`, `SCR-<lead-id>-01`, `STG-<opp-id>-01`. "
          "Counters are zero-padded and assigned in `created_at` order; IDs are immutable and identical across files.", ""]
    for t in TABLES:
        L += [f"## {t.name}", "", t.description, ""]
        if t.lifecycle:
            L += [f"**Lifecycle:** {t.lifecycle}", ""]
        L += [f"**Primary key:** `{', '.join(t.pk)}`", "",
              "| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |", "|---|---|---|---|---|---|---|---|"]
        for c in t.cols:
            allowed = ", ".join(c.allowed) if c.allowed else (f"`{c.pattern}`" if c.pattern else "")
            L.append(f"| `{c.name}` | {c.type} | {'Y' if c.required else 'N'} | {allowed} | {c.unit} | "
                     f"{'Y' if c.unique or (c.name in t.pk and len(t.pk) == 1) else ''} | {c.fk} | {c.rule} |")
        L.append("")
    return "\n".join(L)
