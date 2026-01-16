from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from aiogram.utils.deep_linking import decode_payload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.menu.content import MENU_TEXT, WELCOME_TEXT
from src.menu.keyboards import main_menu_keyboard
from src.models.app_setting import AppSetting
from src.models.required_subscription import RequiredSubscription
from src.models.staff import StaffMember
from src.models.staff_invite import StaffInvite
from src.models.user_memory import UserMemory
from src.services.currency_rates_service import (
    ensure_full_refresh,
    format_rates_text,
    get_fast_snapshot,
)
from src.services.staff_service import is_admin, is_staff, touch_staff_profile
from src.utils.access_gate import gate_keyboard, gate_text
from src.utils.funnel import log_event
from src.utils.keyboards import services_keyboard
from src.utils.messages import msg
from src.utils.service_entry import entry_screen_for_service
from src.utils.webapp_url import get_webapp_public_url

router = Router()


class ContactRequest(StatesGroup):
    waiting_for_contact = State()


async def _ask_contact_enabled(session: AsyncSession) -> bool:
    raw = await AppSetting.get(session, "ask_contact_on_start")
    # Default ON if not set
    if raw is None or not str(raw).strip():
        return True
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


async def _required_subscriptions(
    session: AsyncSession,
) -> list[RequiredSubscription]:
    return await RequiredSubscription.list_all(session)


def _chat_ref_for_api(chat_ref: str) -> str | int:
    t = (chat_ref or "").strip()
    # If admin stored a URL (invite link), we can't verify via getChatMember.
    # Caller should skip verification in that case.
    if t.lstrip("-").isdigit():
        try:
            return int(t)
        except Exception:
            return t
    return t


async def _check_gate(
    *, bot, session: AsyncSession, user_id: int
) -> tuple[bool, list[RequiredSubscription], str | None]:
    # Staff should never be blocked by marketing gates
    try:
        if await is_staff(session, user_id):
            return True, [], None
    except Exception:
        pass

    req = await _required_subscriptions(session)
    if not req:
        return True, [], None

    missing: list[RequiredSubscription] = []
    for it in req:
        # If chat_ref is a URL, it's "open-only" (can't be verified).
        if (
            (it.chat_ref or "")
            .strip()
            .startswith(("http://", "https://", "t.me/"))
        ):
            continue
        try:
            cm = await bot.get_chat_member(
                _chat_ref_for_api(it.chat_ref), user_id
            )
            status = getattr(cm, "status", None)
            if status in {"left", "kicked"}:
                missing.append(it)
        except Exception:
            # If we cannot verify (bot not admin/member), treat as missing.
            missing.append(it)
    return len(missing) == 0, missing, None


async def _maybe_request_contact(
    message: Message, state: FSMContext, session: AsyncSession
) -> bool:
    """
    Ask user to share contact via ReplyKeyboard (Telegram requires explicit user action).
    Returns True if we requested contact, False otherwise.
    """
    if not await _ask_contact_enabled(session):
        return False

    # Requirement: ask contact only for a brand-new user (not yet in DB).
    # Existing users should not be asked again.
    um = (
        await session.execute(
            select(UserMemory).where(
                UserMemory.user_id == message.from_user.id
            )
        )
    ).scalar_one_or_none()
    if um is not None:
        return False

    # Create record for the new user
    um = await UserMemory.get_or_create(session, message.from_user.id)

    # Enter a dedicated state so we don't block other FSM flows with catch-all handlers.
    try:
        await state.set_state(ContactRequest.waiting_for_contact)
    except Exception:
        pass

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📲 Поделиться контактом", request_contact=True
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        selective=True,
    )
    await message.answer(
        "Чтобы менеджер мог быстро с вами связаться, поделитесь контактом (номер телефона).",
        reply_markup=kb,
    )
    return True


async def _open_menu_from_callback(
    *,
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    text: str,
) -> None:
    await state.clear()
    message = callback.message
    if message is None:
        try:
            await callback.answer()
        except Exception:
            pass
        return

    allowed, missing, _ = await _check_gate(
        bot=message.bot,
        session=session,
        user_id=callback.from_user.id,
    )
    if not allowed:
        await message.answer(gate_text(missing), reply_markup=gate_keyboard(missing))
        try:
            await callback.answer()
        except Exception:
            pass
        return

    requested = await _maybe_request_contact(message, state, session)
    if requested:
        try:
            await callback.answer()
        except Exception:
            pass
        return

    try:
        await message.edit_text(text, reply_markup=main_menu_keyboard())
    except Exception:
        try:
            sent = await message.answer(text, reply_markup=main_menu_keyboard())
            try:
                await message.delete()
            except Exception:
                pass
            message = sent
        except Exception:
            pass
    try:
        await callback.answer()
    except Exception:
        pass


