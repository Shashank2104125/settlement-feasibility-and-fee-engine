"""Front-loaded program fee allocation across cadence dates."""

from __future__ import annotations

from datetime import date

from feasibility.models import Client


def allocate_fees_greedily(
    client: Client,
    cadence_dates: list[date],
    creditor_pays: list[int],
    program_fee_total: int,
    bank_fee: int,
    horizon: date,
) -> list[int] | None:
    """Collect program fees as early as balance allows; fee-only dates incur no bank fee."""
    k = len(cadence_dates)
    if len(creditor_pays) != k:
        return None

    fee_alloc = [0] * k
    if program_fee_total == 0:
        return fee_alloc

    future_credits: dict[date, int] = {}
    future_debits: dict[date, int] = {}

    for entry in client.ledger:
        if entry.date <= client.as_of_date:
            continue
        if entry.type == "credit":
            future_credits[entry.date] = (
                future_credits.get(entry.date, 0) + entry.amount_cents
            )
        else:
            future_debits[entry.date] = (
                future_debits.get(entry.date, 0) + entry.amount_cents
            )

    cadence_set = set(cadence_dates)
    cadence_idx = {d: i for i, d in enumerate(cadence_dates)}
    all_dates = sorted(set(future_credits) | set(future_debits) | cadence_set)

    running = client.current_balance_cents
    fee_remaining = program_fee_total

    for d in all_dates:
        if d > horizon:
            return None

        running += future_credits.get(d, 0)
        running -= future_debits.get(d, 0)

        if d not in cadence_set:
            continue

        i = cadence_idx[d]
        cp = creditor_pays[i]
        bf = bank_fee if cp > 0 else 0
        running -= cp + bf

        if running < 0:
            return None

        if fee_remaining > 0:
            collectable = min(fee_remaining, running)
            fee_alloc[i] = collectable
            fee_remaining -= collectable
            running -= collectable

    if fee_remaining > 0:
        return None
    
    return fee_alloc
