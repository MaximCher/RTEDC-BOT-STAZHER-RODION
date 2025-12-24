from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, MenuButtonWebApp, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.services.staff_service import is_admin
from src.utils.service_entry import entry_screen_for_service
from src.utils.keyboards import services_keyboard
from src.utils.messages import msg


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    # If user is admin, enable "Admin panel" button near input (Telegram menu button)
    try:
        if await is_admin(session, message.from_user.id):
            await message.bot.set_chat_menu_button(
                chat_id=message.chat.id,
                menu_button=MenuButtonWebApp(
                    text="Админка SRVT",
                    web_app=WebAppInfo(url=settings.webapp_public_url),
                ),
            )
    except Exception:
        # do not block /start on menu button errors
        pass
    await message.answer(msg("welcome"), reply_markup=services_keyboard())


@router.callback_query(F.data == "menu:root")
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    # UX: avoid chat spam. Prefer re-rendering menu in the same message.
    try:
        await callback.message.edit_text(msg("choose_service"), reply_markup=services_keyboard())
        await callback.answer()
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
        await callback.message.bot.send_message(chat_id, msg("choose_service"), reply_markup=services_keyboard())
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "menu:new")
async def open_menu_new_message(callback: CallbackQuery) -> None:
    """Open menu without editing/deleting the current message (keeps important info in history)."""
    await callback.message.answer(msg("choose_service"), reply_markup=services_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("entry:new:"))
async def open_entry_new_message(callback: CallbackQuery) -> None:
    """Open a service entry screen without editing/deleting the current message."""
    service_key = (callback.data or "").split("entry:new:", 1)[-1].strip()
    text, kb, pm = entry_screen_for_service(service_key)
    await callback.message.answer(text, reply_markup=kb, parse_mode=pm)
    await callback.answer()


