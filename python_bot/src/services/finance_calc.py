from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class FinanceEstimate:
    principal_rub: int
    current_rate: Optional[float]  # annual, 0..1
    term_months: Optional[int]
    savings_range_rub_per_year: Optional[Tuple[int, int]]  # (min, max)
    note: str


_PERCENT_RE = re.compile(r"(?P<p>\d{1,3}(?:[.,]\d{1,2})?)\s*%?")
_TERM_RE = re.compile(r"(?P<n>\d{1,3})\s*(?P<u>мес|месяц|месяцев|г|год|года|лет)", re.IGNORECASE)


def parse_percent(text: str) -> Optional[float]:
    if not text:
        return None
    m = _PERCENT_RE.search(text.strip().lower())
    if not m:
        return None
    raw = m.group("p").replace(",", ".")
    try:
        p = float(raw)
    except ValueError:
        return None
    if p <= 0 or p > 100:
        return None
    return p / 100.0


def parse_term_months(text: str) -> Optional[int]:
    if not text:
        return None
    m = _TERM_RE.search(text.strip().lower())
    if not m:
        # fallback: first integer is months
        nums = re.findall(r"\d{1,4}", text)
        if not nums:
            return None
        try:
            n = int(nums[0])
        except ValueError:
            return None
        # heuristic: 1..120 as months
        if 1 <= n <= 240:
            return n
        return None
    n = int(m.group("n"))
    u = (m.group("u") or "").lower()
    if "мес" in u or "меся" in u:
        return max(1, min(360, n))
    # years
    return max(1, min(360, n * 12))


def annuity_payment(principal_rub: int, annual_rate: float, term_months: int) -> int:
    """Monthly annuity payment, rounded to int rub."""
    if principal_rub <= 0 or term_months <= 0:
        return 0
    r = max(0.0, annual_rate) / 12.0
    if r == 0.0:
        return int(round(principal_rub / term_months))
    k = r * (1 + r) ** term_months / ((1 + r) ** term_months - 1)
    return int(round(principal_rub * k))


def estimate_refinance(
    *,
    principal_rub: int,
    current_rate: Optional[float],
    term_months: Optional[int],
    delta_points_min: float = 2.0,
    delta_points_max: float = 5.0,
) -> FinanceEstimate:
    """
    Conservative early-stage estimate:
    - savings/year ≈ principal * (delta_rate)
    We intentionally avoid promising a specific target rate.
    """
    if principal_rub <= 0:
        return FinanceEstimate(
            principal_rub=principal_rub,
            current_rate=current_rate,
            term_months=term_months,
            savings_range_rub_per_year=None,
            note="Не вижу сумму/остаток долга — без этого расчёт невозможен.",
        )

    if current_rate is None:
        return FinanceEstimate(
            principal_rub=principal_rub,
            current_rate=current_rate,
            term_months=term_months,
            savings_range_rub_per_year=None,
            note="Если пришлёте текущую ставку (%), посчитаю экономию точнее. Пока можно оценить на созвоне.",
        )

    # clamp deltas: can't reduce below zero, and delta can't exceed current_rate
    delta_min = min(current_rate, max(0.0, delta_points_min / 100.0))
    delta_max = min(current_rate, max(delta_min, delta_points_max / 100.0))
    savings_min = int(round(principal_rub * delta_min))
    savings_max = int(round(principal_rub * delta_max))

    note = (
        "Оценка экономии — ориентир. Итог зависит от программы/банка, финансового профиля и условий сделки."
    )

    # optional: add monthly payment reference if term provided
    if term_months and term_months > 0:
        p_now = annuity_payment(principal_rub, current_rate, term_months)
        p_better = annuity_payment(principal_rub, max(0.0, current_rate - delta_max), term_months)
        if p_now and p_better:
            note += f" По аннуитету платёж может снизиться примерно с ~{p_now:,} ₽ до ~{p_better:,} ₽/мес.".replace(",", " ")

    return FinanceEstimate(
        principal_rub=principal_rub,
        current_rate=current_rate,
        term_months=term_months,
        savings_range_rub_per_year=(min(savings_min, savings_max), max(savings_min, savings_max)),
        note=note,
    )


