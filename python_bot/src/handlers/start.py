from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.utils.deep_linking import decode_payload
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, MenuButtonWebApp, WebAppInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.staff import StaffMember
from src.models.staff_invite import StaffInvite
from src.services.staff_service import is_admin, touch_staff_profile
from src.utils.service_entry import entry_screen_for_service
from src.utils.keyboards import services_keyboard
from src.utils.messages import msg
from src.utils.webapp_url import get_webapp_public_url


router = Router()


async def _render_menu(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()

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
                    web_app=WebAppInfo(url=get_webapp_public_url(settings.webapp_public_url)),
                ),
            )
    except Exception:
        # do not block /start on menu button errors
        pass
    await message.answer(msg("welcome"), reply_markup=services_keyboard())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _render_menu(message, state, session)


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
        if inv and inv.used_by_tg_user_id is None and (not inv.expires_at or inv.expires_at >= datetime.utcnow()):
            existing = (
                await session.execute(select(StaffMember).where(StaffMember.tg_user_id == message.from_user.id))
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
            await message.answer(f"Готово! Вы добавлены как **{inv.role}**.", parse_mode="Markdown")
        else:
            await message.answer("Приглашение недействительно или истекло.")
    await _render_menu(message, state, session)


@router.callback_query(F.data == "menu:root")
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    # UX: acknowledge click immediately to stop Telegram "loading" spinner
    try:
        await callback.answer()
    except Exception:
        pass
    await state.clear()
    # UX: avoid chat spam. Prefer re-rendering menu in the same message.
    try:
        await callback.message.edit_text(msg("welcome"), reply_markup=services_keyboard())
        return
    except Exception:
        pass

    # Fallback: if message can't be edited (too old, etc.) delete & send one fresh menu.
    chat_id = callback.message.chat.id
    try:
        await callback.message.delete()
    except Exception:
        pass
    try:
        await callback.message.bot.send_message(chat_id, msg("welcome"), reply_markup=services_keyboard())
    except Exception:
        pass


@router.callback_query(F.data == "menu:new")
async def open_menu_new_message(callback: CallbackQuery) -> None:
    """Open menu without editing/deleting the current message (keeps important info in history)."""
    # UX: acknowledge click immediately to stop Telegram "loading" spinner
    try:
        await callback.answer()
    except Exception:
        pass
    await callback.message.answer(msg("welcome"), reply_markup=services_keyboard())


@router.callback_query(F.data.startswith("entry:new:"))
async def open_entry_new_message(callback: CallbackQuery) -> None:
    """Open a service entry screen without editing/deleting the current message."""
    # UX: acknowledge click immediately to stop Telegram "loading" spinner
    try:
        await callback.answer()
    except Exception:
        pass
    service_key = (callback.data or "").split("entry:new:", 1)[-1].strip()
    text, kb, pm = entry_screen_for_service(service_key)
    await callback.message.answer(text, reply_markup=kb, parse_mode=pm)


