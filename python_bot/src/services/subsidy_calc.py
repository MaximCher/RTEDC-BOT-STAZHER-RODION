from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class SubsidyEstimate:
    percent: Optional[float]  # 0..1
    cap_rub: Optional[int]
    spend_rub: int
    estimated_rub: int
    evidence: str


_MONEY_RE = re.compile(
    r"(?P<num>\d[\d\s.,]*)\s*(?P<unit>млрд|миллиард|млн|миллион|тыс|тысяч|kk|кк|k|к)?",
    re.IGNORECASE,
)

_PERCENT_RE = re.compile(r"(?P<p>\d{1,3})\s*%", re.IGNORECASE)


def parse_money_rub(text: str) -> List[int]:
    values: List[int] = []
    for m in _MONEY_RE.finditer(text or ""):
        raw_num = (m.group("num") or "").strip()
        if not raw_num:
            continue
        normalized = raw_num.replace(" ", "").replace(",", ".")
        try:
            base = float(normalized)
        except ValueError:
            continue
        unit = (m.group("unit") or "").lower()
        mult = 1
        if "млрд" in unit or "миллиард" in unit or unit == "b":
            mult = 1_000_000_000
        elif "млн" in unit or "миллион" in unit or unit in {"m", "kk", "кк"}:
            mult = 1_000_000
        elif "тыс" in unit or "тысяч" in unit or unit in {"k", "к"}:
            mult = 1_000
        else:
            # heuristic: ignore too small numbers without unit (likely not budget)
            if base < 100_000:
                continue
        value = int(round(base * mult))
        if value > 0:
            values.append(value)
    return values


def parse_spend_from_question(text: str) -> Optional[int]:
    """Try to extract spend/budget from user question."""
    values = parse_money_rub(text)
    if not values:
        return None
    # take max mentioned amount as spend proxy
    return max(values)


def _extract_percents(context: str) -> List[float]:
    percents: List[float] = []
    for m in _PERCENT_RE.finditer(context or ""):
        p = int(m.group("p"))
        if 0 < p <= 100:
            percents.append(p / 100.0)
    # keep unique, prefer larger
    return sorted(list(set(percents)), reverse=True)


def _extract_caps(context: str) -> List[int]:
    caps: List[int] = []
    values = parse_money_rub(context)
    # heuristic: treat big numbers as caps
    for v in values:
        if v >= 200_000:  # 200k+ looks like money cap/limit
            caps.append(v)
    return sorted(list(set(caps)), reverse=True)


def estimate_from_context(
    context: str, spend_rub: int, top_k: int = 3
) -> List[SubsidyEstimate]:
    if not context or spend_rub <= 0:
        return []

    percents = _extract_percents(context)
    caps = _extract_caps(context)

    # If no explicit percent, we can't compute reliably
    if not percents:
        return []

    # build candidates from best percents and caps
    candidates: List[SubsidyEstimate] = []
    for p in percents[:5]:
        if caps:
            for cap in caps[:5]:
                est = min(int(round(spend_rub * p)), cap)
                candidates.append(
                    SubsidyEstimate(
                        percent=p,
                        cap_rub=cap,
                        spend_rub=spend_rub,
                        estimated_rub=est,
                        evidence=_build_evidence(p, cap),
                    )
                )
        else:
            est = int(round(spend_rub * p))
            candidates.append(
                SubsidyEstimate(
                    percent=p,
                    cap_rub=None,
                    spend_rub=spend_rub,
                    estimated_rub=est,
                    evidence=_build_evidence(p, None),
                )
            )

    # dedupe by estimated amount (keep top)
    candidates.sort(key=lambda c: c.estimated_rub, reverse=True)
    dedup: List[SubsidyEstimate] = []
    seen = set()
    for c in candidates:
        key = (c.percent, c.cap_rub)
        if key in seen:
            continue
        seen.add(key)
        dedup.append(c)
        if len(dedup) >= top_k:
            break
    return dedup


def _format_rub(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _build_evidence(p: float, cap: Optional[int]) -> str:
    percent = f"до {int(round(p * 100))}%"
    if cap:
        return f"{percent}, лимит до {_format_rub(cap)} ₽"
    return percent


def format_estimates(estimates: List[SubsidyEstimate]) -> str:
    if not estimates:
        return ""
    lines = ["📌 Предварительный расчёт по найденным условиям:"]
    for i, e in enumerate(estimates, start=1):
        lines.append(f"{i}) {e.evidence} → ~{_format_rub(e.estimated_rub)} ₽")
    lines.append("⚠️ Это ориентир. Итог зависит от отбора и пакета документов.")
    return "\n".join(lines)


