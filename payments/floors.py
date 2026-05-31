"""Per-position minimum creditor payment floors."""

from __future__ import annotations

from feasibility.models import CreditorRules


def compute_floors(k: int, rules: CreditorRules) -> list[int]:
    """Return the floor (in cents) for each payment position 1..k."""
    floors: list[int] = []
    token_used = 0

    for pos in range(1, k + 1):
        floor = rules.min_payment_cents

        for tier_pos, tier_floor in rules.min_payment_tiers:
            if pos >= tier_pos:
                floor = max(floor, tier_floor)

        if token_used >= rules.max_token_pays and floor == rules.min_payment_cents:
            floor += 1

        if floor == rules.min_payment_cents:
            token_used += 1

        floors.append(floor)
    
    return floors
