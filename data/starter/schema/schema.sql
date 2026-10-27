CREATE TABLE Company (
  company_id TEXT NOT NULL,
  company_name TEXT NOT NULL UNIQUE,
  domain TEXT NOT NULL UNIQUE,
  industry TEXT NOT NULL CHECK (industry IN ('Software', 'Financial Services', 'Healthcare', 'Manufacturing', 'Retail', 'Education', 'Logistics', 'Energy', 'Media', 'Public Sector')),
  employee_count INTEGER NOT NULL,
  employee_band TEXT NOT NULL CHECK (employee_band IN ('1-10', '11-50', '51-200', '201-1000', '1000+')),
  annual_revenue_usd REAL NOT NULL,
  country TEXT NOT NULL CHECK (country IN ('US', 'CA', 'BR', 'MX', 'AR', 'CL', 'CO', 'GB', 'DE', 'NL', 'SE', 'IE', 'FR', 'ES', 'IT', 'AE', 'ZA', 'PT', 'AU', 'SG', 'JP', 'IN')),
  territory TEXT NOT NULL CHECK (territory IN ('NORAM', 'LATAM', 'EMEA-N', 'EMEA-S', 'APAC', 'INDIA')),
  created_at TEXT NOT NULL,
  PRIMARY KEY (company_id)
);

CREATE TABLE Contact (
  contact_id TEXT NOT NULL,
  company_id TEXT NOT NULL,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  email TEXT NOT NULL,
  email_type TEXT NOT NULL CHECK (email_type IN ('corporate', 'free')),
  phone TEXT,
  job_title TEXT NOT NULL,
  seniority TEXT NOT NULL CHECK (seniority IN ('c_level', 'vp', 'director', 'manager', 'individual')),
  created_at TEXT NOT NULL,
  duplicate_of_contact_id TEXT,
  PRIMARY KEY (contact_id),
  FOREIGN KEY (company_id) REFERENCES Company(company_id),
  FOREIGN KEY (duplicate_of_contact_id) REFERENCES Contact(contact_id)
);

CREATE TABLE Campaign (
  campaign_id TEXT NOT NULL,
  campaign_name TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('paid_search', 'webinar', 'trade_show', 'referral', 'partner', 'content_download')),
  product_focus TEXT CHECK (product_focus IN ('Platform', 'Analytics', 'Automation', 'Security')),
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  budget_usd REAL NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('planned', 'active', 'completed')),
  PRIMARY KEY (campaign_id)
);

CREATE TABLE SalesRep (
  rep_id TEXT NOT NULL,
  rep_name TEXT NOT NULL,
  territory TEXT NOT NULL CHECK (territory IN ('NORAM', 'LATAM', 'EMEA-N', 'EMEA-S', 'APAC', 'INDIA')),
  hire_date TEXT NOT NULL,
  is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
  PRIMARY KEY (rep_id)
);

CREATE TABLE RepCoverage (
  rep_id TEXT NOT NULL,
  territory TEXT NOT NULL CHECK (territory IN ('NORAM', 'LATAM', 'EMEA-N', 'EMEA-S', 'APAC', 'INDIA')),
  product TEXT NOT NULL CHECK (product IN ('Platform', 'Analytics', 'Automation', 'Security')),
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  PRIMARY KEY (rep_id, territory, product),
  FOREIGN KEY (rep_id) REFERENCES SalesRep(rep_id)
);

CREATE TABLE Consent (
  consent_id TEXT NOT NULL,
  contact_id TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('email', 'phone')),
  status TEXT NOT NULL CHECK (status IN ('opt_in', 'opt_out')),
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  capture_method TEXT NOT NULL CHECK (capture_method IN ('web_form', 'event_badge_scan', 'partner_transfer', 'sales_call', 'user_request')),
  PRIMARY KEY (consent_id),
  FOREIGN KEY (contact_id) REFERENCES Contact(contact_id)
);

CREATE TABLE Lead (
  lead_id TEXT NOT NULL,
  contact_id TEXT NOT NULL,
  company_id TEXT NOT NULL,
  campaign_id TEXT,
  consent_id TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('paid_search', 'organic_search', 'webinar', 'trade_show', 'referral', 'partner', 'content_download')),
  product_interest TEXT NOT NULL CHECK (product_interest IN ('Platform', 'Analytics', 'Automation', 'Security')),
  territory TEXT NOT NULL CHECK (territory IN ('NORAM', 'LATAM', 'EMEA-N', 'EMEA-S', 'APAC', 'INDIA')),
  created_at TEXT NOT NULL,
  assigned_rep_id TEXT,
  routed_at TEXT,
  routing_rule TEXT CHECK (routing_rule IN ('territory_product_least_loaded', 'duplicate_follows_master')),
  status TEXT NOT NULL CHECK (status IN ('New', 'Working', 'Qualified', 'Converted', 'Disqualified', 'Duplicate', 'Stale')),
  duplicate_of_lead_id TEXT,
  PRIMARY KEY (lead_id),
  FOREIGN KEY (contact_id) REFERENCES Contact(contact_id),
  FOREIGN KEY (company_id) REFERENCES Company(company_id),
  FOREIGN KEY (campaign_id) REFERENCES Campaign(campaign_id),
  FOREIGN KEY (consent_id) REFERENCES Consent(consent_id),
  FOREIGN KEY (assigned_rep_id) REFERENCES SalesRep(rep_id),
  FOREIGN KEY (duplicate_of_lead_id) REFERENCES Lead(lead_id)
);

