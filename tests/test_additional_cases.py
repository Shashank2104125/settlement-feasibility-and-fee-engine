"""Expectations for additional cases beyond the four provided examples."""

from __future__ import annotations

from feasibility.engine import evaluate_offer
from feasibility.models import load_case, offer_total_cents


def _run(case: str):
    client, offer, rules = load_case(f"cases/{case}")
    return evaluate_offer(client, offer, rules)


def test_case5_token_pays():
    r = _run("case5_token_pays")
    assert r.feasible is True
    assert r.pay_shape_used == "staircase"
    payments = [
        row.creditor_payment_cents
        for row in r.schedule
        if row.creditor_payment_cents > 0
    ]
    assert sum(payments) == offer_total_cents(load_case("cases/case5_token_pays")[1])
    assert sum(1 for p in payments if p == 2500) <= 3


def test_case6_max_segments():
    r = _run("case6_max_segments")
    assert r.feasible is True
    assert r.pay_shape_used == "staircase"
    payments = [
        row.creditor_payment_cents
        for row in r.schedule
        if row.creditor_payment_cents > 0
    ]
    assert len(set(payments)) <= 2


def test_case7_guardrail_exceed():
    r = _run("case7_guardrail_exceed")
    assert r.feasible is False
    af = r.additional_funds
    assert af is not None
    assert af.lump_sum.within_guardrail is False
    assert af.monthly_increment.within_guardrail is False
    assert af.lump_sum.amount_cents > 0
    assert af.monthly_increment.amount_cents > 0
