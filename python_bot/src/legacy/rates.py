from __future__ import annotations

from src.legacy.currency_parser import (
    get_cbr_rates,
    get_investing_rates,
    get_profinance_usd_last_selenium,
    get_rapira_usdt_title,
)


def get_all_rates_table() -> list[list[str]]:
    cbr = get_cbr_rates()
    investing = get_investing_rates()
    profinance_usd = get_profinance_usd_last_selenium()
    usdt = get_rapira_usdt_title()
    table = [
        ["Источник", "USD", "EUR", "CNY", "USDT"],
        [
            "ЦБ РФ",
            str(cbr.get("USD", "-")),
            str(cbr.get("EUR", "-")),
            str(cbr.get("CNY", "-")),
            "-",
        ],
        [
            "Investing.com",
            str(profinance_usd),
            str(investing.get("EUR", "-")),
            str(investing.get("CNY", "-")),
            "-",
        ],
        ["USDT", "-", "-", "-", str(usdt)],
    ]
    return table

