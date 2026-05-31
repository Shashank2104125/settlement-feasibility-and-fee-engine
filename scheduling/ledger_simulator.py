"""Day-by-day SDA ledger simulation."""

from __future__ import annotations

from datetime import date

from feasibility.models import Client
from result import ScheduleRow


def simulate_ledger(
    client: Client,

    cadence_dates: list[date],
    creditor_pays: list[int],
    fee_alloc: list[int],
    bank_fee: int,
    horizon: date,
) -> list[ScheduleRow] | None:
    """Simulate the SDA chronologically; credits before debits each day."""
    k = len(cadence_dates)

    if len(creditor_pays) != k or len(fee_alloc) != k:
        return None

    future_entries: dict[date, tuple[int, int]] = {}
    for entry in client.ledger:
        if entry.date <= client.as_of_date:
            continue
        cr, db = future_entries.get(entry.date, (0, 0))
        if entry.type == "credit":
            cr += entry.amount_cents
        else:
            db += entry.amount_cents
        future_entries[entry.date] = (cr, db)

    new_debits: dict[date, tuple[int, int, int]] = {}
    for i, d in enumerate(cadence_dates):
        cp = creditor_pays[i]
        pf = fee_alloc[i]
        bf = bank_fee if cp > 0 else 0
        new_debits[d] = (cp, pf, bf)

    all_dates = sorted(set(future_entries) | set(new_debits))
    balance = client.current_balance_cents
    rows: list[ScheduleRow] = []
    cadence_index = {d: i for i, d in enumerate(cadence_dates)}

    for d in all_dates:
        if d > horizon:
            return None

        cr, db = future_entries.get(d, (0, 0))
        balance += cr
        balance -= db

        cp, pf, bf = new_debits.get(d, (0, 0, 0))
        balance -= cp + pf + bf

        if balance < 0:
            return None

        if d in cadence_index:
            rows.append(
                ScheduleRow(
                    date=d,
                    creditor_payment_cents=cp,
                    program_fee_cents=pf,
                    bank_fee_cents=bf,
                    balance_cents=balance,
                )
            )

    return rows
