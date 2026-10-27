"""Reference vocabularies. All values are fictional / synthetic (no real people, firms or domains)."""

PRODUCTS = ["Platform", "Analytics", "Automation", "Security"]
PRODUCT_WEIGHT = {"Platform": .35, "Analytics": .25, "Automation": .22, "Security": .18}
PRODUCT_BASE_AMOUNT = {"Platform": 40000, "Analytics": 30000, "Automation": 25000, "Security": 35000}

SOURCES = ["paid_search", "organic_search", "webinar", "trade_show", "referral", "partner", "content_download"]
SOURCE_WEIGHT = [.22, .18, .12, .10, .08, .10, .20]
SOURCE_INTENT = {"referral": .80, "partner": .65, "trade_show": .55, "webinar": .55,
                 "paid_search": .45, "organic_search": .40, "content_download": .35}
SOURCE_LABEL = {"paid_search": "Paid Search", "organic_search": "Organic", "webinar": "Webinar",
                "trade_show": "Trade Show", "referral": "Referral Program", "partner": "Partner",
                "content_download": "Content Syndication"}
CONSENT_METHOD = {"trade_show": "event_badge_scan", "partner": "partner_transfer", "referral": "sales_call"}

TERRITORIES = ["NORAM", "LATAM", "EMEA-N", "EMEA-S", "APAC", "INDIA"]
REPS_PER_TERRITORY = {"NORAM": 10, "LATAM": 5, "EMEA-N": 8, "EMEA-S": 6, "APAC": 6, "INDIA": 6}
# country -> (territory, sampling weight, calling code)
COUNTRIES = {
    "US": ("NORAM", 30, 1), "CA": ("NORAM", 5, 1),
    "BR": ("LATAM", 5, 55), "MX": ("LATAM", 4, 52), "AR": ("LATAM", 1.5, 54), "CL": ("LATAM", 1.5, 56), "CO": ("LATAM", 1.5, 57),
    "GB": ("EMEA-N", 8, 44), "DE": ("EMEA-N", 7, 49), "NL": ("EMEA-N", 3, 31), "SE": ("EMEA-N", 2, 46),
    "IE": ("EMEA-N", 2, 353), "FR": ("EMEA-N", 5, 33),
    "ES": ("EMEA-S", 3, 34), "IT": ("EMEA-S", 3, 39), "AE": ("EMEA-S", 3, 971), "ZA": ("EMEA-S", 2, 27), "PT": ("EMEA-S", 1, 351),
    "AU": ("APAC", 4, 61), "SG": ("APAC", 3, 65), "JP": ("APAC", 3, 81),
    "IN": ("INDIA", 8, 91),
}

# industry -> (weight, is_target_industry)
INDUSTRIES = {"Software": (.16, 1), "Financial Services": (.12, 1), "Healthcare": (.11, 1), "Manufacturing": (.12, 0),
              "Retail": (.10, 0), "Education": (.08, 0), "Logistics": (.08, 0), "Energy": (.07, 0),
              "Media": (.08, 0), "Public Sector": (.08, 0)}
TARGET_INDUSTRIES = {k for k, v in INDUSTRIES.items() if v[1]}

BANDS = [("1-10", 1, 10, .25), ("11-50", 11, 50, .28), ("51-200", 51, 200, .24),
         ("201-1000", 201, 1000, .15), ("1000+", 1001, 50000, .08)]
BAND_LABELS = [b[0] for b in BANDS]
BAND_AMOUNT_MULT = {"1-10": .4, "11-50": .7, "51-200": 1.0, "201-1000": 1.8, "1000+": 3.5}


def band_of(n):
    for label, lo, hi, _ in BANDS:
        if n <= hi:
            return label
    return BANDS[-1][0]


SENIORITY = {  # level -> (titles, weight, rank used by hidden fit index)
    "c_level": (["Chief Executive Officer", "Chief Technology Officer", "Chief Information Officer", "Chief Operating Officer"], .06, 1.0),
    "vp": (["VP of Engineering", "VP of Operations", "VP of Sales", "VP of IT"], .10, .85),
    "director": (["Director of IT", "Director of Operations", "Director of Analytics", "Director of Security"], .20, .65),
    "manager": (["IT Manager", "Operations Manager", "Product Manager", "Marketing Manager"], .30, .40),
    "individual": (["Analyst", "Software Engineer", "Specialist", "Coordinator"], .34, .10),
}

