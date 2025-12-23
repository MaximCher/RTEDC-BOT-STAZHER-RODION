from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.utils.keyboards import services_keyboard
from src.utils.messages import msg


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(msg("welcome"), reply_markup=services_keyboard())


@router.callback_query(F.data == "menu:root")
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(msg("choose_service"), reply_markup=services_keyboard())
    await callback.answer()


