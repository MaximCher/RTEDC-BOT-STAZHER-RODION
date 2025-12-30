from __future__ import annotations

import asyncio
import html
import re
from typing import Optional

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.dialog_message import DialogMessage

UI_MESSAGE_ID_KEY = "_ui_message_id"
UI_MODE_KEY = "_ui_mode"

_DEFAULT_STEP_HINT = (
    "Ответьте на вопрос ниже — можно коротко (1–2 слова/фразы)."
)


def _coerce_bool(v: object, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    return default


def format_step(
    *,
    title: str,
    step: int,
    total: int,
    question: str,
    intro: Optional[str] = None,
) -> str:
    title_h = html.escape(title)
    intro_h = html.escape(intro) if intro else html.escape(_DEFAULT_STEP_HINT)
    question_h = html.escape(question)
    parts = [f"<b>{title_h}</b>", f"Шаг {step}/{total}"]
    if intro_h:
        parts.append(intro_h)
    parts.append("")
    parts.append(question_h)
    return "\n".join(parts).strip()


def _to_plain_text(text: str) -> str:
    """
    Admin UI renders plain text. When we send HTML to Telegram, store a readable version.
    """
    raw = text or ""
    # naive, but good enough for our limited markup usage (<b>, <i>, etc.)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = html.unescape(raw).strip()
    # Make history less "technical": drop the "Шаг X/Y" line from format_step().
    lines = [ln.strip() for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]
    if len(lines) >= 2 and re.match(r"^Шаг\s+\d+\s*/\s*\d+\s*$", lines[1]):
        lines.pop(1)
    return "\n".join(lines).strip()


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
    # Optional: persist message to admin "conversation" history (DialogMessage)
    persist: bool = False,
    session: Optional[AsyncSession] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
    phone: Optional[str] = None,
) -> None:
    """
    Render flow UI in a single message:
    Two modes:
    - keep_at_bottom=False (default): try to edit stored message_id (less API calls)
    - keep_at_bottom=True: send a new message and delete previous UI message (keeps UI near input)
    """
    data = await state.get_data()
    msg_id = data.get(UI_MESSAGE_ID_KEY)
    ui_mode = data.get(UI_MODE_KEY)
    if keep_at_bottom:
        # Always create a fresh message to keep UI close to the input,
        # then best-effort delete the previous UI message.
        sent = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        if (
            persist
            and session is not None
            and isinstance(user_id, int)
            and user_id > 0
        ):
            try:
                await DialogMessage.create(
                    session,
                    user_id=user_id,
                    username=username,
                    full_name=full_name,
                    phone=phone,
                    message_text=_to_plain_text(text),
                    role="assistant",
                    chat_id=chat_id,
                    message_id=int(sent.message_id),
                )
            except Exception:
                pass
        new_id = int(sent.message_id)
        await state.update_data(
            **{UI_MESSAGE_ID_KEY: new_id, UI_MODE_KEY: "bottom"}
        )
        # Best-effort cleanup
        # IMPORTANT: when we switch screens via callback_query, `prefer_message_id`
        # can point to the *entry screen* message, while `msg_id` points to a previous
        # transient UI message tracked in FSM. To prevent "double UI panels", try
        # deleting BOTH candidates if they are different.
        candidates: list[int] = []
        if isinstance(msg_id, int) and msg_id > 0:
            candidates.append(int(msg_id))
        # IMPORTANT: never delete a user-clicked "important" message.
        # After ui_send_persistent() we set UI_MODE_KEY="persistent" and clear UI_MESSAGE_ID_KEY,
        # so prefer_message_id can point to an important message (e.g. "Что сделаем дальше").
        if (
            ui_mode != "persistent"
            and isinstance(prefer_message_id, int)
            and prefer_message_id > 0
        ):
            candidates.append(int(prefer_message_id))
        for old_id in dict.fromkeys(candidates):  # stable unique
            if old_id <= 0 or old_id == new_id:
                continue
            try:
                # Fire-and-forget: deletion is non-critical and can be slow.
                asyncio.create_task(
                    bot.delete_message(chat_id=chat_id, message_id=old_id)
                )
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
            if (
                persist
                and session is not None
                and isinstance(user_id, int)
                and user_id > 0
            ):
                try:
                    await DialogMessage.create(
                        session,
                        user_id=user_id,
                        username=username,
                        full_name=full_name,
                        phone=phone,
                        message_text=_to_plain_text(text),
                        role="assistant",
                        chat_id=chat_id,
                        message_id=int(msg_id),
                    )
                except Exception:
                    pass
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
            if (
                persist
                and session is not None
                and isinstance(user_id, int)
                and user_id > 0
            ):
                try:
                    await DialogMessage.create(
                        session,
                        user_id=user_id,
                        username=username,
                        full_name=full_name,
                        phone=phone,
                        message_text=_to_plain_text(text),
                        role="assistant",
                        chat_id=chat_id,
                        message_id=int(prefer_message_id),
                    )
                except Exception:
                    pass
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
    if (
        persist
        and session is not None
        and isinstance(user_id, int)
        and user_id > 0
    ):
        try:
            await DialogMessage.create(
                session,
                user_id=user_id,
                username=username,
                full_name=full_name,
                phone=phone,
                message_text=_to_plain_text(text),
                role="assistant",
                chat_id=chat_id,
                message_id=int(sent.message_id),
            )
        except Exception:
            pass
    await state.update_data(
        **{UI_MESSAGE_ID_KEY: int(sent.message_id), UI_MODE_KEY: "send"}
    )


async def ui_send_persistent(
    *,
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str | None = "HTML",
    delete_transient: bool = True,
    # Optional: persist message to admin "conversation" history (DialogMessage)
    persist: bool = False,
    session: Optional[AsyncSession] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
    phone: Optional[str] = None,
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
    sent = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )

    if (
        persist
        and session is not None
        and isinstance(user_id, int)
        and user_id > 0
    ):
        raw = _to_plain_text(text)
        try:
            await DialogMessage.create(
                session,
                user_id=user_id,
                username=username,
                full_name=full_name,
                phone=phone,
                message_text=raw,
                role="assistant",
                chat_id=chat_id,
                message_id=int(sent.message_id),
            )
        except Exception:
            pass
    # Clear transient tracking so future UI updates won't target the persistent message.
    await state.update_data(
        **{UI_MESSAGE_ID_KEY: 0, UI_MODE_KEY: "persistent"}
    )
