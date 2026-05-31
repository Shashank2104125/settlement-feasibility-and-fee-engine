"""Even payment shape — all creditor payments as equal as possible."""

from __future__ import annotations

from feasibility.models import CreditorRules

from payments.floors import compute_floors


def build_even_payments(k: int, offer_total: int, rules: CreditorRules) -> list[int] | None:
    """Split offer_total across k equal-ish payments; remainder on the latest pays."""
    if k <= 0:
        return None

    floors = compute_floors(k, rules)
    base, rem = divmod(offer_total, k)
    pays = [base] * (k - rem) + [base + 1] * rem

    if sum(pays) != offer_total:
        return None
    if any(pay < floor for pay, floor in zip(pays, floors)):
        return None
    if any(pays[i] < pays[i - 1] for i in range(1, k)):
        return None

    return pays
