# Validation summary: **PASS**

Invariants: 97/97 pass. Injected-anomaly detectors matching ground truth: 7/7.

## Row counts

- Company: 250
- Contact: 500
- Campaign: 34
- SalesRep: 41
- RepCoverage: 72
- Consent: 764
- Lead: 1,000
- Task: 1,122
- Activity: 19,724
- ScoreRule: 46
- LeadScore: 988
- LeadScoreComponent: 5,939
- Opportunity: 150
- StageHistory: 579

## Funnel reconciliation

- leads: 1,000
- duplicate_leads: 15
- master_leads: 985
- scored_leads: 985
- leads_with_tasks: 744
- leads_with_completed_task: 678
- opportunities: 150
- opps_from_master_leads: 148
- opps_from_duplicate_leads: 2
- open: 4
- won: 53
- lost: 93
- leads_status_converted: 148

## Injected edge cases: detector output vs ground truth

| issue_type | expected | detected | missing | unexpected | status |
|---|---|---|---|---|---|
| duplicate_contact | 15 | 15 | 0 | 0 | PASS |
| duplicate_creates_duplicate_opportunity | 2 | 2 | 0 | 0 | PASS |
| duplicate_lead | 15 | 15 | 0 | 0 | PASS |
| lead_assigned_outside_territory | 2 | 2 | 0 | 0 | PASS |
| opted_out_lead_contacted | 4 | 4 | 0 | 0 | PASS |
| score_uses_post_conversion_event | 3 | 3 | 0 | 0 | PASS |
| stage_history_gap | 2 | 2 | 0 | 0 | PASS |

## Invariant checks

