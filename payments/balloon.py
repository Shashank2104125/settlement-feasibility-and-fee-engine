"""Balloon payment shape — minimum early pays, final absorbs remainder."""

from __future__ import annotations

from feasibility.models import CreditorRules

from payments.floors import compute_floors


def build_balloon_payments(k: int, offer_total: int, rules: CreditorRules) -> list[int] | None:
    """Payments 1..k-1 at floor; final payment absorbs the remainder."""
    if k <= 0:
        return None

    floors = compute_floors(k, rules)

    if k == 1:
        if offer_total < floors[0]:
            return None
        return [offer_total]

    early = floors[:-1]
    balloon = offer_total - sum(early)

    if balloon < floors[-1]:
        return None
    if balloon < early[-1]:
        return None

    return early + [balloon]
