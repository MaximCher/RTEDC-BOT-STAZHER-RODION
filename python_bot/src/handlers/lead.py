from __future__ import annotations

import re
from typing import Optional, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.dialog_message import DialogMessage
from src.models.consultation_request import ConsultationRequest
from src.models.payment import Payment
from src.models.user_memory import UserMemory
from src.services.payment_service import (
    create_uniteller_payment,
    finalize_paid_request,
    get_payment_config,
)
from src.utils.funnel import log_event
from src.utils.keyboards import (
    flow_nav_keyboard,
    lead_services_keyboard,
    meeting_window_keyboard,
    payment_link_keyboard,
    services_keyboard,
)
from src.utils.messages import msg
from src.utils.rate_limit import FixedWindowRateLimiter
from src.utils.service_entry import entry_screen_for_service
from src.utils.ui_flow import UI_MESSAGE_ID_KEY, format_step, ui_upsert

router = Router()

_lead_rate_limiter = FixedWindowRateLimiter(
    limit=3, window_sec=60
)  # 3 leads/min per user

_INN_RE = re.compile(r"(?<!\d)(\d{10}|\d{12})(?!\d)")


class LeadForm(StatesGroup):
    waiting_for_inn = State()
    waiting_for_contact_data = State()
    waiting_for_meeting_window = State()
    waiting_for_payment = State()


@router.callback_query(F.data == "lead:back")
async def lead_back(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    # UX: acknowledge click immediately to stop Telegram "loading" spinner
    try:
        await callback.answer()
    except Exception:
        pass
    current = await state.get_state()
    if current in {
        LeadForm.waiting_for_inn.state,
        LeadForm.waiting_for_contact_data.state,
    }:
        data = await state.get_data()
        service_key = (
            data.get("service_key")
            if isinstance(data.get("service_key"), str)
            else ""
        )
        await state.clear()
        text, kb, pm = entry_screen_for_service(service_key)
        await ui_upsert(
            bot=callback.message.bot,
            state=state,
            chat_id=callback.message.chat.id,
            prefer_message_id=callback.message.message_id,
            text=text,
            reply_markup=kb,
            parse_mode=pm,
            keep_at_bottom=True,
        )
        return

    if current == LeadForm.waiting_for_payment.state:
        await state.clear()
        await ui_upsert(
            bot=callback.message.bot,
            state=state,
            chat_id=callback.message.chat.id,
            prefer_message_id=callback.message.message_id,
            text=msg("welcome"),
            reply_markup=services_keyboard(),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        return

    if current != LeadForm.waiting_for_meeting_window.state:
        return

    data = await state.get_data()
    service_key = data.get("service_key")
    if not isinstance(service_key, str):
        await state.clear()
        try:
            await callback.message.edit_text(
                msg("welcome"), reply_markup=services_keyboard()
            )
        except Exception:
            await callback.message.answer(
                msg("welcome"), reply_markup=services_keyboard()
            )
        return

    # Go back to contact step (allow user to fix name/phone)
    await state.set_state(LeadForm.waiting_for_contact_data)
    await state.update_data(full_name=None, phone=None, username=None)

    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Заявка на консультацию",
            step=2,
            total=3,
            question=msg("lead_contact_request"),
        ),
        reply_markup=flow_nav_keyboard("lead:back"),
        keep_at_bottom=True,
        persist=True,
        session=session,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
    )


@router.callback_query(F.data.startswith("lead:start:"))
async def lead_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    # UX: acknowledge click immediately to stop Telegram "loading" spinner
    try:
        await callback.answer()
    except Exception:
        pass
    service_key = (callback.data or "").split("lead:start:", 1)[-1].strip()

    # Allow starting from global menus where a service isn't chosen yet.
    # In this case we do NOT create a lead with "unknown" — we route user to service selection.
    if not service_key or service_key not in SERVICES:
        await state.clear()
        await ui_upsert(
            bot=callback.message.bot,
            state=state,
            chat_id=callback.message.chat.id,
            prefer_message_id=callback.message.message_id,
            text=msg("choose_service"),
            reply_markup=lead_services_keyboard(),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        return
    await state.set_state(LeadForm.waiting_for_inn)
    await state.update_data(service_key=service_key)
    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="cta_lead_start",
        service_key=service_key,
    )
    await ui_upsert(
        bot=callback.message.bot,
        state=state,
        chat_id=callback.message.chat.id,
        prefer_message_id=callback.message.message_id,
        text=format_step(
            title="SRVT • Заявка на консультацию",
            step=1,
            total=3,
            question=msg("lead_inn_request"),
        ),
        reply_markup=flow_nav_keyboard("lead:back"),
        keep_at_bottom=True,
        persist=True,
        session=session,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
    )