| category | check | violations | status |
|---|---|---|---|
| primary_keys | Company: primary key unique | 0 | PASS |
| primary_keys | Company.company_name: unique | 0 | PASS |
| primary_keys | Company.domain: unique | 0 | PASS |
| schema | Company: required/type/enum/pattern | 0 | PASS |
| primary_keys | Contact: primary key unique | 0 | PASS |
| schema | Contact: required/type/enum/pattern | 0 | PASS |
| primary_keys | Campaign: primary key unique | 0 | PASS |
| schema | Campaign: required/type/enum/pattern | 0 | PASS |
| primary_keys | SalesRep: primary key unique | 0 | PASS |
| schema | SalesRep: required/type/enum/pattern | 0 | PASS |
| primary_keys | RepCoverage: primary key unique | 0 | PASS |
| schema | RepCoverage: required/type/enum/pattern | 0 | PASS |
| primary_keys | Consent: primary key unique | 0 | PASS |
| schema | Consent: required/type/enum/pattern | 0 | PASS |
| primary_keys | Lead: primary key unique | 0 | PASS |
| schema | Lead: required/type/enum/pattern | 0 | PASS |
| primary_keys | Task: primary key unique | 0 | PASS |
| schema | Task: required/type/enum/pattern | 0 | PASS |
| primary_keys | Activity: primary key unique | 0 | PASS |
| schema | Activity: required/type/enum/pattern | 0 | PASS |
| primary_keys | ScoreRule: primary key unique | 0 | PASS |
| schema | ScoreRule: required/type/enum/pattern | 0 | PASS |
| primary_keys | LeadScore: primary key unique | 0 | PASS |
| schema | LeadScore: required/type/enum/pattern | 0 | PASS |
| primary_keys | LeadScoreComponent: primary key unique | 0 | PASS |
| schema | LeadScoreComponent: required/type/enum/pattern | 0 | PASS |
| primary_keys | Opportunity: primary key unique | 0 | PASS |
| primary_keys | Opportunity.lead_id: unique | 0 | PASS |
| schema | Opportunity: required/type/enum/pattern | 0 | PASS |
| primary_keys | StageHistory: primary key unique | 0 | PASS |
| schema | StageHistory: required/type/enum/pattern | 0 | PASS |
| primary_keys | Company: IDs contiguous & zero-padded | 0 | PASS |
| primary_keys | Contact: IDs contiguous & zero-padded | 0 | PASS |
| primary_keys | Consent: IDs contiguous & zero-padded | 0 | PASS |
| foreign_keys | FK Contact.company_id -> Company.company_id | 0 | PASS |
| foreign_keys | FK Contact.duplicate_of_contact_id -> Contact.contact_id | 0 | PASS |
| foreign_keys | FK RepCoverage.rep_id -> SalesRep.rep_id | 0 | PASS |
| foreign_keys | FK Consent.contact_id -> Contact.contact_id | 0 | PASS |
| foreign_keys | FK Lead.contact_id -> Contact.contact_id | 0 | PASS |
| foreign_keys | FK Lead.company_id -> Company.company_id | 0 | PASS |
| foreign_keys | FK Lead.campaign_id -> Campaign.campaign_id | 0 | PASS |
| foreign_keys | FK Lead.consent_id -> Consent.consent_id | 0 | PASS |
| foreign_keys | FK Lead.assigned_rep_id -> SalesRep.rep_id | 0 | PASS |
| foreign_keys | FK Lead.duplicate_of_lead_id -> Lead.lead_id | 0 | PASS |
| foreign_keys | FK Task.lead_id -> Lead.lead_id | 0 | PASS |
| foreign_keys | FK Task.rep_id -> SalesRep.rep_id | 0 | PASS |
| foreign_keys | FK Activity.lead_id -> Lead.lead_id | 0 | PASS |
| foreign_keys | FK Activity.rep_id -> SalesRep.rep_id | 0 | PASS |
| foreign_keys | FK Activity.task_id -> Task.task_id | 0 | PASS |
| foreign_keys | FK LeadScore.lead_id -> Lead.lead_id | 0 | PASS |
| foreign_keys | FK LeadScoreComponent.score_id -> LeadScore.score_id | 0 | PASS |
| foreign_keys | FK LeadScoreComponent.rule_id -> ScoreRule.rule_id | 0 | PASS |
| foreign_keys | FK Opportunity.lead_id -> Lead.lead_id | 0 | PASS |
| foreign_keys | FK Opportunity.company_id -> Company.company_id | 0 | PASS |
| foreign_keys | FK Opportunity.contact_id -> Contact.contact_id | 0 | PASS |
| foreign_keys | FK Opportunity.rep_id -> SalesRep.rep_id | 0 | PASS |
| foreign_keys | FK StageHistory.opportunity_id -> Opportunity.opportunity_id | 0 | PASS |
| date_ordering | Contact.created_at >= Company.created_at | 0 | PASS |
| date_ordering | Contact.created_at == created_at of the contact's first lead; every contact has a lead | 0 | PASS |
| referential_semantics | Lead.company_id == Contact.company_id | 0 | PASS |
| derived_values | Lead.territory == Company.territory | 0 | PASS |
| date_ordering | Lead within campaign window and channel == source | 0 | PASS |
| date_ordering | Lead.routed_at >= created_at | 0 | PASS |
| date_ordering | Activity.occurred_at >= Lead.created_at | 0 | PASS |
| schema | Activity direction/channel match type | 0 | PASS |
| primary_keys | Activity IDs sequential & time-ordered per lead | 0 | PASS |
| date_ordering | Task due >= created, completed >= created, status/cancel_reason consistent | 0 | PASS |
| date_ordering | Opportunity.created_at > initial score time; >= lead.created_at | 0 | PASS |
| referential_semantics | Opportunity company/contact/rep consistent with lead | 0 | PASS |
| lifecycle | Consent timelines contiguous, non-overlapping, alternating | 0 | PASS |
| referential_semantics | Lead.consent_id is the email consent period in force at created_at | 0 | PASS |
| date_ordering | Campaign dates ordered | 0 | PASS |
| derived_values | Company.employee_band == band_of(employee_count) | 0 | PASS |
| derived_values | Company.territory == territory(country) | 0 | PASS |
| derived_values | Company revenue / amounts positive | 0 | PASS |
| derived_values | ScoreRule description states its own points/cap (per-unit rules) | 0 | PASS |
| arithmetic | Component points == rule.points x units | 0 | PASS |
| arithmetic | LeadScore raw == sum(components); total == clamp(raw); tier from thresholds | 0 | PASS |
| reproducibility | Score is reproducible from source rows (features, rule version, components) | 0 | PASS |
| derived_values | Every non-duplicate lead has exactly one initial score; duplicates have none | 0 | PASS |
| lifecycle | Opportunity.current_stage/status == latest StageHistory | 0 | PASS |
| lifecycle | Opportunity closed_at/outcome_reason consistent with closing event | 0 | PASS |
| lifecycle | StageHistory: valid transitions, starts at Qualification, times non-decreasing | 0 | PASS |
| duplicates | Dedupe recomputed == stored duplicate_of_contact_id / duplicate_of_lead_id | 0 | PASS |
| duplicates | No two master contacts share a normalised email | 0 | PASS |
| duplicates | Duplicate leads follow master rep | 0 | PASS |
| derived_values | Lead.status recomputed from source records | 0 | PASS |
| consent | Completed/open non-cancelled tasks had consent for their channel at due time | 0 | PASS |
| routing | Assigned rep is active | 0 | PASS |
| routing | Every lead has a rep, routed_at and a form_submit activity | 0 | PASS |
| leakage | Initial score uses only pre-conversion data (initial scored_at < opp.created_at) | 0 | PASS |
| leakage | No ground-truth/label columns in input tables | 0 | PASS |
| leakage | Ground truth lives in separate files | 0 | PASS |
| funnel | Funnel: master+duplicate leads == leads; scored == master leads | 0 | PASS |
| funnel | Funnel: opps from master + from duplicates == opportunities; open+won+lost == opportunities | 0 | PASS |
| funnel | Funnel: leads with status Converted == opportunities from master leads | 0 | PASS |
| funnel | Volumes match configuration | 0 | PASS |
