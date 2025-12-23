from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, MenuButtonWebApp, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.services.staff_service import is_admin
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
    await callback.message.edit_text(msg("choose_service"), reply_markup=services_keyboard())
    await callback.answer()


