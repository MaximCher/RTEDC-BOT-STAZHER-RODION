from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class UnitellerRegisterResponse:
    code: str
    note: str
    order_id: str
    link: str
    raw: Dict[str, Any]


def _sha256_ascii(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _md5_utf8(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def format_amount(amount: Decimal) -> str:
    normalized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{normalized:.2f}"


def current_date_msk() -> str:
    now = datetime.utcnow() + timedelta(hours=3)
    return now.strftime("%Y-%m-%d %H:%M:%S")


def build_return_url(base: str, path: str) -> str:
    parsed = urlparse(base)
    if not parsed.scheme or not parsed.netloc:
        return base
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def build_register_signature(
    *,
    order_id: str,
    upid: str,
    order_lifetime: str,
    current_date: str,
    subtotal_p: str,
    lifetime: str,
    password: str,
) -> str:
    payload = (
        _sha256_ascii(order_id)
        + "&"
        + _sha256_ascii(upid)
        + "&"
        + _sha256_ascii(order_lifetime)
        + "&"
        + _sha256_ascii(current_date)
        + "&"
        + _sha256_ascii(subtotal_p)
        + "&"
        + _sha256_ascii(lifetime)
        + "&"
        + _sha256_ascii(password)
    )
    return _sha256_ascii(payload).upper()


class UnitellerClient:
    def __init__(
        self,
        *,
        api_url: str,
        upid: str,
        password: str,
        timeout_sec: float = 15.0,
    ) -> None:
        self.api_url = api_url
        self.upid = upid
        self.password = password
        self.timeout_sec = timeout_sec

    async def register_payment_link(
        self,
        *,
        order_id: str,
        subtotal_p: Decimal,
        order_lifetime: str,
        current_date: str,
        lifetime: str,
        url_return: Optional[str] = None,
        url_return_ok: Optional[str] = None,
        url_return_no: Optional[str] = None,
        callback_fields: Optional[str] = None,
        callback_format: Optional[str] = None,
        merchant_order_id: Optional[str] = None,
        currency: Optional[str] = None,
        payment_type_limits: Optional[str] = None,
        customer_idp: Optional[str] = None,
        card_idp: Optional[str] = None,
        email: Optional[str] = None,
        preauth: Optional[str] = None,
    ) -> UnitellerRegisterResponse:
        subtotal_p_str = format_amount(subtotal_p)
        signature = build_register_signature(
            order_id=order_id,
            upid=self.upid,
            order_lifetime=order_lifetime,
            current_date=current_date,
            subtotal_p=subtotal_p_str,
            lifetime=lifetime,
            password=self.password,
        )

        payload: Dict[str, str] = {
            "OrderID": order_id,
            "UPID": self.upid,
            "OrderLifeTime": order_lifetime,
            "CurrentDate": current_date,
            "Subtotal_P": subtotal_p_str,
            "Lifetime": lifetime,
            "Signature": signature,
        }
        if url_return_ok and url_return_no:
            payload["URL_RETURN_OK"] = url_return_ok
            payload["URL_RETURN_NO"] = url_return_no
        elif url_return:
            payload["URL_RETURN"] = url_return
        if callback_fields:
            payload["CallbackFields"] = callback_fields
        if callback_format:
            payload["CallbackFormat"] = callback_format
        if merchant_order_id:
            payload["MerchantOrderId"] = merchant_order_id
        if currency:
            payload["Currency"] = currency
        if payment_type_limits:
            payload["PaymentTypeLimits"] = payment_type_limits
        if customer_idp:
            payload["Customer_IDP"] = customer_idp
        if card_idp:
            payload["Card_IDP"] = card_idp
        if email:
            payload["Email"] = email
        if preauth:
            payload["Preauth"] = preauth

        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            resp = await client.post(self.api_url, data=payload)
            resp.raise_for_status()
            data = resp.json()

        return UnitellerRegisterResponse(
            code=str(data.get("Code", "")),
            note=str(data.get("Note", "")),
            order_id=str(data.get("OrderID", "")),
            link=str(data.get("Link", "")),
            raw=data,
        )

    async def get_payment_status(
        self,
        *,
        results_url: str,
        shop_id: str,
        login: str,
        password: str,
        format_code: str,
        shop_order_number: str,
    ) -> tuple[Optional[str], str]:
        payload = {
            "Shop_ID": shop_id,
            "Login": login,
            "Password": password,
            "Format": format_code,
            "ShopOrderNumber": shop_order_number,
        }
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            resp = await client.post(results_url, data=payload)
            resp.raise_for_status()
            body = resp.text or ""
        status = _extract_status(body)
        return status, body


_STATUS_RE = re.compile(
    r"status[^a-z]*(waiting|not authorized|authorized|paid|canceled)",
    re.IGNORECASE,
)


def _extract_status(payload: str) -> Optional[str]:
    if not payload:
        return None
    match = _STATUS_RE.search(payload)
    if not match:
        return None
    return match.group(1).strip().lower()
