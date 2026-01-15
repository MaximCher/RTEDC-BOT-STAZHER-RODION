from __future__ import annotations

import json
import logging
import time
import traceback
from typing import Dict


def get_cbr_rates() -> Dict[str, object]:
    """
    CBR XML daily rates (USD/EUR/CNY).
    Returns dict with float or '-' values.
    """
    import requests
    from bs4 import BeautifulSoup

    url = "https://www.cbr.ru/scripts/XML_daily.asp"
    try:
        res = requests.get(url, timeout=10)
        res.encoding = "windows-1251"
        soup = BeautifulSoup(res.text, "xml")
        rates: Dict[str, object] = {}
        for code in ["USD", "EUR", "CNY"]:
            val = soup.find("CharCode", string=code)
            if val:
                parent = val.find_parent("Valute")
                value = parent.Value.text.replace(",", ".")
                nominal = float(parent.Nominal.text)
                rates[code] = round(float(value) / nominal, 4)
        return rates
    except Exception as e:
        logging.error(
            "CBR rates error: %s\n%s", e, traceback.format_exc()
        )
        return {k: "-" for k in ["USD", "EUR", "CNY"]}


def get_investing_rates() -> Dict[str, object]:
    """
    Investing.com (EUR/CNY). USD not parsed in legacy implementation.
    """
    import requests
    from bs4 import BeautifulSoup

    rates: Dict[str, object] = {"USD": "-"}
    urls = {
        "EUR": "https://uk.investing.com/currencies/eur-rub-chart",
        "CNY": "https://uk.investing.com/currencies/cny-rub",
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    for code, url in urls.items():
        try:
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            price_tags = soup.find_all("div", {"data-test": "instrument-price-last"})
            if price_tags:
                rate_text = (
                    price_tags[0]
                    .text.replace(",", ".")
                    .replace("\xa0", "")
                    .strip()
                )
                try:
                    rates[code] = float(rate_text)
                except Exception:
                    logging.error("Cannot parse %s rate: '%s'", code, rate_text)
                    rates[code] = "-"
            else:
                logging.error(
                    "Investing %s element not found. HTML: %s",
                    code,
                    res.text[:2000],
                )
                rates[code] = "-"
        except Exception as e:
            logging.error(
                "Investing %s error: %s\n%s", code, e, traceback.format_exc()
            )
            rates[code] = "-"
    return rates


def get_rapira_usdt_title() -> object:
    """
    USDT/RUB from rapira.net title via Selenium (headless).
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait

    url = "https://rapira.net/exchange/USDT_RUB"
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            lambda d: d.title != "Rapira" and "USDT/RUB" in d.title
        )
        import re

        match = re.match(r"([\d.]+) \| USDT/RUB", driver.title)
        if match:
            return float(match.group(1))
        logging.error("USDT rate not found in title: %s", driver.title)
        return "-"
    except Exception as e:
        logging.error(
            "Rapira title error: %s\n%s", e, traceback.format_exc()
        )
        return "-"
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def get_profinance_usd_last_selenium() -> object:
    """
    USD/RUB last from profinance.ru via Selenium.
    """
    from bs4 import BeautifulSoup
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    url = "https://www.profinance.ru/currency_usd.asp"
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//table[contains(@class, 'currency-table') or "
                    "contains(@class, 'table-body') or "
                    "contains(@class, 'pfs-news-2x5') or "
                    "contains(@class, 'stat')]",
                )
            )
        )
        time.sleep(1)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        row = soup.find("td", id="USDRUB") or soup.find("td", string="USD/RUB")
        if not row:
            raise Exception("USD/RUB row not found")
        tr = row.find_parent("tr")
        last_td = tr.find("td", class_="col-last")
        if not last_td:
            raise Exception("col-last not found")
        main = last_td.contents[0].strip()
        span = last_td.find("span", class_="last-digit")
        last = main + (span.text.strip() if span else "")
        return float(last)
    except Exception as e:
        logging.error(
            "Profinance selenium error: %s\n%s", e, traceback.format_exc()
        )
        return "-"
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def _debug_json_dump(obj: object) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)