FREE_EMAIL_DOMAIN = "mailbox.example"

FIRST = ("Aarav Aiko Alejandro Amara Ananya Andrei Beatriz Carlos Chen Chloe Daniel Diego Elena Emma Fatima Felix Gabriel Hana "
         "Hiroshi Isabella Ivan Jamal Jin Kavya Kenji Klaus Laura Liam Lucas Mai Marco Maria Mateo Mei Mohammed Nadia Nikhil "
         "Noah Olivia Omar Priya Rahul Rosa Ryo Sara Sofia Stefan Thomas Tara Uma Victor Wei Xavier Yara Yuki Zainab Zoe "
         "Anders Ingrid Thabo").split()
LAST = ("Adeyemi Almeida Andersson Bhatt Brown Chatterjee Chen Costa Das Dubois Fernandez Fischer Garcia Gupta Hansen Hughes "
        "Ito Iyer Jensen Joshi Kapoor Khan Kim Kowalski Kumar Larsen Lee Li Lopez Martin Mehta Moreau Murphy Nair Nakamura "
        "Nguyen Novak Okafor Patel Perez Petrov Reddy Rossi Santos Sato Schmidt Sharma Silva Singh Suzuki Tan Tanaka Taylor "
        "Verma Wang Weber Wilson Wong Yamamoto Zhang").split()
CO_PREFIX = ("Northwind Bluepeak Ironbridge Silverline Redwood Cobalt Evergreen Falcon Granite Harbor Indigo Juniper Keystone "
             "Lumen Meridian Nimbus Orchid Pinnacle Quartz Riverstone Summit Tidewater Union Vertex Willow Zenith Alpine "
             "Beacon Crescent Dynamo Ember Frontier Glacier Horizon Ivory Jade Kestrel Lagoon Mosaic Nova").split()
CO_NOUN = ("Data Cloud Logic Works Dynamics Networks Robotics Analytics Finance Health Energy Logistics Media Retail Learning "
           "Materials Software Digital Capital Care Power Freight Pharma Foods Motors Textiles Security Mobility Insight Cyber").split()
CO_SUFFIX = ["Systems", "Labs", "Group", "Technologies", "Partners", "Solutions", "Holdings", "Industries"]

# activity_type -> (direction, channel, consent channel required to perform it, or None)
ACTIVITY_TYPES = {
    "form_submit": ("inbound", "web", None),
    "web_visit": ("inbound", "web", None),
    "pricing_page_visit": ("inbound", "web", None),
    "content_download": ("inbound", "web", None),
    "demo_request": ("inbound", "web", None),
    "email_open": ("inbound", "email", None),
    "email_click": ("inbound", "email", None),
    "email_outbound": ("outbound", "email", "email"),
    "call_outbound": ("outbound", "phone", "phone"),
    "demo_delivered": ("outbound", "video", "email"),
    "proposal_sent": ("outbound", "email", "email"),
    "meeting": ("outbound", "video", "email"),
}
REP_TOUCH_TYPES = {"call_outbound", "demo_delivered", "proposal_sent", "meeting"}

STAGES = ["Qualification", "Discovery", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]
OPEN_STAGES = STAGES[:4]
STAGE_EDGES = {None: {"Qualification"},
               "Qualification": {"Discovery", "Closed Lost"}, "Discovery": {"Proposal", "Closed Lost"},
               "Proposal": {"Negotiation", "Closed Lost"}, "Negotiation": {"Closed Won", "Closed Lost"}}
STAGE_DAYS = {0: (2, 9), 1: (4, 14), 2: (5, 18), 3: (4, 20)}
WIN_REASONS = ["product_fit", "price", "relationship", "features"]
LOSS_REASONS = ["budget", "competitor", "no_decision", "price", "timing", "not_a_fit", "features"]
BLOCKERS = {"no_budget": -1.8, "competitor_incumbent": -1.6, "no_response": -2.2}