@router.message(LeadForm.waiting_for_inn)
async def lead_process_inn(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    service_key = data.get("service_key")
    if not isinstance(service_key, str):
        await message.answer(
            msg("unknown_service"), reply_markup=services_keyboard()
        )
        await state.clear()
        return

    m = _INN_RE.search(text)
    if not m:
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=format_step(
                title="SRVT • Заявка на консультацию",
                step=1,
                total=3,
                intro="Ошибка: не вижу ИНН. Пришлите 10 или 12 цифр (без пробелов).",
                question=msg("lead_inn_request"),
            ),
            reply_markup=flow_nav_keyboard("lead:back"),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=message.from_user.id,
            username=message.from_user.username,
        )
        return

    inn = m.group(1)
    user_id = message.from_user.id
    await UserMemory.update_user_data(session, user_id, inn=inn)
    await log_event(
        session,
        user_id=user_id,
        chat_id=message.chat.id,
        username=message.from_user.username,
        event="inn_submitted",
        service_key=service_key,
        meta={"inn": inn},
    )
    await state.update_data(inn=inn)
    await state.set_state(LeadForm.waiting_for_contact_data)
    await ui_upsert(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        text=format_step(
            title="SRVT • Заявка на консультацию",
            step=2,
            total=3,
            question=msg("lead_contact_request"),
        ),
        reply_markup=flow_nav_keyboard("lead:back"),
        keep_at_bottom=True,
        persist=True,
        session=session,
        user_id=message.from_user.id,
        username=message.from_user.username,
    )


@router.message(LeadForm.waiting_for_contact_data)
async def lead_process_contact(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    service_key = data.get("service_key")
    if not isinstance(service_key, str):
        await message.answer(
            msg("unknown_service"), reply_markup=services_keyboard()
        )
        await state.clear()
        return

    full_name, phone = parse_contact_data(text)
    if not phone:
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text=format_step(
                title="SRVT • Заявка на консультацию",
                step=2,
                total=3,
                intro="Ошибка: не вижу телефон. Пример: Иванов Иван +79991234567",
                question=msg("lead_contact_request"),
            ),
            reply_markup=flow_nav_keyboard("lead:back"),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=message.from_user.id,
            username=message.from_user.username,
        )
        return

    user_id = message.from_user.id
    if not _lead_rate_limiter.allow(str(user_id)):
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            text="Слишком много заявок за минуту. Пожалуйста, попробуйте чуть позже.",
            reply_markup=services_keyboard(),
            parse_mode=None,
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=message.from_user.id,
            username=message.from_user.username,
        )
        return
    username = message.from_user.username

    # Pull questionnaire summary if exists
    questionnaire_summary = data.get("questionnaire_summary")
    summary_text = (
        questionnaire_summary if isinstance(questionnaire_summary, str) else ""
    )
    inn = data.get("inn") if isinstance(data.get("inn"), str) else None

    # Persist contact
    await UserMemory.update_user_data(
        session, user_id, full_name=full_name, phone=phone, inn=inn
    )

    await DialogMessage.create(
        session,
        user_id=user_id,
        username=username,
        full_name=full_name,
        phone=phone,
        message_text=text,
        role="user",
        chat_id=message.chat.id,
        message_id=message.message_id,
    )

    # Ask preferred meeting window as next step
    await state.update_data(
        full_name=full_name,
        phone=phone,
        username=username,
        questionnaire_summary=summary_text,
    )
    await state.set_state(LeadForm.waiting_for_meeting_window)
    await log_event(
        session,
        user_id=user_id,
        chat_id=message.chat.id,
        username=username,
        event="contact_submitted",
        service_key=service_key,
    )
    await ui_upsert(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        text=format_step(
            title="SRVT • Заявка на консультацию",
            step=3,
            total=3,
            question=msg("lead_meeting_window_request"),
        ),
        reply_markup=meeting_window_keyboard(include_back=True),
        keep_at_bottom=True,
        persist=True,
        session=session,
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=full_name,
        phone=phone,
    )


def _meeting_window_from_code(code: str) -> str:
    mapping = {
        "today_am": "Сегодня 10:00–13:00",
        "today_pm": "Сегодня 14:00–18:00",
        "tomorrow_am": "Завтра 10:00–13:00",
        "tomorrow_pm": "Завтра 14:00–18:00",
        "weekdays_19": "Будни после 19:00",
        "any": "Не важно",
    }
    return mapping.get(code, "Не важно")


