from __future__ import annotations

import html
from typing import Optional

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

UI_MESSAGE_ID_KEY = "_ui_message_id"


def format_step(*, title: str, step: int, total: int, question: str, intro: Optional[str] = None) -> str:
    title_h = html.escape(title)
    intro_h = html.escape(intro) if intro else ""
    question_h = html.escape(question)
    parts = [f"<b>{title_h}</b>", f"Шаг {step}/{total}"]
    if intro_h:
        parts.append(intro_h)
    parts.append("")
    parts.append(question_h)
    return "\n".join(parts).strip()


async def ui_upsert(
    *,
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    prefer_message_id: Optional[int] = None,
    parse_mode: str | None = "HTML",
) -> None:
    """
    Render flow UI in a single message:
    - If we have stored message_id -> edit it
    - Else if prefer_message_id provided -> try edit it and store
    - Else -> send a new message and store its id
    """
    data = await state.get_data()
    msg_id = data.get(UI_MESSAGE_ID_KEY)
    if isinstance(msg_id, int) and msg_id > 0:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return
        except Exception:
            # fall through and re-send
            pass

    if isinstance(prefer_message_id, int) and prefer_message_id > 0:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=prefer_message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            await state.update_data(**{UI_MESSAGE_ID_KEY: prefer_message_id})
            return
        except Exception:
            pass

    sent = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )
    await state.update_data(**{UI_MESSAGE_ID_KEY: int(sent.message_id)})


