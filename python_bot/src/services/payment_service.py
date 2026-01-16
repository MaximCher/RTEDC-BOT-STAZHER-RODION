from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.consultation_request import ConsultationRequest
from src.models.payment import Payment
from src.models.payment_event import PaymentEvent
from src.services.consultation_service import submit_consultation
from src.services.uniteller_service import (
    UnitellerClient,
    build_callback_signature,
    build_return_url,
    current_date_msk,
    normalize_callback_payload,
)
from src.utils.funnel import log_event


@dataclass(frozen=True)
class PaymentConfig:
    enabled: bool
    amount: Decimal
    currency: str
    upid: str
    password: str
    order_lifetime: str
    form_lifetime: str
    api_url: str
    return_url: Optional[str]
    return_ok_url: Optional[str]
    return_no_url: Optional[str]
    callback_fields: Optional[str]
    callback_format: Optional[str]
    results_url: str
    results_login: Optional[str]
    results_password: Optional[str]
    results_shop_id: Optional[str]
    results_format: str


def get_payment_config() -> Optional[PaymentConfig]:
    if not settings.uniteller_enabled:
        return None
    if not settings.uniteller_upid or not settings.uniteller_password:
        return None
    if settings.consultation_price_rub is None:
        return None
    if settings.consultation_price_rub <= Decimal("0"):
        return None
    return PaymentConfig(
        enabled=True,
        amount=settings.consultation_price_rub,
        currency=settings.uniteller_currency or "RUB",
        upid=settings.uniteller_upid,
        password=settings.uniteller_password,
        order_lifetime=settings.uniteller_order_lifetime or "24:00",
        form_lifetime=settings.uniteller_form_lifetime or "",
        api_url=settings.uniteller_api_url,
        return_url=settings.uniteller_return_url or None,
        return_ok_url=settings.uniteller_return_ok_url or None,
        return_no_url=settings.uniteller_return_no_url or None,
        callback_fields=settings.uniteller_callback_fields or None,
        callback_format=settings.uniteller_callback_format or None,
        results_url=settings.uniteller_results_url,
        results_login=settings.uniteller_results_login or None,
        results_password=settings.uniteller_results_password or None,
        results_shop_id=settings.uniteller_results_shop_id or None,
        results_format=settings.uniteller_results_format or "4",
    )


def _build_default_return_urls() -> Tuple[str, str]:
    ok_url = build_return_url(settings.webapp_public_url, "/payment/ok")
    fail_url = build_return_url(settings.webapp_public_url, "/payment/fail")
    if not ok_url or not fail_url:
        ok_url = "https://wpay.uniteller.ru"
        fail_url = "https://wpay.uniteller.ru"
    return ok_url, fail_url


def _make_order_id(request_id: int) -> str:
    suffix = uuid4().hex[:8]
    order_id = f"srvt-{request_id}-{suffix}"
    return order_id[:64]


async def create_uniteller_payment(
    *,
    session: AsyncSession,
    request: ConsultationRequest,
) -> Optional[Payment]:
    cfg = get_payment_config()
    if not cfg:
        return None

    ok_url, fail_url = _build_default_return_urls()
    url_return_ok = cfg.return_ok_url or ok_url
    url_return_no = cfg.return_no_url or fail_url
    url_return = cfg.return_url

    order_id = _make_order_id(request.id)
    payment = Payment(
        provider="uniteller",
        order_id=order_id,
        upid=cfg.upid,
        amount=cfg.amount,
        currency=cfg.currency,
        status="pending",
        callback_fields=cfg.callback_fields,
        callback_format=cfg.callback_format,
        consultation_request_id=request.id,
    )
    session.add(payment)
    await session.flush()

    client = UnitellerClient(
        api_url=cfg.api_url,
        upid=cfg.upid,
        password=cfg.password,
    )
    try:
        response = await client.register_payment_link(
            order_id=order_id,
            subtotal_p=cfg.amount,
            order_lifetime=cfg.order_lifetime,
            current_date=current_date_msk(),
            lifetime=cfg.form_lifetime,
            url_return=url_return,
            url_return_ok=url_return_ok,
            url_return_no=url_return_no,
            callback_fields=cfg.callback_fields,
            callback_format=cfg.callback_format,
            currency=cfg.currency,
        )
    except Exception as exc:
        payment.status = "failed"
        payment.response_note = str(exc)
        await session.flush()
        return payment

    payment.response_code = response.code
    payment.response_note = response.note
    payment.raw_response = json.dumps(response.raw, ensure_ascii=False)
    if response.code in {"00", "04"} and response.link:
        payment.payment_link = response.link
        payment.status = "pending"
    else:
        payment.status = "failed"
    await session.flush()
    return payment


