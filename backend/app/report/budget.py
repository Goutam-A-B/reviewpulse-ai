"""Hard premium-call ceiling (PRD §6.5, EC-P5-04/11).

The counter is authoritative and increments BEFORE the call, so a request that
rate-limits or fails still counts against the budget (it consumed the slot). This
is what makes "one premium call per report" an enforced guarantee, not a hope.
"""
from __future__ import annotations


class PremiumCeilingReached(RuntimeError):
    pass


class PremiumBudget:
    def __init__(self, ceiling: int) -> None:
        self.ceiling = ceiling
        self.used = 0

    def can_spend(self) -> bool:
        return self.used < self.ceiling

    def spend(self) -> None:
        if not self.can_spend():
            raise PremiumCeilingReached(f"premium ceiling {self.ceiling} reached")
        self.used += 1
