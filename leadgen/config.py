from dataclasses import dataclass, asdict


@dataclass
class Config:
    seed: int = 20261022
    n_companies: int = 5000
    n_contacts: int = 10000
    n_leads: int = 20000
    n_opportunities: int = 3000
    as_of: str = "2026-10-22T00:00:00"          # dataset "today"
    lead_start: str = "2026-01-01T00:00:00"
    lead_end: str = "2026-08-31T23:59:59"
    holdout_cutoff: str = "2026-07-01T00:00:00"  # leads created >= this are the held-out test split
    score_window_days: int = 14                  # initial score = state of the lead 14 days after creation
    stale_days: int = 45
    dedupe_window_days: int = 90
    dup_contact_rate: float = 0.03
    free_email_rate: float = 0.10
    optout_email_rate: float = 0.07
    optout_phone_rate: float = 0.04
    blocker_rate: float = 0.22                   # hidden deal blockers not visible to the score
    # labelled edge cases (full-scale counts; scaled down proportionally)
    n_anom_optout_contacted: int = 80
    n_anom_post_conv_score: int = 60
    n_anom_outside_territory: int = 50
    n_anom_dup_opp: int = 40
    n_anom_stage_gap: int = 50

    def to_dict(self):
        return asdict(self)

    @classmethod
    def scaled(cls, scale=1.0, **overrides):
        """Same generator for starter and full datasets: only volumes change."""
        base = cls()
        c = cls(
            n_companies=max(20, round(base.n_companies * scale)),
            n_contacts=max(40, round(base.n_contacts * scale)),
            n_leads=max(80, round(base.n_leads * scale)),
            n_opportunities=max(10, round(base.n_opportunities * scale)),
        )
        for k in ("n_anom_optout_contacted", "n_anom_post_conv_score", "n_anom_outside_territory",
                  "n_anom_dup_opp", "n_anom_stage_gap"):
            setattr(c, k, max(2, round(getattr(base, k) * scale)))
        for k, v in overrides.items():
            setattr(c, k, v)
        return c