async def _start_payment_flow(
    *,
    session: AsyncSession,
    state: FSMContext,
    bot,
    chat_id: int,
    user_id: int,
    service_key: str,
    full_name: Optional[str],
    phone: Optional[str],
    username: Optional[str],
    inn: Optional[str],
    summary_text: str,
    meeting_window: str,
    prefer_message_id: Optional[int] = None,
) -> None:
    cfg = get_payment_config()
    if not cfg:
        await ui_upsert(
            bot=bot,
            state=state,
            chat_id=chat_id,
            prefer_message_id=prefer_message_id,
            text=msg("lead_payment_error"),
            reply_markup=services_keyboard(),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=user_id,
            username=username,
            full_name=full_name,
            phone=phone,
        )
        return

    request = ConsultationRequest(
        user_id=user_id,
        chat_id=chat_id,
        service_key=service_key,
        full_name=full_name,
        phone=phone,
        username=username,
        inn=inn,
        summary_text=summary_text,
        meeting_window=meeting_window,
        status="pending_payment",
    )
    session.add(request)
    await session.flush()

    payment = await create_uniteller_payment(session=session, request=request)
    if not payment or not payment.payment_link or payment.status != "pending":
        request.status = "payment_failed"
        await session.commit()
        await log_event(
            session,
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            event="payment_failed",
            service_key=service_key,
            meta={"request_id": request.id},
        )
        await ui_upsert(
            bot=bot,
            state=state,
            chat_id=chat_id,
            prefer_message_id=prefer_message_id,
            text=msg("lead_payment_error"),
            reply_markup=services_keyboard(),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=user_id,
            username=username,
            full_name=full_name,
            phone=phone,
        )
        return

    request.payment_id = payment.id
    await session.commit()
    await log_event(
        session,
        user_id=user_id,
        chat_id=chat_id,
        username=username,
        event="payment_link_created",
        service_key=service_key,
        meta={"payment_id": payment.id},
    )

    await state.set_state(LeadForm.waiting_for_payment)
    await state.update_data(
        payment_id=payment.id,
        consultation_request_id=request.id,
    )

    amount_text = f"{cfg.amount:.2f} ₽"
    text = f"{msg('lead_payment_prompt')}\n\nСумма: {amount_text}"
    await ui_upsert(
        bot=bot,
        state=state,
        chat_id=chat_id,
        prefer_message_id=prefer_message_id,
        text=text,
        reply_markup=payment_link_keyboard(payment.payment_link, payment.id),
        keep_at_bottom=True,
        persist=True,
        session=session,
        user_id=user_id,
        username=username,
        full_name=full_name,
        phone=phone,
    )
    data = await state.get_data()
    prompt_id = data.get(UI_MESSAGE_ID_KEY)
    if isinstance(prompt_id, int) and prompt_id > 0:
        payment.prompt_message_id = prompt_id
        await session.commit()


