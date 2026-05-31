"""Orchestration entry point for settlement feasibility evaluation."""

from __future__ import annotations

from feasibility.models import Client, CreditorRules, Offer
from feasibility.solver import find_feasible_schedule
from funding.additional_funds import infeasible_result
from result import AdditionalFunds, FundsOption, Result, ScheduleRow

# Re-export output types for backward compatibility with tests and run.py.
__all__ = [
    "AdditionalFunds",
    "FundsOption",
    "Result",
    "ScheduleRow",
    "evaluate_offer",
]


def evaluate_offer(client: Client, offer: Offer, rules: CreditorRules) -> Result:
    """Evaluate whether an offer is affordable and produce a schedule or minima."""
    found = find_feasible_schedule(client, offer, rules)
    if found is not None:
        rows, shape = found
        return Result(feasible=True, pay_shape_used=shape, schedule=rows)
    return infeasible_result(client, offer, rules)