CREATE TABLE Task (
  task_id TEXT NOT NULL,
  lead_id TEXT NOT NULL,
  rep_id TEXT NOT NULL,
  task_type TEXT NOT NULL CHECK (task_type IN ('call', 'email', 'demo')),
  priority TEXT NOT NULL CHECK (priority IN ('high', 'medium', 'low')),
  created_at TEXT NOT NULL,
  due_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL CHECK (status IN ('open', 'completed', 'overdue', 'cancelled')),
  cancel_reason TEXT CHECK (cancel_reason IN ('no_consent', 'opted_out')),
  PRIMARY KEY (task_id),
  FOREIGN KEY (lead_id) REFERENCES Lead(lead_id),
  FOREIGN KEY (rep_id) REFERENCES SalesRep(rep_id)
);

CREATE TABLE Activity (
  activity_id TEXT NOT NULL,
  lead_id TEXT NOT NULL,
  activity_type TEXT NOT NULL CHECK (activity_type IN ('form_submit', 'web_visit', 'pricing_page_visit', 'content_download', 'demo_request', 'email_open', 'email_click', 'email_outbound', 'call_outbound', 'demo_delivered', 'proposal_sent', 'meeting')),
  direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  channel TEXT NOT NULL CHECK (channel IN ('web', 'email', 'phone', 'video')),
  occurred_at TEXT NOT NULL,
  rep_id TEXT,
  task_id TEXT,
  PRIMARY KEY (activity_id),
  FOREIGN KEY (lead_id) REFERENCES Lead(lead_id),
  FOREIGN KEY (rep_id) REFERENCES SalesRep(rep_id),
  FOREIGN KEY (task_id) REFERENCES Task(task_id)
);

CREATE TABLE ScoreRule (
  rule_id TEXT NOT NULL,
  rule_version INTEGER NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('fit', 'intent', 'engagement')),
  feature TEXT NOT NULL,
  operator TEXT NOT NULL CHECK (operator IN ('eq', 'gte', 'per_unit')),
  value TEXT NOT NULL,
  points INTEGER NOT NULL,
  cap_units INTEGER,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  description TEXT NOT NULL,
  PRIMARY KEY (rule_id)
);

CREATE TABLE LeadScore (
  score_id TEXT NOT NULL,
  lead_id TEXT NOT NULL,
  scored_at TEXT NOT NULL,
  rule_version INTEGER NOT NULL,
  raw_score INTEGER NOT NULL,
  total_score INTEGER NOT NULL,
  tier TEXT NOT NULL CHECK (tier IN ('A', 'B', 'C', 'D')),
  trigger TEXT NOT NULL CHECK (trigger IN ('initial', 'rescore')),
  PRIMARY KEY (score_id),
  FOREIGN KEY (lead_id) REFERENCES Lead(lead_id)
);

CREATE TABLE LeadScoreComponent (
  score_id TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  units INTEGER NOT NULL,
  points INTEGER NOT NULL,
  PRIMARY KEY (score_id, rule_id),
  FOREIGN KEY (score_id) REFERENCES LeadScore(score_id),
  FOREIGN KEY (rule_id) REFERENCES ScoreRule(rule_id)
);

CREATE TABLE Opportunity (
  opportunity_id TEXT NOT NULL,
  lead_id TEXT NOT NULL UNIQUE,
  company_id TEXT NOT NULL,
  contact_id TEXT NOT NULL,
  rep_id TEXT NOT NULL,
  product TEXT NOT NULL CHECK (product IN ('Platform', 'Analytics', 'Automation', 'Security')),
  amount_usd REAL NOT NULL,
  created_at TEXT NOT NULL,
  current_stage TEXT NOT NULL CHECK (current_stage IN ('Qualification', 'Discovery', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost')),
  status TEXT NOT NULL CHECK (status IN ('open', 'won', 'lost')),
  closed_at TEXT,
  outcome_reason TEXT CHECK (outcome_reason IN ('product_fit', 'price', 'relationship', 'features', 'budget', 'competitor', 'no_decision', 'timing', 'not_a_fit')),
  PRIMARY KEY (opportunity_id),
  FOREIGN KEY (lead_id) REFERENCES Lead(lead_id),
  FOREIGN KEY (company_id) REFERENCES Company(company_id),
  FOREIGN KEY (contact_id) REFERENCES Contact(contact_id),
  FOREIGN KEY (rep_id) REFERENCES SalesRep(rep_id)
);

CREATE TABLE StageHistory (
  stage_history_id TEXT NOT NULL,
  opportunity_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  from_stage TEXT CHECK (from_stage IN ('Qualification', 'Discovery', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost')),
  to_stage TEXT NOT NULL CHECK (to_stage IN ('Qualification', 'Discovery', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost')),
  changed_at TEXT NOT NULL,
  transition_reason TEXT NOT NULL,
  PRIMARY KEY (stage_history_id),
  FOREIGN KEY (opportunity_id) REFERENCES Opportunity(opportunity_id)
);
