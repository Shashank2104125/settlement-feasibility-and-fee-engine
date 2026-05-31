"""Money helpers — integer cents with explicit round-half-up."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from feasibility.models import CreditorRules, Offer


def round_half_up(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def creditor_balance_cents(offer: Offer) -> int:
    """Return the creditor balance field (supports both JSON field names)."""
    return getattr(offer, "creditor_balance_cents", offer.current_balance_cents)


def offer_total_cents(offer: Offer) -> int:
    return round_half_up(offer.settlement_pct * creditor_balance_cents(offer))


def program_fee_cents(offer: Offer, rules: CreditorRules) -> int:
    return round_half_up(rules.program_fee_pct * offer.original_balance_cents)


def lump_sum_guardrail_max(offer_total: int) -> int:
    return round_half_up(0.65 * offer_total)


def monthly_increment_guardrail_max(draft_amount_cents: int) -> int:
    return max(10_000, round_half_up(0.40 * draft_amount_cents))
