from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.utils.keyboards import services_keyboard
from src.utils.messages import msg


router = Router()


@router.message(StateFilter(None), F.text)
async def fallback_to_menu(message: Message, state: FSMContext) -> None:
    """
    Safety net: if the bot was restarted and FSM state was lost, user messages would otherwise
    be ignored (no state-specific handler matches). Show the main menu instead.
    """
    try:
        if message.chat.type != ChatType.PRIVATE:
            return
    except Exception:
        # Defensive: if chat type is unavailable, do nothing.
        return

    text = (message.text or "").strip()
    if not text:
        return
    # Do not interfere with commands
    if text.startswith("/"):
        return

    await state.clear()
    await message.answer(msg("choose_service"), reply_markup=services_keyboard())


