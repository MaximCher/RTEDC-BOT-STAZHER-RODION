from __future__ import annotations

import asyncio
import re
from typing import Optional

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    ChatJoinRequest,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
    URLInputFile,
)
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.logger import logger
from src.menu.content import (
    CLUB_JOIN_INTRO,
    EVENT_INFO,
    MENU_TEXT,
    SERVICE_DESCRIPTIONS,
    SUBSERVICE_TEXTS,
    WELCOME_TEXT,
)
from src.menu.keyboards import (
    main_menu_keyboard,
    payments_submenu_keyboard,
    service_menu_keyboard,
)
from src.menu.rates import get_all_rates_table
from src.menu.table_image import draw_simple_table
from src.models.required_subscription import RequiredSubscription
from src.models.user_memory import UserMemory
from src.services.currency_rates_service import (
    ensure_full_refresh,
    format_rates_text,
    get_fast_snapshot,
    get_full_snapshot,
)
from src.services.events_service import get_latest_event_card
from src.services.staff_service import is_staff
from src.utils.access_gate import gate_keyboard, gate_text
from src.utils.event_media_cache import set_event_media
from src.utils.funnel import log_event
from src.utils.keyboards import lead_services_keyboard
from src.utils.messages import msg
from src.utils.ui_flow import ui_upsert

router = Router()

_EVENT_CHANNEL = "@rtedc_org"
_EVENT_CHANNEL_URL = "https://t.me/rtedc_org"


async def _ensure_event_subscription(callback: CallbackQuery) -> bool:
    try:
        cm = await callback.message.bot.get_chat_member(
            _EVENT_CHANNEL, callback.from_user.id
        )
        status = getattr(cm, "status", None)
        if status not in {"left", "kicked"}:
            return True
    except Exception:
        pass
    rows = [
        [
            InlineKeyboardButton(
                text="🔗 Подписаться на @rtedc_org",
                url=_EVENT_CHANNEL_URL,
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Проверить подписку",
                callback_data="events:check",
            )
        ],
    ]
    bot_username = settings.telegram_bot_username.strip().lstrip("@")
    if bot_username:
        rows.append(
            [
                InlineKeyboardButton(
                    text="↩️ Вернуться в бот",
                    url=f"https://t.me/{bot_username}?start=events",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="В главное меню", callback_data="menu:new")]
    )
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await callback.message.answer(
        "Чтобы посмотреть мероприятия, подпишитесь на @rtedc_org.",
        reply_markup=kb,
    )
    try:
        await callback.answer()
    except Exception:
        pass
    return False


def _chat_ref_for_api(chat_ref: str) -> str | int:
    t = (chat_ref or "").strip()
    if t.lstrip("-").isdigit():
        try:
            return int(t)
        except Exception:
            return t
    return t


async def _check_gate(
    *, bot, session: AsyncSession, user_id: int
) -> tuple[bool, list[RequiredSubscription]]:
    try:
        if await is_staff(session, user_id):
            return True, []
    except Exception:
        pass
    req = await RequiredSubscription.list_all(session)
    if not any(
        (it.chat_ref or "").strip().lstrip("@").lower()
        == _EVENT_CHANNEL.lstrip("@").lower()
        for it in req
    ):
        req.append(
            RequiredSubscription(
                kind="channel",
                chat_ref=_EVENT_CHANNEL,
                title="@rtedc_org",
                url=_EVENT_CHANNEL_URL,
            )
        )
    if not req:
        return True, []
    missing: list[RequiredSubscription] = []
    for it in req:
        t = (it.chat_ref or "").strip()
        # If chat_ref is a URL (invite), we cannot verify membership, so don't block.
        if t.startswith(("http://", "https://", "t.me/")):
            continue
        try:
            cm = await bot.get_chat_member(
                _chat_ref_for_api(it.chat_ref), user_id
            )
            status = getattr(cm, "status", None)
            if status in {"left", "kicked"}:
                missing.append(it)
        except Exception:
            missing.append(it)
    return len(missing) == 0, missing