async def _render_menu(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()

    # Legacy dashboard compatibility: log /start as before.
    try:
        await log_event(
            session,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            username=message.from_user.username,
            event="start",
            meta={"label": "Запуск бота"},
        )
    except Exception:
        pass

    # Update staff profile (if user is staff)
    try:
        await touch_staff_profile(
            session,
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
            tg_full_name=message.from_user.full_name,
        )
    except Exception:
        pass

    # If user is admin, enable "Admin panel" button near input (Telegram menu button)
    try:
        if await is_admin(session, message.from_user.id):
            await message.bot.set_chat_menu_button(
                chat_id=message.chat.id,
                menu_button=MenuButtonWebApp(
                    text="Админка SRVT",
                    web_app=WebAppInfo(
                        url=get_webapp_public_url(settings.webapp_public_url)
                    ),
                ),
            )
    except Exception:
        # do not block /start on menu button errors
        pass

    allowed, missing, _ = await _check_gate(
        bot=message.bot, session=session, user_id=message.from_user.id
    )
    if not allowed:
        await message.answer(
            gate_text(missing), reply_markup=gate_keyboard(missing)
        )
        return

    # Optional: ask contact right after access check
    requested = await _maybe_request_contact(message, state, session)
    if requested:
        return

    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


async def _render_main_menu(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    *,
    text: str,
    event: str,
) -> None:
    """
    Render the main menu through the same access/contacts gates.
    Used for both /start (welcome) and /menu (plain menu).
    """
    await state.clear()

    try:
        await log_event(
            session,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            username=message.from_user.username,
            event=event,
            meta={"label": "Главное меню"},
        )
    except Exception:
        pass

    # Update staff profile (if user is staff)
    try:
        await touch_staff_profile(
            session,
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
            tg_full_name=message.from_user.full_name,
        )
    except Exception:
        pass

    allowed, missing, _ = await _check_gate(
        bot=message.bot, session=session, user_id=message.from_user.id
    )
    if not allowed:
        await message.answer(
            gate_text(missing), reply_markup=gate_keyboard(missing)
        )
        return

    requested = await _maybe_request_contact(message, state, session)
    if requested:
        return

    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await _render_menu(message, state, session)


@router.message(Command("menu"))
async def cmd_menu(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await _render_main_menu(
        message,
        state,
        session,
        text=MENU_TEXT,
        event="menu",
    )


@router.callback_query(F.data == "back_to_main")
async def back_to_main(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Legacy callback used by old keyboards. Route it through gate/contacts and
    render menu, стараясь редактировать/заменять сообщение без спама.
    """
    await _open_menu_from_callback(
        callback=callback,
        state=state,
        session=session,
        text=MENU_TEXT,
    )


@router.message(Command("currency"))
async def cmd_currency(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    """
    Legacy command /currency (text output) routed through gate.
    """
    await state.clear()
    allowed, missing, _ = await _check_gate(
        bot=message.bot, session=session, user_id=message.from_user.id
    )
    if not allowed:
        await message.answer(
            gate_text(missing), reply_markup=gate_keyboard(missing)
        )
        return
    try:
        await log_event(
            session,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            username=message.from_user.username,
            event="currency_view",
            meta={"label": "Просмотр курсов валют"},
        )
    except Exception:
        pass
    try:
        snap = await get_fast_snapshot()
        await ensure_full_refresh()
        await message.answer(
            format_rates_text(snap.table, header="Актуальные курсы валют"),
            parse_mode="HTML",
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
        )
    except Exception:
        await message.answer(
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


@router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    command: CommandObject,
) -> None:
    # Deep-link invite: /start invite_<token>
    raw_args = (command.args or "").strip()
    payload = raw_args
    if raw_args:
        try:
            payload = decode_payload(raw_args)
        except Exception:
            payload = raw_args
    if payload.startswith("invite_"):
        token = payload.split("invite_", 1)[-1].strip()
        inv = await StaffInvite.get_by_token(session, token)
        if (
            inv
            and inv.used_by_tg_user_id is None
            and (not inv.expires_at or inv.expires_at >= datetime.utcnow())
        ):
            existing = (
                await session.execute(
                    select(StaffMember).where(
                        StaffMember.tg_user_id == message.from_user.id
                    )
                )
            ).scalar_one_or_none()
            if existing:
                existing.role = inv.role
                existing.tg_username = message.from_user.username
                existing.tg_full_name = message.from_user.full_name
                existing.last_seen_at = datetime.utcnow()
            else:
                session.add(
                    StaffMember(
                        tg_user_id=message.from_user.id,
                        role=inv.role,
                        tg_username=message.from_user.username,
                        tg_full_name=message.from_user.full_name,
                        last_seen_at=datetime.utcnow(),
                    )
                )
            inv.used_by_tg_user_id = message.from_user.id
            inv.used_at = datetime.utcnow()
            await session.commit()
            await message.answer(
                f"Готово! Вы добавлены как **{inv.role}**.",
                parse_mode="Markdown",
            )
        else:
            await message.answer("Приглашение недействительно или истекло.")
    await _render_menu(message, state, session)


@router.callback_query(F.data == "menu:root")
async def back_to_menu(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    # UX: keep Telegram "loading" animation on the pressed button.
    # We'll answer the callback after UI is rendered.
    await _open_menu_from_callback(
        callback=callback,
        state=state,
        session=session,
        text=MENU_TEXT,
    )


@router.callback_query(F.data == "menu:new")
async def open_menu_new_message(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Open menu, предпочитая редактирование сообщения, чтобы не плодить новые."""
    await _open_menu_from_callback(
        callback=callback,
        state=state,
        session=session,
        text=MENU_TEXT,
    )


@router.callback_query(F.data == "srvt:services")
async def open_srvt_services(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Entry point from the main menu into the SRVT service flows.
    Opens a NEW message to avoid overwriting important content.
    """
    allowed, missing, _ = await _check_gate(
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
    requested = await _maybe_request_contact(callback.message, state, session)
    if not requested:
        await state.clear()
        await callback.message.answer(
            msg("welcome"), reply_markup=services_keyboard()
        )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "gate:check")
async def gate_check(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    allowed, missing, _ = await _check_gate(
        bot=callback.message.bot,
        session=session,
        user_id=callback.from_user.id,
    )
    if not allowed:
        try:
            await callback.message.edit_text(
                gate_text(missing), reply_markup=gate_keyboard(missing)
            )
        except Exception:
            await callback.message.answer(
                gate_text(missing), reply_markup=gate_keyboard(missing)
            )
        try:
            await callback.answer(
                "Подписки не найдены. Проверьте ещё раз.", cache_time=1
            )
        except Exception:
            pass
        return

    # Access ok — ask contact (optional) or show menu
    requested = await _maybe_request_contact(callback.message, state, session)
    if requested:
        try:
            await callback.answer("Доступ подтверждён ✅", cache_time=1)
        except Exception:
            pass
        return
    try:
        await callback.message.edit_text(
            WELCOME_TEXT, reply_markup=main_menu_keyboard()
        )
    except Exception:
        await callback.message.answer(
            WELCOME_TEXT, reply_markup=main_menu_keyboard()
        )
    try:
        await callback.answer("Доступ подтверждён ✅", cache_time=1)
    except Exception:
        pass


@router.message(F.contact)
async def on_contact_shared(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    # Save contact to user profile
    contact = message.contact
    phone = getattr(contact, "phone_number", None) or ""
    phone = phone.strip()
    if phone:
        await UserMemory.update_user_data(
            session,
            message.from_user.id,
            phone=phone,
            full_name=message.from_user.full_name,
        )
        # Ensure the phone is visible within this handler before we render menu again.
        try:
            await session.flush()
        except Exception:
            pass
    # Hide reply keyboard and show menu
    await message.answer("Спасибо! ✅", reply_markup=ReplyKeyboardRemove())
    await _render_menu(message, state, session)


@router.message(ContactRequest.waiting_for_contact)
async def contact_required_repeat(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    """
    While waiting for mandatory contact, ignore normal messages and keep prompting.
    This must NOT intercept other FSM flows.
    """
    if message.contact is not None:
        return
    if not await _ask_contact_enabled(session):
        await state.clear()
        await _render_menu(message, state, session)
        return
    um = await UserMemory.get_or_create(session, message.from_user.id)
    if um.phone:
        await _render_menu(message, state, session)
        return
    allowed, missing, _ = await _check_gate(
        bot=message.bot, session=session, user_id=message.from_user.id
    )
    if not allowed:
        await message.answer(
            gate_text(missing), reply_markup=gate_keyboard(missing)
        )
        return
    await _maybe_request_contact(message, state, session)


@router.callback_query(ContactRequest.waiting_for_contact)
async def contact_required_block_callbacks(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """
    Prevent using the bot via old inline buttons until contact is shared.
    """
    um = await UserMemory.get_or_create(session, callback.from_user.id)
    if um.phone:
        await state.clear()
        await callback.answer()
        return
    try:
        await callback.answer(
            "Сначала поделитесь контактом (кнопка «📲 Поделиться контактом»).",
            show_alert=True,
        )
    except Exception:
        pass
    try:
        await _maybe_request_contact(callback.message, state, session)
    except Exception:
        pass


@router.callback_query(F.data.startswith("entry:new:"))
async def open_entry_new_message(callback: CallbackQuery) -> None:
    """Open a service entry screen without editing/deleting the current message."""
    # UX: keep Telegram "loading" animation on the pressed button.
    # We'll answer the callback after UI is rendered.
    service_key = (callback.data or "").split("entry:new:", 1)[-1].strip()
    text, kb, pm = entry_screen_for_service(service_key)
    await callback.message.answer(text, reply_markup=kb, parse_mode=pm)
    try:
        await callback.answer()
    except Exception:
        pass
