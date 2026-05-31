"""Search for a feasible schedule that front-loads program fees."""

from __future__ import annotations

from datetime import date

from feasibility.models import Client, CreditorRules, Offer, default_first_payment_date, monthly_payment_dates
from payments.balloon import build_balloon_payments
from payments.even import build_even_payments
from payments.staircase import build_staircase_payments
from result import ScheduleRow
from scheduling.schedule_builder import fee_score, try_schedule
from utils.money import offer_total_cents, program_fee_cents


def _cadence_dates_for_horizon(
    first_pay_date: date,
    horizon: date,
    max_k: int,
) -> list[date]:
    dates = monthly_payment_dates(first_pay_date, max_k)
    return [d for d in dates if d <= horizon]


def _all_cadence_dates_within_horizon(first_pay_date: date, horizon: date) -> list[date]:
    dates: list[date] = []
    count = 1
    while True:
        batch = monthly_payment_dates(first_pay_date, count)
        d = batch[-1]
        if d > horizon:
            break
        dates.append(d)
        count += 1
    return dates


def find_feasible_schedule(
    client: Client,
    offer: Offer,
    rules: CreditorRules,
) -> tuple[list[ScheduleRow], str] | None:
    """Return the best feasible schedule and pay shape, or None."""
    o_total = offer_total_cents(offer)
    p_fee = program_fee_cents(offer, rules)
    horizon = client.last_draft_date
    first_pay_date = offer.first_payment_date or default_first_payment_date(client)
    max_k = min(rules.max_payments, rules.max_terms)

    cadence_dates = _cadence_dates_for_horizon(first_pay_date, horizon, max_k)

    if not cadence_dates:
        return None

    best_rows: list[ScheduleRow] | None = None
    best_score = float("inf")
    shape_used: str | None = None

    if rules.even_pays:
        shape = "even"
        build_fn = build_even_payments
        k_range = range(1, len(cadence_dates) + 1)
        pick_first = False
    elif rules.is_ballooning_allowed:
        shape = "balloon"
        build_fn = build_balloon_payments
        k_range = range(len(cadence_dates), 0, -1)
        pick_first = True
    else:
        shape = "staircase"
        build_fn = build_staircase_payments
        k_range = range(1, len(cadence_dates) + 1)
        pick_first = False


    for k in k_range:
        dates_k = cadence_dates[:k] if not rules.is_ballooning_allowed else cadence_dates[-k:]
        pays = build_fn(k, o_total, rules)
        
        if pays is None:
            continue

        all_dates = _all_cadence_dates_within_horizon(first_pay_date, horizon)
        last_creditor = dates_k[-1]
        extra_dates = [d for d in all_dates if d > last_creditor]
        full_dates = dates_k + extra_dates
        creditor_full = pays + [0] * len(extra_dates)

        rows = try_schedule(client, p_fee, full_dates, creditor_full, rules, horizon)
        if rows is None:
            continue

        if pick_first:
            return rows, shape

        score = fee_score(rows)
        if score < best_score:
            best_score = score
            best_rows = rows
            shape_used = shape

    if best_rows is None or shape_used is None:
        return None
    return best_rows, shape_used
