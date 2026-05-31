"""Staircase payment shape — non-decreasing steps with a segment cap."""

from __future__ import annotations

from feasibility.models import CreditorRules

from payments.floors import compute_floors


def _enforce_segments(
    pays: list[int],
    max_segments: int,
    floors: list[int],
) -> list[int] | None:
    """Ensure pays uses at most max_segments distinct values."""
    k = len(pays)
    if len(set(pays)) <= max_segments:
        if any(pays[i] < floors[i] for i in range(k)):
            return None
        return pays

    group_size = k // max_segments
    remainder = k % max_segments
    group_sizes = [group_size] * max_segments
    for i in range(remainder):
        group_sizes[max_segments - 1 - i] += 1

    group_floors: list[int] = []
    pos = 0
    for size in group_sizes:
        group_floors.append(max(floors[pos : pos + size]))
        pos += size

    for i in range(1, max_segments):
        if group_floors[i] < group_floors[i - 1]:
            group_floors[i] = group_floors[i - 1]

    early_total = sum(
        group_floors[i] * group_sizes[i] for i in range(max_segments - 1)
    )
    original_total = sum(pays)
    last_group_total = original_total - early_total
    if last_group_total < 0:
        return None

    last_size = group_sizes[-1]
    last_base, last_rem = divmod(last_group_total, last_size)

    new_pays: list[int] = []
    for gi in range(max_segments - 1):
        new_pays.extend([group_floors[gi]] * group_sizes[gi])
    for j in range(last_size):
        new_pays.append(last_base + (1 if j >= last_size - last_rem else 0))

    if sum(new_pays) != original_total:
        return None
    if any(new_pays[i] < floors[i] for i in range(k)):
        return None
    if any(new_pays[i] < new_pays[i - 1] for i in range(1, k)):
        return None

    return new_pays


def build_staircase_payments(k: int, offer_total: int, rules: CreditorRules) -> list[int] | None:
    """Start at floors, push excess onto later payments, cap distinct levels."""
    if k <= 0:
        return None

    floors = compute_floors(k, rules)
    min_sum = sum(floors)
    if min_sum > offer_total:
        return None

    pays = floors[:]
    excess = offer_total - min_sum
    pays[-1] += excess

    return _enforce_segments(pays, rules.max_segments, floors)