class ApplyForm(StatesGroup):
    name = State()
    company = State()
    description = State()


class ClubForm(StatesGroup):
    fio = State()
    company = State()
    expectations = State()


class JoinRequestForm(StatesGroup):
    full_name = State()
    position = State()
    company = State()
    experience = State()
    business = State()
    hobbies = State()
    socials = State()


def _primary_manager_chat_id() -> Optional[int]:
    ids = settings.manager_chat_ids_list
    return ids[0] if ids else None


@router.callback_query(F.data == "back_to_main")
async def menu_back_to_main(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="menu",
        meta={"label": "Главное меню"},
    )
    # Handler moved to src.handlers.start (gate-aware). Kept here only for backward safety.
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("service_"))
async def menu_service_select(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    allowed, missing = await _check_gate(
        bot=callback.message.bot,
        session=session,
        user_id=callback.from_user.id,
    )
    if not allowed:
        await callback.message.answer(
            gate_text(missing), reply_markup=gate_keyboard(missing)
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return
    data = (callback.data or "").strip()
    # Persist topic for the "apply" form.
    await UserMemory.update_user_data(
        session, callback.from_user.id, selected_service=data
    )
    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="service_select",
        meta={"service": data, "label": data},
    )

    text = SERVICE_DESCRIPTIONS.get(data, data)

    def _service_btn(
        label: str, service_key: str
    ) -> list[InlineKeyboardButton]:
        return [
            InlineKeyboardButton(
                text=label,
                callback_data=f"service:{service_key}",
            )
        ]

    # Map menu items → новые калькуляторы (без общего хаба).
    mapped_buttons: list[list[InlineKeyboardButton]] = []
    if data == "service_payments":
        mapped_buttons.append(
            _service_btn(
                "⚡️ Оценить платеж / калькулятор", "international_payments"
            )
        )
        kb = payments_submenu_keyboard()
        kb.inline_keyboard.insert(0, mapped_buttons[0])
    elif data == "service_subsidies":
        mapped_buttons.append(
            _service_btn(
                "⚡️ Рассчитать субсидии/финансирование", "subsidies_financing"
            )
        )
        kb = service_menu_keyboard(extra_rows=mapped_buttons)
    elif data == "service_logistics":
        mapped_buttons.append(
            _service_btn("⚡️ Рассчитать логистику", "logistics_ved")
        )
        kb = service_menu_keyboard(extra_rows=mapped_buttons)
    elif data == "service_check":
        mapped_buttons.append(
            _service_btn("⚡️ Аналитика / проверка ВЭД", "analytics_tnved")
        )
        kb = service_menu_keyboard(extra_rows=mapped_buttons)
    elif data == "service_translate":
        # Нет отдельного калькулятора — оставляем заявку.
        kb = service_menu_keyboard()
    else:
        kb = service_menu_keyboard()

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("sub_payments_"))
async def menu_subservice_select(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    allowed, missing = await _check_gate(
        bot=callback.message.bot,
        session=session,
        user_id=callback.from_user.id,
    )
    if not allowed:
        await callback.message.answer(
            gate_text(missing), reply_markup=gate_keyboard(missing)
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return
    data = (callback.data or "").strip()
    # Store topic for apply form
    await UserMemory.update_user_data(
        session, callback.from_user.id, selected_service=data
    )
    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="subservice_select",
        meta={"subservice": data, "label": data},
    )

    text = SUBSERVICE_TEXTS.get(data, "Описание подуслуги.")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✉️ Подать запрос", callback_data="apply"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Назад", callback_data="service_payments"
                )
            ],
            [
                InlineKeyboardButton(
                    text="В главное меню", callback_data="menu:new"
                )
            ],
        ]
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "apply")
async def menu_apply_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Legacy "apply" CTA is replaced by our improved lead flow.
    We KEEP callback_data="apply" for backward compatibility with older messages.
    """
    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="cta_lead_start",
        meta={"label": "Заявка на консультацию"},
    )
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
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(ApplyForm.name)
async def menu_apply_name(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    # Safety net: if someone is stuck in the old FSM state, route them into the new lead flow.
    await state.clear()
    await message.answer(
        msg("choose_service"), reply_markup=lead_services_keyboard()
    )


@router.message(ApplyForm.company)
async def menu_apply_company(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    await message.answer(
        msg("choose_service"), reply_markup=lead_services_keyboard()
    )


@router.message(ApplyForm.description)
async def menu_apply_description(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    await message.answer(
        msg("choose_service"), reply_markup=lead_services_keyboard()
    )


@router.callback_query(F.data == "srvtevents")
async def menu_events(callback: CallbackQuery, session: AsyncSession) -> None:
    allowed, missing = await _check_gate(
        bot=callback.message.bot,
        session=session,
        user_id=callback.from_user.id,
    )
    if not allowed:
        await callback.message.answer(
            gate_text(missing), reply_markup=gate_keyboard(missing)
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return
    if not await _ensure_event_subscription(callback):
        return
    # Stop spinner without showing a popup.
    try:
        await callback.answer()
    except Exception:
        pass
    try:
        await log_event(
            session,
            user_id=callback.from_user.id,
            chat_id=callback.message.chat.id,
            username=callback.from_user.username,
            event="event_view",
            meta={"label": "Просмотр информации о мероприятии"},
        )
    except Exception:
        pass
    card = None
    try:
        card = await asyncio.wait_for(get_latest_event_card(), timeout=6.0)
    except Exception:
        card = None
    event_text = EVENT_INFO
    event_url = _EVENT_CHANNEL_URL
    image_urls: list[str] = []
    if card:
        event_text = card.text
        event_url = card.url or event_url
        image_urls = list(card.image_urls or [])
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Участвовать", url=event_url),
            ],
            [
                InlineKeyboardButton(
                    text="В главное меню", callback_data="menu:new"
                )
            ],
        ]
    )
    message = callback.message
    chat_id = message.chat.id if message else callback.from_user.id
    try:
        if card and card.is_past:
            await callback.message.answer(
                "⚠️ Мероприятие уже прошло. Мы обновим карточку, как появится следующее."
            )
        if image_urls:
            try:
                media: list[InputMediaPhoto] = []
                for url in image_urls:
                    media.append(InputMediaPhoto(media=URLInputFile(url)))
                if len(media) == 1:
                    msg = await callback.message.answer_photo(media[0].media)
                    set_event_media(
                        user_id=callback.from_user.id,
                        chat_id=chat_id,
                        message_ids=[msg.message_id],
                    )
                else:
                    messages = await callback.bot.send_media_group(
                        chat_id=chat_id, media=media
                    )
                    set_event_media(
                        user_id=callback.from_user.id,
                        chat_id=chat_id,
                        message_ids=[m.message_id for m in messages],
                    )
                await callback.message.answer(event_text, reply_markup=kb)
                return
            except Exception as exc:
                logger.warning(
                    "event_photo_send_failed",
                    error=str(exc),
                    image_urls=image_urls,
                )
        if message:
            await message.edit_text(event_text, reply_markup=kb)
        else:
            await callback.bot.send_message(
                chat_id=chat_id, text=event_text, reply_markup=kb
            )
    except Exception as exc:
        logger.warning(
            "event_card_send_failed", error=str(exc), text_len=len(event_text)
        )
        short_text = event_text
        if len(short_text) > 3500:
            short_text = short_text[:3500].rstrip() + "..."
        try:
            await callback.bot.send_message(
                chat_id=chat_id, text=short_text, reply_markup=kb
            )
        except Exception as exc2:
            logger.warning(
                "event_card_send_failed_fallback",
                error=str(exc2),
                text_len=len(short_text),
            )


@router.callback_query(F.data == "events:check")
async def menu_events_check(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    if not await _ensure_event_subscription(callback):
        return
    await menu_events(callback, session)


@router.callback_query(F.data == "currency_rates")
async def menu_currency_rates(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    allowed, missing = await _check_gate(
        bot=callback.message.bot,
        session=session,
        user_id=callback.from_user.id,
    )
    if not allowed:
        await ui_upsert(
            bot=callback.message.bot,
            state=state,
            chat_id=callback.message.chat.id,
            text=gate_text(missing),
            reply_markup=gate_keyboard(missing),
            keep_at_bottom=True,
            prefer_message_id=callback.message.message_id,
            persist=True,
            session=session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return
    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="currency_view",
        meta={"label": "Просмотр курсов валют"},
    )
    # UX improvement: show fast text instantly; image is available on-demand.
    try:
        snap = await get_fast_snapshot()
        await ensure_full_refresh()
        await ui_upsert(
            bot=callback.message.bot,
            state=state,
            chat_id=callback.message.chat.id,
            prefer_message_id=callback.message.message_id,
            text=format_rates_text(
                snap.table, header="Актуальные курсы валют"
            ),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📷 Таблица картинкой",
                            callback_data="currency:image",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="В главное меню", callback_data="menu:new"
                        )
                    ],
                ]
            ),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
    except Exception:
        await ui_upsert(
            bot=callback.message.bot,
            state=state,
            chat_id=callback.message.chat.id,
            prefer_message_id=callback.message.message_id,
            text="❌ Произошла ошибка при получении курсов валют. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="В главное меню", callback_data="menu:new"
                        )
                    ]
                ]
            ),
            keep_at_bottom=True,
            persist=True,
            session=session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "currency:image")
async def menu_currency_image(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    allowed, missing = await _check_gate(
        bot=callback.message.bot,
        session=session,
        user_id=callback.from_user.id,
    )
    if not allowed:
        await ui_upsert(
            bot=callback.message.bot,
            state=state,
            chat_id=callback.message.chat.id,
            text=gate_text(missing),
            reply_markup=gate_keyboard(missing),
            keep_at_bottom=True,
            prefer_message_id=callback.message.message_id,
            persist=True,
            session=session,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return

    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="currency_view",
        meta={"label": "Просмотр курсов валют (картинка)"},
    )

    # Immediate feedback (spinner -> message).
    try:
        await callback.answer()
    except Exception:
        pass
    sent: Message | None = None
    try:
        sent = await callback.message.answer(
            "⏳ Получаю курсы валют, подождите..."
        )
    except Exception:
        pass

    try:
        snap = await get_full_snapshot(image_path="/tmp/currency_table.png")
        if snap.image_path:
            await callback.message.answer_photo(
                FSInputFile(snap.image_path),
                caption="Таблица курсов валют",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="В главное меню", callback_data="menu:new"
                            )
                        ]
                    ]
                ),
            )
        else:
            await callback.message.answer(
                "❌ Не удалось собрать таблицу картинкой. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="В главное меню", callback_data="menu:new"
                            )
                        ]
                    ]
                ),
            )
        if sent:
            try:
                await sent.delete()
            except Exception:
                pass
    except Exception:
        if sent:
            try:
                await sent.edit_text(
                    "❌ Произошла ошибка при получении курсов валют. Попробуйте позже.",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="В главное меню",
                                    callback_data="menu:new",
                                )
                            ]
                        ]
                    ),
                )
                return
            except Exception:
                pass
        await callback.message.answer(
            "❌ Произошла ошибка при получении курсов валют. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="В главное меню", callback_data="menu:new"
                        )
                    ]
                ]
            ),
        )


@router.message(Command("currency"))
async def menu_currency_command(
    message: Message, session: AsyncSession
) -> None:
    # Handler moved to src.handlers.start (gate-aware). Keep as no-op fallback.
    return


@router.callback_query(F.data == "join_club")
async def menu_join_club_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    allowed, missing = await _check_gate(
        bot=callback.message.bot,
        session=session,
        user_id=callback.from_user.id,
    )
    if not allowed:
        await callback.message.answer(
            gate_text(missing), reply_markup=gate_keyboard(missing)
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return
    await log_event(
        session,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
        event="club_join_start",
        meta={"label": "Начало вступления в клуб"},
    )
    await callback.message.answer(CLUB_JOIN_INTRO)
    await callback.message.answer("Ваше ФИО:")
    await state.set_state(ClubForm.fio)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(ClubForm.fio)
async def menu_join_club_fio(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await log_event(
        session,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        username=message.from_user.username,
        event="club_join_step",
        meta={"step": "fio", "value": message.text, "label": "Шаг клуба: ФИО"},
    )
    await state.update_data(fio=message.text)
    await message.answer("Название вашей компании и сайт:")
    await state.set_state(ClubForm.company)


@router.message(ClubForm.company)
async def menu_join_club_company(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await log_event(
        session,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        username=message.from_user.username,
        event="club_join_step",
        meta={
            "step": "company",
            "value": message.text,
            "label": "Шаг клуба: Компания",
        },
    )
    await state.update_data(company=message.text)
    await message.answer("Ваши ожидания от членства в КЛУБЕ:")
    await state.set_state(ClubForm.expectations)


@router.message(ClubForm.expectations)
async def menu_join_club_expectations(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await log_event(
        session,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        username=message.from_user.username,
        event="club_join_submit",
        meta={"label": "Отправка заявки в клуб"},
    )
    data = await state.get_data()
    user = message.from_user
    user_link = f"[{user.full_name}](tg://user?id={user.id})"
    username = f"@{user.username}" if user.username else "(нет username)"
    text = (
        "Новая заявка в Клуб экспортеров и импортеров СРВТ.РФ:\n"
        f"Пользователь: {user_link} {username}\n"
        f"ID: {user.id}\n"
        f"ФИО: {data.get('fio')}\n"
        f"Компания и сайт: {data.get('company')}\n"
        f"Ожидания: {message.text}"
    )
    chat_id = _primary_manager_chat_id()
    if chat_id:
        try:
            await message.bot.send_message(
                chat_id, text, parse_mode="Markdown"
            )
        except Exception:
            pass
    await message.answer(
        "Ваша заявка принята и менеджер свяжется с вами по итогам рассмотрения или добавит в группу Клуба!"
    )
    await message.answer(MENU_TEXT, reply_markup=main_menu_keyboard())
    await state.clear()


# ============================================================
# Chat join request flow
# ============================================================


@router.message(Command("join"))
async def menu_join_command(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    """
    Legacy command entrypoint for the join form (parity with old bot).
    """
    allowed, missing = await _check_gate(
        bot=message.bot, session=session, user_id=message.from_user.id
    )
    if not allowed:
        await message.answer(
            gate_text(missing), reply_markup=gate_keyboard(missing)
        )
        return
    await state.clear()
    await message.answer("Ваша фамилия, имя, отчество?")
    await state.set_state(JoinRequestForm.full_name)


@router.chat_join_request()
async def menu_chat_join_request(
    event: ChatJoinRequest, session: AsyncSession
) -> None:
    # Only handle join requests to configured main group
    if settings.main_group_id and int(event.chat.id) != int(
        settings.main_group_id
    ):
        return
    user_id = event.from_user.id
    chat_title = event.chat.title or "наш клуб"
    text = (
        "Добрый день!\n\n"
        f"Чтобы вступить в {chat_title}, заполните короткую анкету — "
        "это поможет нам познакомить вас с участниками и красиво представить 🤝\n\n"
        "Нажмите кнопку ниже, чтобы начать заполнение анкеты:"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Заполнить анкету", callback_data="start_join_form"
                )
            ]
        ]
    )
    try:
        await event.bot.send_message(user_id, text, reply_markup=kb)
    except TelegramAPIError:
        return
    await log_event(
        session,
        user_id=user_id,
        chat_id=user_id,
        username=event.from_user.username,
        event="join_request_instruction_sent",
        meta={"chat_id": int(event.chat.id)},
    )


@router.callback_query(F.data == "start_join_form")
async def menu_start_join_form(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    allowed, missing = await _check_gate(
        bot=callback.message.bot,
        session=session,
        user_id=callback.from_user.id,
    )
    if not allowed:
        await callback.message.answer(
            gate_text(missing), reply_markup=gate_keyboard(missing)
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return
    await callback.answer()
    await callback.message.edit_text("Ваша фамилия, имя, отчество?")
    await state.set_state(JoinRequestForm.full_name)


@router.message(JoinRequestForm.full_name)
async def menu_join_full_name(message: Message, state: FSMContext) -> None:
    await state.update_data(full_name=message.text)
    await message.answer("Ваша должность?")
    await state.set_state(JoinRequestForm.position)


@router.message(JoinRequestForm.position)
async def menu_join_position(message: Message, state: FSMContext) -> None:
    await state.update_data(position=message.text)
    await message.answer("Компания и сайт?")
    await state.set_state(JoinRequestForm.company)


@router.message(JoinRequestForm.company)
async def menu_join_company(message: Message, state: FSMContext) -> None:
    await state.update_data(company=message.text)
    await message.answer("Опыт, достижения, чем гордитесь?")
    await state.set_state(JoinRequestForm.experience)


@router.message(JoinRequestForm.experience)
async def menu_join_experience(message: Message, state: FSMContext) -> None:
    await state.update_data(experience=message.text)
    await message.answer("Бизнес/индустрия, оборот, сотрудники?")
    await state.set_state(JoinRequestForm.business)


@router.message(JoinRequestForm.business)
async def menu_join_business(message: Message, state: FSMContext) -> None:
    await state.update_data(business=message.text)
    await message.answer("Хобби?")
    await state.set_state(JoinRequestForm.hobbies)


@router.message(JoinRequestForm.hobbies)
async def menu_join_hobbies(message: Message, state: FSMContext) -> None:
    await state.update_data(hobbies=message.text)
    await message.answer("Ссылки на соцсети?")
    await state.set_state(JoinRequestForm.socials)


@router.message(JoinRequestForm.socials)
async def menu_join_socials(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.update_data(socials=message.text)
    data = await state.get_data()
    await state.clear()

    user = message.from_user
    full_name = data.get("full_name", "")
    tg_name = user.full_name or ""
    username = f"@{user.username}" if user.username else ""
    user_display = f"{full_name} ({tg_name}) {username}".strip()
    user_link = f'<a href="tg://user?id={user.id}">{user.id}</a>'
    card = (
        "<b>Новая заявка</b>\n"
        f"Пользователь: {user_display}\n"
        f"ID: {user_link}\n"
        f"<b>Должность:</b> {data.get('position','')}\n"
        f"<b>Компания и сайт:</b> {data.get('company','')}\n"
        f"<b>ФИО:</b> {full_name}\n"
        f"<b>Опыт:</b> {data.get('experience','')}\n"
        f"<b>Бизнес:</b> {data.get('business','')}\n"
        f"<b>Хобби:</b> {data.get('hobbies','')}\n"
        f"<b>Соцсети:</b> {data.get('socials','')}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=f"approve:{user.id}:{settings.main_group_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"decline:{user.id}:{settings.main_group_id}",
                ),
            ]
        ]
    )
    chat_id = _primary_manager_chat_id()
    if chat_id:
        try:
            await message.bot.send_message(
                chat_id, card, parse_mode="HTML", reply_markup=kb
            )
        except Exception:
            pass
    await message.answer(
        "Спасибо! Ваша заявка отправлена на модерацию. Ожидайте решения."
    )
    await log_event(
        session,
        user_id=user.id,
        chat_id=message.chat.id,
        username=user.username,
        event="join_request_submitted",
        meta={"chat_id": int(settings.main_group_id or 0), **data},
    )


@router.callback_query(F.data.startswith(("approve:", "decline:")))
async def menu_join_decision(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    data = callback.data or ""
    try:
        action, user_id_s, chat_id_s = data.split(":")
        user_id = int(user_id_s)
        chat_id = int(chat_id_s)
    except Exception:
        await callback.answer("Ошибка данных", show_alert=True)
        return

    if callback.from_user.id not in set(settings.admin_user_ids_list):
        await callback.answer("Нет прав", show_alert=True)
        return

    try:
        await callback.message.edit_reply_markup()
    except Exception:
        pass

    if action == "approve":
        try:
            await callback.bot.approve_chat_join_request(chat_id, user_id)
        except Exception as e:
            await callback.answer(f"Ошибка: {e}", show_alert=True)
            return

        # Extract join-form fields from the message text.
        text = callback.message.text or callback.message.html_text or ""

        def extract_field(field: str, src: str) -> str:
            m = re.search(rf"{re.escape(field)}: ?(.+)", src)
            return m.group(1).strip() if m else ""

        full_name = extract_field("ФИО", text)
        position = extract_field("Должность", text)
        company = extract_field("Компания и сайт", text)
        experience = extract_field("Опыт", text)
        business = extract_field("Бизнес", text)
        hobbies = extract_field("Хобби", text)
        socials = extract_field("Соцсети", text)

        socials_line = f"<b>Соцсети:</b> {socials}" if socials else ""
        try:
            group = await callback.bot.get_chat(chat_id)
            group_title = getattr(group, "title", None) or "нашей группы"
        except Exception:
            group_title = "нашей группы"

        user_link = (
            f'<a href="tg://user?id={user_id}">{full_name or user_id}</a>'
        )
        welcome_text = (
            "<b>Добро пожаловать!</b>\n\n"
            f"Рады представить нового члена нашей группы «{group_title}»:\n\n"
            f"<b>{user_link}</b>\n"
            f"{position}, {company}\n\n"
            f"<b>Опыт:</b> {experience}\n"
            f"<b>Бизнес:</b> {business}\n"
            f"<b>Хобби:</b> {hobbies}\n"
            f"{socials_line}"
        )
        if settings.main_group_id:
            try:
                await callback.bot.send_message(
                    int(settings.main_group_id),
                    welcome_text,
                    parse_mode="HTML",
                )
            except Exception:
                pass
        try:
            await callback.bot.send_message(
                user_id, "Ваша заявка одобрена! Добро пожаловать!"
            )
        except Exception:
            pass
        await callback.answer("Заявка одобрена")
        await log_event(
            session,
            user_id=callback.from_user.id,
            chat_id=callback.message.chat.id,
            username=callback.from_user.username,
            event="join_request_approved",
            meta={"user_id": user_id, "chat_id": chat_id},
        )
    else:
        try:
            await callback.bot.decline_chat_join_request(chat_id, user_id)
        except Exception as e:
            await callback.answer(f"Ошибка: {e}", show_alert=True)
            return
        try:
            await callback.bot.send_message(
                user_id, "К сожалению, ваша заявка отклонена."
            )
        except Exception:
            pass
        await callback.answer("Заявка отклонена")
        await log_event(
            session,
            user_id=callback.from_user.id,
            chat_id=callback.message.chat.id,
            username=callback.from_user.username,
            event="join_request_declined",
            meta={"user_id": user_id, "chat_id": chat_id},
        )