async def record_payment_event(
    session: AsyncSession,
    payment_id: int,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    session.add(
        PaymentEvent(
            payment_id=payment_id,
            event_type=event_type,
            payload=json.dumps(payload, ensure_ascii=False),
        )
    )
    await session.flush()


async def poll_payment_status(
    *,
    session: AsyncSession,
    payment: Payment,
) -> Optional[str]:
    cfg = get_payment_config()
    if not cfg:
        return None
    login = cfg.results_login
    if not login:
        return None
    shop_id = cfg.results_shop_id or cfg.upid
    password = cfg.results_password or cfg.password
    client = UnitellerClient(
        api_url=cfg.api_url,
        upid=cfg.upid,
        password=cfg.password,
    )
    try:
        status, raw = await client.get_payment_status(
            results_url=cfg.results_url,
            shop_id=shop_id,
            login=login,
            password=password,
            format_code=cfg.results_format,
            shop_order_number=payment.order_id,
        )
    except Exception as exc:
        await record_payment_event(
            session,
            payment.id,
            "results_poll_failed",
            {"error": str(exc)},
        )
        return None
    await record_payment_event(
        session,
        payment.id,
        "results_poll",
        {"status": status, "raw": raw[:4000]},
    )
    if not status:
        return None
    payment.status = status
    if status == "paid":
        payment.paid_at = datetime.utcnow()
    await session.flush()
    return status


async def handle_uniteller_callback(
    *,
    session: AsyncSession,
    payload: Dict[str, Any],
) -> Tuple[bool, Optional[Payment], Optional[ConsultationRequest]]:
    cfg = get_payment_config()
    if not cfg:
        return False, None, None

    normalized = normalize_callback_payload(payload)
    order_id = normalized.get("Order_ID") or normalized.get("OrderID") or ""
    status = normalized.get("Status") or ""
    signature = normalized.get("Signature") or ""

    if not order_id or not status or not signature:
        return False, None, None

    payment = (
        await session.execute(
            select(Payment).where(Payment.order_id == order_id)
        )
    ).scalar_one_or_none()
    if not payment:
        return False, None, None

    callback_fields = (payment.callback_fields or "").strip()
    fields = []
    if callback_fields:
        for item in callback_fields.split():
            fields.append(normalized.get(item, ""))

    expected_sig = build_callback_signature(
        order_id=order_id,
        status=status,
        fields=fields,
        password=cfg.password,
    )
    if signature.upper() != expected_sig.upper():
        await record_payment_event(
            session,
            payment.id,
            "callback_invalid_signature",
            normalized,
        )
        if payment.consultation_request_id:
            req = await session.get(
                ConsultationRequest, payment.consultation_request_id
            )
            if req:
                await log_event(
                    session,
                    user_id=req.user_id,
                    chat_id=req.chat_id,
                    username=req.username,
                    event="payment_callback_invalid",
                    service_key=req.service_key,
                    meta={"payment_id": payment.id},
                )
        return False, payment, None

    await record_payment_event(
        session,
        payment.id,
        "callback_received",
        normalized,
    )

    payment.status = status.lower()
    if payment.status == "paid":
        payment.paid_at = datetime.utcnow()
    await session.flush()

    request = (
        await session.execute(
            select(ConsultationRequest).where(
                ConsultationRequest.id == payment.consultation_request_id
            )
        )
    ).scalar_one_or_none()
    return True, payment, request


async def finalize_paid_request(
    *,
    session: AsyncSession,
    payment: Payment,
    request: ConsultationRequest,
) -> bool:
    if request.status in {"submitted", "closed"}:
        return False

    bot = Bot(token=settings.telegram_bot_token)
    try:
        created = await submit_consultation(
            session=session,
            bot=bot,
            user_id=request.user_id,
            chat_id=request.chat_id,
            service_key=request.service_key,
            full_name=request.full_name,
            phone=request.phone,
            username=request.username,
            inn=request.inn,
            summary_text=request.summary_text or "",
            meeting_window=request.meeting_window or "Не важно",
        )
        request.status = "submitted"
        request.payment_id = payment.id
        await session.commit()
        try:
            await log_event(
                session,
                user_id=request.user_id,
                chat_id=request.chat_id,
                username=request.username,
                event="payment_paid",
                service_key=request.service_key,
                meta={
                    "payment_id": payment.id,
                    "order_id": payment.order_id,
                },
            )
            await session.commit()
        except Exception:
            pass
        return created
    finally:
        await bot.session.close()
