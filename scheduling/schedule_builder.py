"""Schedule assembly: fee allocation + ledger simulation."""

from __future__ import annotations

from datetime import date

from feasibility.models import Client, CreditorRules
from result import ScheduleRow
from scheduling.fee_allocator import allocate_fees_greedily
from scheduling.ledger_simulator import simulate_ledger


def try_schedule(
    client: Client,
    prog_fee: int,
    cadence_dates: list[date],
    creditor_pays: list[int],
    rules: CreditorRules,
    horizon: date,
) -> list[ScheduleRow] | None:
    """Allocate fees front-loaded and simulate; return schedule rows or None."""
    fee_alloc = allocate_fees_greedily(
        client,
        cadence_dates,
        creditor_pays,
        prog_fee,
        rules.bank_fee_cents,
        horizon,
    )

    if fee_alloc is None:
        return None

    return simulate_ledger(
        client,
        cadence_dates,
        creditor_pays,
        fee_alloc,
        rules.bank_fee_cents,
        horizon,
    )


def fee_score(rows: list[ScheduleRow]) -> float:
    """Lower score means program fees collected earlier."""
    return sum(i * r.program_fee_cents for i, r in enumerate(rows))