@router.message(LeadForm.waiting_for_meeting_window)
async def lead_process_meeting_window(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    service_key = data.get("service_key")
    if not isinstance(service_key, str):
        await message.answer(
            msg("unknown_service"), reply_markup=services_keyboard()
        )
        await state.clear()
        return

    user_id = message.from_user.id
    full_name = (
        data.get("full_name")
        if isinstance(data.get("full_name"), str)
        else None
    )
    phone = data.get("phone") if isinstance(data.get("phone"), str) else None
    username = (
        data.get("username")
        if isinstance(data.get("username"), str)
        else message.from_user.username
    )
    inn = data.get("inn") if isinstance(data.get("inn"), str) else None

    summary_text = (
        data.get("questionnaire_summary")
        if isinstance(data.get("questionnaire_summary"), str)
        else ""
    )
    meeting_window = text[:300]
    if meeting_window.lower().strip() in {"не важно", "неважно", "any", "нет"}:
        meeting_window = "Не важно"
    await log_event(
        session,
        user_id=user_id,
        chat_id=message.chat.id,
        username=username,
        event="meeting_window_submitted",
        service_key=service_key,
        meta={"value": meeting_window},
    )
    await _start_payment_flow(
        session=session,
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
        user_id=user_id,
        service_key=service_key,
        full_name=full_name,
        phone=phone,
        username=username,
        inn=inn,
        summary_text=summary_text,
        meeting_window=meeting_window,
        prefer_message_id=message.message_id,
    )


@router.callback_query(F.data.startswith("lead:mw:"))
async def lead_meeting_window_pick(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    # Works only when user is in lead meeting window step
    current_state = await state.get_state()
    if current_state != LeadForm.waiting_for_meeting_window.state:
        await callback.answer(
            "Время для созвона можно выбрать после отправки контакта.",
            show_alert=True,
        )
        return

    code = (callback.data or "").split("lead:mw:", 1)[-1].strip()
    meeting_window = _meeting_window_from_code(code)

    data = await state.get_data()
    service_key = data.get("service_key")
    if not isinstance(service_key, str):
        await callback.message.answer(
            msg("unknown_service"), reply_markup=services_keyboard()
        )
        await state.clear()
        await callback.answer()
        return

    user_id = callback.from_user.id
    full_name = (
        data.get("full_name")
        if isinstance(data.get("full_name"), str)
        else None
    )
    phone = data.get("phone") if isinstance(data.get("phone"), str) else None
    username = (
        data.get("username")
        if isinstance(data.get("username"), str)
        else callback.from_user.username
    )
    inn = data.get("inn") if isinstance(data.get("inn"), str) else None
    summary_text = (
        data.get("questionnaire_summary")
        if isinstance(data.get("questionnaire_summary"), str)
        else ""
    )

    await log_event(
        session,
        user_id=user_id,
        chat_id=callback.message.chat.id,
        username=username,
        event="meeting_window_selected",
        service_key=service_key,
        meta={"value": meeting_window},
    )

    await _start_payment_flow(
        session=session,
        state=state,
        bot=callback.message.bot,
        chat_id=callback.message.chat.id,
        user_id=user_id,
        service_key=service_key,
        full_name=full_name,
        phone=phone,
        username=username,
        inn=inn,
        summary_text=summary_text,
        meeting_window=meeting_window,
        prefer_message_id=callback.message.message_id,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("payment:check:"))
async def lead_payment_check(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    raw = (callback.data or "").split("payment:check:", 1)[-1].strip()
    try:
        payment_id = int(raw)
    except ValueError:
        await callback.answer("Не удалось проверить оплату.", show_alert=True)
        return

    payment = await session.get(Payment, payment_id)
    if not payment:
        await callback.answer("Оплата не найдена.", show_alert=True)
        return

    request = None
    if payment.consultation_request_id:
        request = await session.get(ConsultationRequest, payment.consultation_request_id)

    if payment.status == "paid" and request:
        await finalize_paid_request(session=session, payment=payment, request=request)
        await ui_upsert(
            bot=callback.message.bot,
            state=state,
            chat_id=callback.message.chat.id,
            prefer_message_id=callback.message.message_id,
            text=msg("lead_payment_received"),
            reply_markup=services_keyboard(),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=request.full_name,
            phone=request.phone,
        )
        await callback.answer()
        await state.clear()
        return

    if not payment.payment_link:
        await ui_upsert(
            bot=callback.message.bot,
            state=state,
            chat_id=callback.message.chat.id,
            prefer_message_id=callback.message.message_id,
            text=msg("lead_payment_error"),
            reply_markup=services_keyboard(),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
    else:
        await ui_upsert(
            bot=callback.message.bot,
            state=state,
            chat_id=callback.message.chat.id,
            prefer_message_id=callback.message.message_id,
            text=msg("lead_payment_pending"),
            reply_markup=payment_link_keyboard(payment.payment_link, payment.id),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
    await callback.answer()


@router.message(LeadForm.waiting_for_payment)
async def lead_payment_pending(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    payment_id = data.get("payment_id")
    if not isinstance(payment_id, int):
        await message.answer(msg("lead_payment_pending"))
        return

    payment = await session.get(Payment, payment_id)
    if not payment:
        await message.answer(msg("lead_payment_pending"))
        return

    request = None
    if payment.consultation_request_id:
        request = await session.get(ConsultationRequest, payment.consultation_request_id)
    if payment.status == "paid" and request:
        await finalize_paid_request(session=session, payment=payment, request=request)
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            prefer_message_id=message.message_id,
            text=msg("lead_payment_received"),
            reply_markup=services_keyboard(),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=message.from_user.id,
            username=message.from_user.username,
            full_name=request.full_name,
            phone=request.phone,
        )
        await state.clear()
        return

    if not payment.payment_link:
        await ui_upsert(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            prefer_message_id=message.message_id,
            text=msg("lead_payment_error"),
            reply_markup=services_keyboard(),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=message.from_user.id,
            username=message.from_user.username,
        )
        return

    await ui_upsert(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        prefer_message_id=message.message_id,
        text=msg("lead_payment_pending"),
        reply_markup=payment_link_keyboard(payment.payment_link, payment.id),
        keep_at_bottom=True,
        persist=True,
        session=session,
        user_id=message.from_user.id,
        username=message.from_user.username,
    )


PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{7,}\d)")


def parse_contact_data(text: str) -> Tuple[str, Optional[str]]:
    phone_match = PHONE_RE.search(text)
    if not phone_match:
        return text.strip()[:200], None
    phone_raw = phone_match.group(1)
    phone = re.sub(r"[^\d+]", "", phone_raw)
    name = (text.replace(phone_raw, "")).strip()
    if not name:
        name = "Не указано"
    return name[:200], phone[:32]
