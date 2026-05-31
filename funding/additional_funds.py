"""Part 2 — minimum lump sum and monthly increment when infeasible."""

from __future__ import annotations

from datetime import date
from typing import Callable

from feasibility.models import (
    Client,
    CreditorRules,
    LedgerEntry,
    Offer,
    default_first_payment_date,
    monthly_payment_dates,
)
from payments.balloon import build_balloon_payments
from payments.even import build_even_payments
from payments.staircase import build_staircase_payments
from result import AdditionalFunds, FundsOption, Result
from scheduling.schedule_builder import try_schedule
from utils.money import (
    lump_sum_guardrail_max,
    monthly_increment_guardrail_max,
    offer_total_cents,
    program_fee_cents,
)


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


def _extend_cadence(
    creditor_dates: list[date],
    first_pay_date: date,
    horizon: date,
) -> list[date]:
    """Include fee-only cadence dates after the last creditor payment."""
    all_dates = _all_cadence_dates_within_horizon(first_pay_date, horizon)
    if not all_dates:
        return creditor_dates
    last_creditor = creditor_dates[-1]
    extra = [d for d in all_dates if d > last_creditor]
    return creditor_dates + extra


def _is_feasible_only(client: Client, offer: Offer, rules: CreditorRules) -> bool:
    o_total = offer_total_cents(offer)
    p_fee = program_fee_cents(offer, rules)
    horizon = client.last_draft_date
    first_pay_date = offer.first_payment_date or default_first_payment_date(client)
    max_k = min(rules.max_payments, rules.max_terms)
    cadence_dates = _cadence_dates_for_horizon(first_pay_date, horizon, max_k)

    if not cadence_dates:
        return False

    if rules.even_pays:
        builders: list[tuple[Callable[..., list[int] | None], range]] = [
            (build_even_payments, range(1, len(cadence_dates) + 1)),
        ]
    elif rules.is_ballooning_allowed:
        builders = [(build_balloon_payments, range(len(cadence_dates), 0, -1))]
    else:
        builders = [(build_staircase_payments, range(1, len(cadence_dates) + 1))]

    for build_fn, k_range in builders:
        for k in k_range:
            dates_k = cadence_dates[:k] if not rules.is_ballooning_allowed else cadence_dates[-k:]
            pays = build_fn(k, o_total, rules)
            if pays is None:
                continue
            full_dates = _extend_cadence(dates_k, first_pay_date, horizon)
            creditor_full = pays + [0] * (len(full_dates) - k)
            if try_schedule(client, p_fee, full_dates, creditor_full, rules, horizon):
                return True
            if rules.is_ballooning_allowed:
                break
    return False


def _evaluate_with_extra(
    client: Client,
    offer: Offer,
    rules: CreditorRules,
    lump: int = 0,
    lump_date: date | None = None,
    monthly_add: int = 0,
) -> bool:
    new_ledger: list[LedgerEntry] = []
    for entry in client.ledger:
        if monthly_add > 0 and entry.type == "credit" and entry.date > client.as_of_date:
            new_ledger.append(
                LedgerEntry(
                    date=entry.date,
                    amount_cents=entry.amount_cents + monthly_add,
                    type="credit",
                )
            )
        else:
            new_ledger.append(entry)

    extra_balance = 0
    if lump > 0 and lump_date is not None:
        if lump_date <= client.as_of_date:
            extra_balance = lump
        else:
            merged = False
            for i, entry in enumerate(new_ledger):
                if entry.date == lump_date and entry.type == "credit":
                    new_ledger[i] = LedgerEntry(
                        date=lump_date,
                        amount_cents=entry.amount_cents + lump,
                        type="credit",
                    )
                    merged = True
                    break
            if not merged:
                new_ledger.append(
                    LedgerEntry(date=lump_date, amount_cents=lump, type="credit")
                )

    aug_client = Client(
        draft_amount_cents=client.draft_amount_cents + monthly_add,
        draft_day=client.draft_day,
        first_draft_date=client.first_draft_date,
        last_draft_date=client.last_draft_date,
        as_of_date=client.as_of_date,
        current_balance_cents=client.current_balance_cents + extra_balance,
        ledger=new_ledger,
    )
    return _is_feasible_only(aug_client, offer, rules)


def _binary_search_min(predicate: Callable[[int], bool], lo: int, hi: int) -> int:
    if not predicate(hi):
        return hi + 1
    while lo < hi:
        mid = (lo + hi) // 2
        if predicate(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo


def _best_lump_date(client: Client, offer: Offer, rules: CreditorRules) -> date:
    """Pick the earliest date (most useful) on or before the horizon."""
    horizon = client.last_draft_date
    candidates = sorted(
        {client.as_of_date, client.first_draft_date}
        | {e.date for e in client.ledger if e.date <= horizon}
    )
    for d in candidates:
        if _evaluate_with_extra(client, offer, rules, lump=1, lump_date=d):
            return d
    return client.as_of_date


def infeasible_result(
    client: Client,
    offer: Offer,
    rules: CreditorRules,
) -> Result:
    """Compute minimum lump sum and monthly increment with guardrails."""
    o_total = offer_total_cents(offer)
    lump_date = _best_lump_date(client, offer, rules)

    lump_amount = _binary_search_min(
        lambda amount: _evaluate_with_extra(
            client, offer, rules, lump=amount, lump_date=lump_date
        ),
        lo=0,
        hi=10_000_000,
    )

    lump_max = lump_sum_guardrail_max(o_total)
    lump_ok = lump_amount <= lump_max
    lump_reason = (
        ""
        if lump_ok
        else f"Lump sum {lump_amount} exceeds 65% of offer total ({lump_max})"
    )

    future_drafts = [
        e for e in client.ledger if e.type == "credit" and e.date > client.as_of_date
    ]
    n_drafts = len(future_drafts)

    if n_drafts == 0:
        monthly_amount = 0
        monthly_ok = True
        monthly_reason = "No future drafts to increment"
    else:
        monthly_amount = _binary_search_min(
            lambda amount: _evaluate_with_extra(client, offer, rules, monthly_add=amount),
            lo=0,
            hi=10_000_000,
        )
        monthly_max = monthly_increment_guardrail_max(client.draft_amount_cents)
        monthly_ok = monthly_amount <= monthly_max
        monthly_reason = (
            ""
            if monthly_ok
            else (
                f"Monthly increment {monthly_amount} exceeds "
                f"max(10000, 40% of draft={monthly_max})"
            )
        )

    return Result(
        feasible=False,
        pay_shape_used=None,
        schedule=None,
        additional_funds=AdditionalFunds(
            lump_sum=FundsOption(
                amount_cents=lump_amount,
                within_guardrail=lump_ok,
                reason=lump_reason,
                date=lump_date,
            ),
            monthly_increment=FundsOption(
                amount_cents=monthly_amount,
                within_guardrail=monthly_ok,
                reason=monthly_reason,
                num_drafts=n_drafts,
            ),
        ),
    )
