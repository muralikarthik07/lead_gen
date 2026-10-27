# Data Dictionary

_Generated from `leadgen/schema.py` (single source of truth for DDL, this document and the validator)._

Conventions: timestamps are naive UTC ISO-8601 (`YYYY-MM-DDTHH:MM:SS`); `effective_to` is an **exclusive** upper bound; empty CSV cell = NULL; all names/domains/phones are fictional (`.example` TLD, `555` numbers).

## Relationships and cardinality

| Parent | Child | Cardinality | Optionality |
|---|---|---|---|
| Company | Contact | 1:N | required |
| Company | Lead | 1:N | required (denormalised, must match contact's company) |
| Contact | Lead | 1:N | required |
| Contact | Consent | 1:N | required (>=1 email timeline) |
| Consent | Lead | 1:N | required (consent period in force at capture) |
| Campaign | Lead | 1:N | OPTIONAL (organic leads have none) |
| SalesRep | RepCoverage | 1:N | required |
| SalesRep | Lead | 1:N | required after routing |
| SalesRep | Task | 1:N | required |
| Lead | Task | 1:N | optional (tier D and duplicates get none) |
| Lead | Activity | 1:N | required (>=1 form_submit) |
| Task | Activity | 1:N | optional |
| Lead | LeadScore | 1:N | optional (duplicates are not scored) |
| LeadScore | ScoreRule | N:M | via LeadScoreComponent bridge |
| Lead | Opportunity | 1:0..1 | optional |
| Opportunity | StageHistory | 1:N | required |
| Contact | Contact | 1:N | optional self-reference (duplicate_of_contact_id) |
| Lead | Lead | 1:N | optional self-reference (duplicate_of_lead_id) |

## ID conventions

`CO-000001`, `CON-000001`, `LEAD-2026-000001`, `ACT-<lead-id>-001`, `OPP-2026-000001`, `TASK-<lead-id>-001`; additionally `CMP-001`, `REP-001`, `CNS-000001`, `SR-v1-001`, `SCR-<lead-id>-01`, `STG-<opp-id>-01`. Counters are zero-padded and assigned in `created_at` order; IDs are immutable and identical across files.

## Company

Master data: prospect organisations.

**Lifecycle:** Created once; never deleted.

**Primary key:** `company_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `company_id` | text | Y | `^CO-\d{6}$` |  | Y |  | CO-000001 sequence by created_at, immutable |
| `company_name` | text | Y |  |  | Y |  |  |
| `domain` | text | Y | `^[a-z0-9]+\.example$` |  | Y |  | reserved .example TLD: no real domains |
| `industry` | text | Y | Software, Financial Services, Healthcare, Manufacturing, Retail, Education, Logistics, Energy, Media, Public Sector |  |  |  |  |
| `employee_count` | integer | Y |  | employees |  |  | >= 1 |
| `employee_band` | text | Y | 1-10, 11-50, 51-200, 201-1000, 1000+ |  |  |  | derived: must equal band_of(employee_count) |
| `annual_revenue_usd` | real | Y |  | USD |  |  | > 0; ~ employees x revenue/employee |
| `country` | text | Y | US, CA, BR, MX, AR, CL, CO, GB, DE, NL, SE, IE, FR, ES, IT, AE, ZA, PT, AU, SG, JP, IN | ISO-3166 alpha-2 |  |  |  |
| `territory` | text | Y | NORAM, LATAM, EMEA-N, EMEA-S, APAC, INDIA |  |  |  | derived from country |
| `created_at` | datetime | Y |  | UTC |  |  | <= first contact created_at |

## Contact

Master data: people at companies.

**Lifecycle:** Duplicate records are kept and linked, never deleted or merged away.

**Primary key:** `contact_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `contact_id` | text | Y | `^CON-\d{6}$` |  | Y |  |  |
| `company_id` | text | Y |  |  |  | Company.company_id |  |
| `first_name` | text | Y |  |  |  |  |  |
| `last_name` | text | Y |  |  |  |  |  |
| `email` | text | Y |  |  |  |  | syntactically valid; NOT unique across duplicate records (dedupe key = normalised email) |
| `email_type` | text | Y | corporate, free |  |  |  |  |
| `phone` | text | N | `^\+\d{1,3}-555-\d{4}$` |  |  |  | fictional 555 numbers only |
| `job_title` | text | Y |  |  |  |  |  |
| `seniority` | text | Y | c_level, vp, director, manager, individual |  |  |  |  |
| `created_at` | datetime | Y |  | UTC |  |  | = created_at of the contact's first lead |
| `duplicate_of_contact_id` | text | N |  |  |  | Contact.contact_id | set by the dedupe step; NULL for master records |

## Campaign

Marketing campaigns that source leads. organic_search leads have no campaign (optional FK).

**Lifecycle:** planned -> active -> completed (derived).

**Primary key:** `campaign_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `campaign_id` | text | Y | `^CMP-\d{3}$` |  | Y |  |  |
| `campaign_name` | text | Y |  |  |  |  |  |
| `channel` | text | Y | paid_search, webinar, trade_show, referral, partner, content_download |  |  |  | equals the source of leads attributed to it |
| `product_focus` | text | N | Platform, Analytics, Automation, Security |  |  |  | NULL = all products |
| `start_date` | date | Y |  |  |  |  |  |
| `end_date` | date | Y |  |  |  |  | >= start_date |
| `budget_usd` | real | Y |  | USD |  |  | > 0 |
| `status` | text | Y | planned, active, completed |  |  |  | derived from dates vs as_of |

## SalesRep

Sales representatives.

**Primary key:** `rep_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `rep_id` | text | Y | `^REP-\d{3}$` |  | Y |  |  |
| `rep_name` | text | Y |  |  |  |  |  |
| `territory` | text | Y | NORAM, LATAM, EMEA-N, EMEA-S, APAC, INDIA |  |  |  | home territory |
| `hire_date` | date | Y |  |  |  |  |  |
| `is_active` | bool | Y |  |  |  |  | inactive reps are never routed new leads |

## RepCoverage

Bridge table SalesRep N:M (territory x product); the routing rulebook.

**Primary key:** `rep_id, territory, product`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `rep_id` | text | Y |  |  |  | SalesRep.rep_id |  |
| `territory` | text | Y | NORAM, LATAM, EMEA-N, EMEA-S, APAC, INDIA |  |  |  |  |
| `product` | text | Y | Platform, Analytics, Automation, Security |  |  |  |  |
| `effective_from` | datetime | Y |  | UTC |  |  |  |
| `effective_to` | datetime | N |  |  |  |  | exclusive upper bound; NULL = open-ended |

## Consent

Consent as an append-only timeline per contact and channel. No consent record => no outbound contact.

**Lifecycle:** opt_in -> opt_out -> (optionally) opt_in; each change is a new row, old rows are closed with effective_to.

**Primary key:** `consent_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `consent_id` | text | Y | `^CNS-\d{6}$` |  | Y |  |  |
| `contact_id` | text | Y |  |  |  | Contact.contact_id |  |
| `channel` | text | Y | email, phone |  |  |  |  |
| `status` | text | Y | opt_in, opt_out |  |  |  |  |
| `effective_from` | datetime | Y |  | UTC |  |  |  |
| `effective_to` | datetime | N |  |  |  |  | exclusive upper bound; NULL = current. Periods per (contact, channel) are contiguous and non-overlapping |
| `capture_method` | text | Y | web_form, event_badge_scan, partner_transfer, sales_call, user_request |  |  |  |  |

## Lead

A marketing/sales inquiry. Core transactional entity.

**Lifecycle:** New -> Working -> Qualified -> Converted; side exits Disqualified / Stale / Duplicate (derived snapshot; history lives in Activity/Task/StageHistory).

**Primary key:** `lead_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `lead_id` | text | Y | `^LEAD-\d{4}-\d{6}$` |  | Y |  |  |
| `contact_id` | text | Y |  |  |  | Contact.contact_id |  |
| `company_id` | text | Y |  |  |  | Company.company_id | must equal the contact's company_id |
| `campaign_id` | text | N |  |  |  | Campaign.campaign_id |  |
| `consent_id` | text | Y |  |  |  | Consent.consent_id | the email consent period in force at created_at |
| `source` | text | Y | paid_search, organic_search, webinar, trade_show, referral, partner, content_download |  |  |  |  |
| `product_interest` | text | Y | Platform, Analytics, Automation, Security |  |  |  |  |
| `territory` | text | Y | NORAM, LATAM, EMEA-N, EMEA-S, APAC, INDIA |  |  |  | derived from company territory |
| `created_at` | datetime | Y |  | UTC |  |  | within the campaign window when campaign_id is set |
| `assigned_rep_id` | text | N |  |  |  | SalesRep.rep_id | rep must cover (territory, product) in RepCoverage and be active |
| `routed_at` | datetime | N |  |  |  |  | >= created_at |
| `routing_rule` | text | N | territory_product_least_loaded, duplicate_follows_master |  |  |  |  |
| `status` | text | Y | New, Working, Qualified, Converted, Disqualified, Duplicate, Stale |  |  |  | DERIVED SNAPSHOT as of as_of; depends on outcomes (e.g. Converted) - NOT a legitimate model feature |
| `duplicate_of_lead_id` | text | N |  |  |  | Lead.lead_id | set by dedupe step |

## Task

Follow-up tasks created from score tier. Consent-gated.

**Lifecycle:** open -> completed | overdue | cancelled (derived at as_of).

**Primary key:** `task_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `task_id` | text | Y | `^TASK-LEAD-\d{4}-\d{6}-\d{3}$` |  | Y |  |  |
| `lead_id` | text | Y |  |  |  | Lead.lead_id |  |
| `rep_id` | text | Y |  |  |  | SalesRep.rep_id | = lead.assigned_rep_id |
| `task_type` | text | Y | call, email, demo |  |  |  |  |
| `priority` | text | Y | high, medium, low |  |  |  | from score tier: A/B high-medium, C low |
| `created_at` | datetime | Y |  |  |  |  | = initial score time |
| `due_at` | datetime | Y |  |  |  |  | >= created_at |
| `completed_at` | datetime | N |  |  |  |  | >= created_at; only when status = completed |
| `status` | text | Y | open, completed, overdue, cancelled |  |  |  |  |
| `cancel_reason` | text | N | no_consent, opted_out |  |  |  | required iff status = cancelled |

## Activity

Immutable activity history per lead.

**Lifecycle:** Append-only.

**Primary key:** `activity_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `activity_id` | text | Y | `^ACT-LEAD-\d{4}-\d{6}-\d{3}$` |  | Y |  | ACT-<lead-id>-NNN in time order |
| `lead_id` | text | Y |  |  |  | Lead.lead_id |  |
| `activity_type` | text | Y | form_submit, web_visit, pricing_page_visit, content_download, demo_request, email_open, email_click, email_outbound, call_outbound, demo_delivered, proposal_sent, meeting |  |  |  |  |
| `direction` | text | Y | inbound, outbound |  |  |  | fixed by activity_type |
| `channel` | text | Y | web, email, phone, video |  |  |  | fixed by activity_type |
| `occurred_at` | datetime | Y |  |  |  |  | >= lead.created_at |
| `rep_id` | text | N |  |  |  | SalesRep.rep_id |  |
| `task_id` | text | N |  |  |  | Task.task_id |  |

## ScoreRule

Transparent, versioned scoring rules (effective-dated).

**Lifecycle:** v1 superseded by v2 on 2026-06-01; v1 rows are kept.

**Primary key:** `rule_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `rule_id` | text | Y | `^SR-v\d-\d{3}$` |  | Y |  |  |
| `rule_version` | integer | Y |  |  |  |  |  |
| `category` | text | Y | fit, intent, engagement |  |  |  |  |
| `feature` | text | Y |  |  |  |  |  |
| `operator` | text | Y | eq, gte, per_unit |  |  |  |  |
| `value` | text | Y |  |  |  |  | eq: compared as text; gte: numeric threshold; per_unit: unused |
| `points` | integer | Y |  | score points |  |  | may be negative |
| `cap_units` | integer | N |  |  |  |  | per_unit only: max units counted |
| `effective_from` | datetime | Y |  |  |  |  |  |
| `effective_to` | datetime | N |  |  |  |  | exclusive upper bound |
| `description` | text | Y |  |  |  |  |  |

## LeadScore

Score events (append-only). One 'initial' score per non-duplicate lead.

**Primary key:** `score_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `score_id` | text | Y | `^SCR-LEAD-\d{4}-\d{6}-\d{2}$` |  | Y |  |  |
| `lead_id` | text | Y |  |  |  | Lead.lead_id |  |
| `scored_at` | datetime | Y |  |  |  |  | score uses only activities with occurred_at <= scored_at |
| `rule_version` | integer | Y |  |  |  |  | version effective at scored_at |
| `raw_score` | integer | Y |  |  |  |  | = sum of component points |
| `total_score` | integer | Y |  | 0-100 |  |  | = clamp(raw_score, 0, 100) |
| `tier` | text | Y | A, B, C, D |  |  |  | A>=55, B>=40, C>=25, else D |
| `trigger` | text | Y | initial, rescore |  |  |  | model evaluation must use trigger = initial |

## LeadScoreComponent

Bridge Lead(Score) N:M ScoreRule: explains every score (traceability).

**Primary key:** `score_id, rule_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `score_id` | text | Y |  |  |  | LeadScore.score_id |  |
| `rule_id` | text | Y |  |  |  | ScoreRule.rule_id |  |
| `units` | integer | Y |  |  |  |  | >= 1 |
| `points` | integer | Y |  |  |  |  | = rule.points x units |

## Opportunity

Sales opportunity created from a converted lead.

**Lifecycle:** Qualification -> Discovery -> Proposal -> Negotiation -> Closed Won | Closed Lost.

**Primary key:** `opportunity_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `opportunity_id` | text | Y | `^OPP-\d{4}-\d{6}$` |  | Y |  |  |
| `lead_id` | text | Y |  |  | Y | Lead.lead_id | at most one opportunity per lead |
| `company_id` | text | Y |  |  |  | Company.company_id |  |
| `contact_id` | text | Y |  |  |  | Contact.contact_id |  |
| `rep_id` | text | Y |  |  |  | SalesRep.rep_id |  |
| `product` | text | Y | Platform, Analytics, Automation, Security |  |  |  |  |
| `amount_usd` | real | Y |  | USD |  |  | > 0 |
| `created_at` | datetime | Y |  |  |  |  | >= lead score time |
| `current_stage` | text | Y | Qualification, Discovery, Proposal, Negotiation, Closed Won, Closed Lost |  |  |  | = to_stage of the latest StageHistory row |
| `status` | text | Y | open, won, lost |  |  |  | derived from current_stage |
| `closed_at` | datetime | N |  |  |  |  | = changed_at of the closing StageHistory row |
| `outcome_reason` | text | N | product_fit, price, relationship, features, budget, competitor, no_decision, timing, not_a_fit |  |  |  | required iff status in (won, lost) |

## StageHistory

Append-only stage-transition events; the opportunity's history is never overwritten.

**Primary key:** `stage_history_id`

| Field | Type | Req | Allowed values / pattern | Unit | Unique | FK | Validation rule |
|---|---|---|---|---|---|---|---|
| `stage_history_id` | text | Y | `^STG-OPP-\d{4}-\d{6}-\d{2}$` |  | Y |  |  |
| `opportunity_id` | text | Y |  |  |  | Opportunity.opportunity_id |  |
| `seq` | integer | Y |  |  |  |  | 1..n consecutive per opportunity |
| `from_stage` | text | N | Qualification, Discovery, Proposal, Negotiation, Closed Won, Closed Lost |  |  |  | NULL only for seq 1 |
| `to_stage` | text | Y | Qualification, Discovery, Proposal, Negotiation, Closed Won, Closed Lost |  |  |  |  |
| `changed_at` | datetime | Y |  |  |  |  | non-decreasing within an opportunity |
| `transition_reason` | text | Y |  |  |  |  |  |
