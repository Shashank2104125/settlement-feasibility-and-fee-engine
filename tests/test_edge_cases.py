"""Edge-case tests beyond the four provided cases."""

from __future__ import annotations

from datetime import date

import pytest

from feasibility.engine import evaluate_offer
from feasibility.models import (
    Client,
    CreditorRules,
    LedgerEntry,
    Offer,
    monthly_payment_dates,
    offer_total_cents,
    program_fee_cents,
)
from payments.even import build_even_payments
from payments.floors import compute_floors
from scheduling.fee_allocator import allocate_fees_greedily
from scheduling.ledger_simulator import simulate_ledger
from utils.money import round_half_up


def _client(
    *,
    balance: int = 0,
    draft: int = 10_000,
    first_draft: date = date(2026, 1, 1),
    last_draft: date = date(2026, 6, 1),
    as_of: date = date(2025, 12, 31),
    ledger: list[LedgerEntry] | None = None,
) -> Client:
    if ledger is None:
        ledger = []
        d = first_draft
        while d <= last_draft:
            ledger.append(LedgerEntry(d, draft, "credit"))
            if d.month == 12:
                d = date(d.year + 1, 1, 1)
            else:
                d = date(d.year, d.month + 1, 1)
    return Client(
        draft_amount_cents=draft,
        draft_day=1,
        first_draft_date=first_draft,
        last_draft_date=last_draft,
        as_of_date=as_of,
        current_balance_cents=balance,
        ledger=ledger,
    )


def _offer(**kwargs) -> Offer:
    defaults = dict(
        creditor="TestCo",
        current_balance_cents=50_000,
        original_balance_cents=50_000,
        settlement_pct=0.5,
        first_payment_date=date(2026, 1, 31),
    )
    defaults.update(kwargs)
    return Offer(**defaults)


def _rules(**kwargs) -> CreditorRules:
    defaults = dict(
        max_terms=6,
        max_payments=6,
        min_payment_cents=2500,
        max_token_pays=6,
        min_payment_tiers=[],
        even_pays=True,
        is_ballooning_allowed=False,
        max_segments=2,
        bank_fee_cents=500,
        program_fee_pct=0.2,
    )
    defaults.update(kwargs)
    return CreditorRules(**defaults)


def test_round_half_up_away_from_zero():
    assert round_half_up(2.5) == 3
    assert round_half_up(3.5) == 4
    assert round_half_up(-2.5) == -3


def test_creditor_payments_sum_to_offer_total():
    client, offer, _rules = _load_case_tuple("case1_feasible_even")
    r = evaluate_offer(client, offer, _rules)
    assert r.feasible
    total = sum(row.creditor_payment_cents for row in r.schedule)
    assert total == offer_total_cents(offer)


def test_program_fee_fully_collected():
    r = evaluate_offer(*_load_case_tuple("case1_feasible_even"))
    _, offer, rules = _load_case_tuple("case1_feasible_even")
    fee_total = sum(row.program_fee_cents for row in r.schedule)
    assert fee_total == program_fee_cents(offer, rules)


def test_no_program_fee_before_first_creditor_payment():
    r = evaluate_offer(*_load_case_tuple("case1_feasible_even"))
    first_creditor_idx = next(
        i for i, row in enumerate(r.schedule) if row.creditor_payment_cents > 0
    )
    for row in r.schedule[:first_creditor_idx]:
        assert row.program_fee_cents == 0


def test_bank_fee_only_on_creditor_payment_dates():
    r = evaluate_offer(*_load_case_tuple("case1_feasible_even"))
    for row in r.schedule:
        if row.creditor_payment_cents == 0:
            assert row.bank_fee_cents == 0
        else:
            assert row.bank_fee_cents == 1000


def test_final_balance_non_negative():
    r = evaluate_offer(*_load_case_tuple("case1_feasible_even"))
    assert r.schedule[-1].balance_cents >= 0


def test_horizon_excludes_dates_after_last_draft():
    client, offer, rules = _load_case_tuple("case1_feasible_even")
    r = evaluate_offer(client, offer, rules)
    horizon = client.last_draft_date
    assert all(row.date <= horizon for row in r.schedule)


def test_token_pay_floor_enforced():
    floors = compute_floors(8, _rules(max_token_pays=3, even_pays=False))
    assert floors[:3] == [2500, 2500, 2500]
    assert all(f >= 2501 for f in floors[3:])


def test_tier_floor_enforced():
    floors = compute_floors(10, _rules(min_payment_tiers=[(7, 5000)], even_pays=False))
    assert all(f == 2500 for f in floors[:6])
    assert all(f == 5000 for f in floors[6:])


def test_even_remainder_on_latest_payments():
    pays = build_even_payments(6, 50_000, _rules())
    assert pays == [8333, 8333, 8333, 8333, 8334, 8334]


def test_infeasible_guardrails():
    r = evaluate_offer(*_load_case_tuple("case2_infeasible_minima"))
    assert r.additional_funds.lump_sum.within_guardrail
    assert r.additional_funds.monthly_increment.within_guardrail


def test_default_first_payment_date_when_omitted():
    client = _client(draft = 25_000)
    offer = _offer(first_payment_date=None)
    rules = _rules(program_fee_pct=0.0, bank_fee_cents=0, max_terms=1, max_payments=1, min_payment_cents=25000)
    r = evaluate_offer(client, offer, rules)
    assert r.feasible
    assert r.schedule[0].date == date(2026, 1, 31)


def _load_case_tuple(case: str):
    from feasibility.models import load_case

    return load_case(f"cases/{case}")
