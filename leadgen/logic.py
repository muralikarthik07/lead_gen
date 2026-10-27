"""Shared business logic used by BOTH the generator and the validator (so rules are defined once)."""
from collections import defaultdict
from datetime import timedelta
from .util import parse, fmt


def normalize_email(e):
    local, _, dom = e.strip().lower().partition("@")
    return f"{local.split('+')[0]}@{dom}"


def dedupe_contacts(rows):
    """rows: dicts with contact_id,email,created_at. Returns {duplicate_id: master_id}; master = earliest record."""
    dup, masters = {}, {}
    for r in sorted(rows, key=lambda r: (r["created_at"], r["contact_id"])):
        k = normalize_email(r["email"])
        if k in masters:
            dup[r["contact_id"]] = masters[k]
        else:
            masters[k] = r["contact_id"]
    return dup


def dedupe_leads(rows, contact_dup, window_days):
    """Lead is a duplicate of the latest master lead with the same (master contact, product) within window_days."""
    last, dup = {}, {}
    for r in sorted(rows, key=lambda r: (r["created_at"], r["lead_id"])):
        key = (contact_dup.get(r["contact_id"], r["contact_id"]), r["product_interest"])
        m = last.get(key)
        if m is not None and parse(r["created_at"]) - parse(m["created_at"]) <= timedelta(days=window_days):
            dup[r["lead_id"]] = m["lead_id"]
        else:
            last[key] = r
    return dup


class ConsentIndex:
    """Point-in-time consent lookup over the append-only Consent timeline (ISO strings compare chronologically)."""

    def __init__(self, rows):
        self._p = defaultdict(list)
        for r in rows:
            self._p[(r["contact_id"], r["channel"])].append(r)
        for v in self._p.values():
            v.sort(key=lambda x: x["effective_from"])

    def period_at(self, contact_id, channel, t):
        for r in self._p.get((contact_id, channel), ()):
            if r["effective_from"] <= t and (not r["effective_to"] or t < r["effective_to"]):
                return r
        return None

    def has_consent(self, contact_id, channel, t):
        r = self.period_at(contact_id, channel, t)
        return bool(r and r["status"] == "opt_in")

    def contactable_through(self, contact_id, t0, t1):
        """True if some channel stays opted-in for the whole interval [t0, t1]."""
        for ch in ("email", "phone"):
            r = self.period_at(contact_id, ch, t0)
            if r and r["status"] == "opt_in" and (not r["effective_to"] or r["effective_to"] > t1):
                return True
        return False

    def opted_out_everywhere(self, contact_id, t):
        return not any(self.has_consent(contact_id, ch, t) for ch in ("email", "phone"))


def derive_lead_status(is_dup, has_opp, opted_out_all, last_activity, as_of, stale_days, tier, has_completed_task, has_rep_touch):
    """Documented precedence: Duplicate > Converted > Disqualified > Stale > Qualified > Working > New."""
    if is_dup:
        return "Duplicate"
    if has_opp:
        return "Converted"
    if opted_out_all:
        return "Disqualified"
    if last_activity < fmt(parse(as_of) - timedelta(days=stale_days)):
        return "Stale"
    if tier in ("A", "B") and has_completed_task:
        return "Qualified"
    if has_completed_task or has_rep_touch:
        return "Working"
    return "New"
