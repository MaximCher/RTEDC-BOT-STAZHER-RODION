from __future__ import annotations

import html
from typing import Optional

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

UI_MESSAGE_ID_KEY = "_ui_message_id"
UI_MODE_KEY = "_ui_mode"


def _coerce_bool(v: object, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    return default


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
    keep_at_bottom: bool = False,
) -> None:
    """
    Render flow UI in a single message:
    Two modes:
    - keep_at_bottom=False (default): try to edit stored message_id (less API calls)
    - keep_at_bottom=True: send a new message and delete previous UI message (keeps UI near input)
    """
    data = await state.get_data()
    msg_id = data.get(UI_MESSAGE_ID_KEY)
    if keep_at_bottom:
        # Always create a fresh message to keep UI close to the input,
        # then best-effort delete the previous UI message.
        sent = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        new_id = int(sent.message_id)
        await state.update_data(**{UI_MESSAGE_ID_KEY: new_id, UI_MODE_KEY: "bottom"})
        # Best-effort cleanup
        # IMPORTANT: when we switch screens via callback_query, `prefer_message_id`
        # can point to the *entry screen* message, while `msg_id` points to a previous
        # transient UI message tracked in FSM. To prevent "double UI panels", try
        # deleting BOTH candidates if they are different.
        candidates: list[int] = []
        if isinstance(msg_id, int) and msg_id > 0:
            candidates.append(int(msg_id))
        if isinstance(prefer_message_id, int) and prefer_message_id > 0:
            candidates.append(int(prefer_message_id))
        for old_id in dict.fromkeys(candidates):  # stable unique
            if old_id <= 0 or old_id == new_id:
                continue
            try:
                await bot.delete_message(chat_id=chat_id, message_id=old_id)
            except Exception:
                pass
        return

    if isinstance(msg_id, int) and msg_id > 0:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            await state.update_data(**{UI_MODE_KEY: "edit"})
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
    await state.update_data(**{UI_MESSAGE_ID_KEY: int(sent.message_id), UI_MODE_KEY: "send"})


async def ui_send_persistent(
    *,
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str | None = "HTML",
    delete_transient: bool = True,
) -> None:
    """
    Send an important message that should remain in chat history (not edited/deleted later).
    Optionally deletes the current transient UI message tracked in state.
    """
    data = await state.get_data()
    msg_id = data.get(UI_MESSAGE_ID_KEY)
    if delete_transient and isinstance(msg_id, int) and msg_id > 0:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    # Clear transient tracking so future UI updates won't target the persistent message.
    await state.update_data(**{UI_MESSAGE_ID_KEY: 0, UI_MODE_KEY: "persistent"})


