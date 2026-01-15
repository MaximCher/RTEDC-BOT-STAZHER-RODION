from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from sqlalchemy.ext.asyncio import AsyncSession

from src.handlers.start import _check_gate, _maybe_request_contact
from src.legacy.content import LEGACY_WELCOME_TEXT
from src.legacy.keyboards import legacy_main_menu_keyboard
from src.utils.access_gate import gate_keyboard, gate_text


router = Router()


@router.message(StateFilter(None), F.text)
async def fallback_to_menu(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
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
    allowed, missing, _ = await _check_gate(
        bot=message.bot, session=session, user_id=message.from_user.id
    )
    if not allowed:
        await message.answer(gate_text(missing), reply_markup=gate_keyboard(missing))
        return

    requested = await _maybe_request_contact(message, state, session)
    if requested:
        return

    await message.answer(LEGACY_WELCOME_TEXT, reply_markup=legacy_main_menu_keyboard())


