from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dialog_message import DialogMessage
from src.models.lead_ticket import LeadTicket
from src.models.staff import StaffMember
from src.services.staff_service import is_admin, is_staff, touch_staff_profile
from src.utils.keyboards import (
    lead_chat_active_keyboard,
    lead_chat_request_keyboard,
    services_keyboard,
    staff_chat_active_keyboard,
    staff_ticket_keyboard,
)


router = Router()


class StaffChat(StatesGroup):
    active = State()  # staff is chatting with lead for a ticket_id


class LeadSupportChat(StatesGroup):
    active = State()  # lead is chatting with staff for a ticket_id


def _fmt_user(from_user) -> str:
    name = getattr(from_user, "full_name", None) or ""
    username = getattr(from_user, "username", None) or ""
    if username:
        return f"{name} (@{username})".strip()
    return name.strip() or "Пользователь"


@router.callback_query(F.data.startswith("staff:ticket:claim:"))
async def staff_claim_ticket(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_staff(session, callback.from_user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    try:
        await touch_staff_profile(
            session,
            tg_user_id=callback.from_user.id,
            tg_username=callback.from_user.username,
            tg_full_name=callback.from_user.full_name,
        )
    except Exception:
        pass

    raw = (callback.data or "").split("staff:ticket:claim:", 1)[-1].strip()
    try:
        ticket_id = int(raw)
    except ValueError:
        await callback.answer()
        return
    ticket = await LeadTicket.get_by_id(session, ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден.", show_alert=True)
        return
    if ticket.assigned_to_tg_user_id and ticket.assigned_to_tg_user_id != callback.from_user.id:
        await callback.answer("Лид уже закреплён за другим менеджером.", show_alert=True)
        return
    ticket.assigned_to_tg_user_id = callback.from_user.id
    ticket.status = "open"
    ticket.updated_at = datetime.utcnow()
    await callback.answer("Закреплено за вами.")
    try:
        await callback.message.edit_reply_markup(reply_markup=staff_ticket_keyboard(ticket_id))
    except Exception:
        pass


@router.callback_query(F.data.startswith("staff:ticket:request_chat:"))
async def staff_request_chat(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_staff(session, callback.from_user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    raw = (callback.data or "").split("staff:ticket:request_chat:", 1)[-1].strip()
    try:
        ticket_id = int(raw)
    except ValueError:
        await callback.answer()
        return
    ticket = await LeadTicket.get_by_id(session, ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден.", show_alert=True)
        return

    # Auto-assign to requester if free
    if ticket.assigned_to_tg_user_id is None:
        ticket.assigned_to_tg_user_id = callback.from_user.id
    if ticket.assigned_to_tg_user_id != callback.from_user.id:
        await callback.answer("Лид закреплён за другим менеджером.", show_alert=True)
        return

    ticket.status = "open"
    ticket.updated_at = datetime.utcnow()

    lead_text = (
        "Чтобы менеджер подключился и уточнил детали, подтвердите консультацию:\n\n"
        "Нажмите «✅ Да, хочу консультацию» — и вы сможете писать менеджеру прямо здесь."
    )
    try:
        await callback.message.bot.send_message(
            chat_id=ticket.lead_chat_id,
            text=lead_text,
            reply_markup=lead_chat_request_keyboard(ticket_id),
        )
    except Exception:
        await callback.answer("Не удалось отправить сообщение лиду.", show_alert=True)
        return

    await callback.answer("Запрос отправлен лиду.")


@router.callback_query(F.data.startswith("lead:chat:accept:"))
async def lead_accept_chat(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    raw = (callback.data or "").split("lead:chat:accept:", 1)[-1].strip()
    try:
        ticket_id = int(raw)
    except ValueError:
        await callback.answer()
        return
    ticket = await LeadTicket.get_by_id(session, ticket_id)
    if not ticket or ticket.lead_user_id != callback.from_user.id:
        await callback.answer("Тикет не найден.", show_alert=True)
        return
    if not ticket.assigned_to_tg_user_id:
        await callback.answer("Менеджер ещё не назначен. Попробуйте чуть позже.", show_alert=True)
        return

    ticket.chat_enabled = 1
    ticket.updated_at = datetime.utcnow()

    await state.set_state(LeadSupportChat.active)
    await state.update_data(ticket_id=ticket_id)

    await callback.message.answer(
        "Менеджер подключился. Напишите сообщение — я передам его.\n\n"
        "Чтобы вернуться к услугам, нажмите «🚪 Выйти из чата».",
        reply_markup=lead_chat_active_keyboard(ticket_id),
    )
    await callback.answer()

    # Notify staff
    try:
        await callback.message.bot.send_message(
            chat_id=ticket.assigned_to_tg_user_id,
            text=f"Лид подтвердил консультацию. Можно писать в чат (тикет #{ticket_id}).",
            reply_markup=staff_ticket_keyboard(ticket_id),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("lead:chat:decline:"))
async def lead_decline_chat(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = (callback.data or "").split("lead:chat:decline:", 1)[-1].strip()
    try:
        ticket_id = int(raw)
    except ValueError:
        await callback.answer()
        return
    ticket = await LeadTicket.get_by_id(session, ticket_id)
    if not ticket or ticket.lead_user_id != callback.from_user.id:
        await callback.answer()
        return
    ticket.chat_enabled = 0
    ticket.updated_at = datetime.utcnow()
    await callback.answer("Ок.")
    try:
        await callback.message.edit_text("Хорошо. Если захотите консультацию позже — просто оставьте заявку ещё раз.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("lead:chat:exit:"))
async def lead_exit_chat(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Вы вышли из чата.")


@router.message(LeadSupportChat.active)
async def lead_forward_to_staff(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if not text:
        return
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not isinstance(ticket_id, int):
        return
    ticket = await LeadTicket.get_by_id(session, ticket_id)
    if not ticket or not ticket.assigned_to_tg_user_id or ticket.chat_enabled != 1:
        await state.clear()
        try:
            await message.answer(
                "Чат с менеджером сейчас недоступен. Вернёмся в меню.",
                reply_markup=services_keyboard(),
            )
        except Exception:
            pass
        return

    # Log lead message
    try:
        await DialogMessage.create(
            session,
            user_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            phone=None,
            message_text=f"[lead_chat #{ticket_id}] {text}",
            role="user",
            chat_id=message.chat.id,
            message_id=message.message_id,
        )
    except Exception:
        pass

    staff_text = f"Сообщение от лида (тикет #{ticket_id}):\n\n{text}"
    try:
        await message.bot.send_message(
            chat_id=ticket.assigned_to_tg_user_id,
            text=staff_text,
            reply_markup=staff_ticket_keyboard(ticket_id),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("staff:ticket:open:"))
async def staff_open_chat(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_staff(session, callback.from_user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    raw = (callback.data or "").split("staff:ticket:open:", 1)[-1].strip()
    try:
        ticket_id = int(raw)
    except ValueError:
        await callback.answer()
        return
    ticket = await LeadTicket.get_by_id(session, ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден.", show_alert=True)
        return
    if ticket.assigned_to_tg_user_id and ticket.assigned_to_tg_user_id != callback.from_user.id:
        await callback.answer("Лид закреплён за другим менеджером.", show_alert=True)
        return
    if ticket.assigned_to_tg_user_id is None:
        ticket.assigned_to_tg_user_id = callback.from_user.id
    ticket.status = "open"
    ticket.updated_at = datetime.utcnow()

    await state.set_state(StaffChat.active)
    await state.update_data(ticket_id=ticket_id)

    lead_label = ticket.lead_full_name or f"User {ticket.lead_user_id}"
    phone = f"\nТелефон: {ticket.lead_phone}" if ticket.lead_phone else ""
    await callback.message.answer(
        f"Вы в чате с лидом (тикет #{ticket_id}).\n"
        f"{lead_label}{phone}\n\n"
        "Напишите сообщение — я отправлю его лиду.",
        reply_markup=staff_chat_active_keyboard(ticket_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("staff:ticket:close:"))
async def staff_close_ticket(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await is_staff(session, callback.from_user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    raw = (callback.data or "").split("staff:ticket:close:", 1)[-1].strip()
    try:
        ticket_id = int(raw)
    except ValueError:
        await callback.answer()
        return
    ticket = await LeadTicket.get_by_id(session, ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден.", show_alert=True)
        return
    if ticket.assigned_to_tg_user_id and ticket.assigned_to_tg_user_id != callback.from_user.id:
        if not await is_admin(session, callback.from_user.id):
            await callback.answer("Лид закреплён за другим менеджером.", show_alert=True)
            return

    ticket.status = "closed"
    ticket.chat_enabled = 0
    ticket.updated_at = datetime.utcnow()
    await state.clear()
    await callback.answer("Тикет закрыт.")
    try:
        await callback.message.answer(f"Тикет #{ticket_id} закрыт.")
    except Exception:
        pass
    # Inform lead (best-effort)
    try:
        await callback.message.bot.send_message(
            chat_id=ticket.lead_chat_id,
            text="Консультация закрыта. Если появятся новые вопросы — нажмите /start и выберите услугу.",
            reply_markup=services_keyboard(),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("staff:ticket:transfer:"))
async def staff_transfer_ticket(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Передавать лиды может только admin.", show_alert=True)
        return
    raw = (callback.data or "").split("staff:ticket:transfer:", 1)[-1].strip()
    try:
        ticket_id = int(raw)
    except ValueError:
        await callback.answer()
        return
    ticket = await LeadTicket.get_by_id(session, ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден.", show_alert=True)
        return

    res = await session.execute(select(StaffMember).where(StaffMember.role == "manager").order_by(StaffMember.created_at.desc()))
    managers = list(res.scalars().all())
    if not managers:
        await callback.answer("Нет менеджеров в staff.", show_alert=True)
        return

    buttons = []
    for m in managers[:20]:
        label = m.tg_full_name or (f"@{m.tg_username}" if m.tg_username else str(m.tg_user_id))
        buttons.append(
            [
                InlineKeyboardButton(
                    text=label[:40],
                    callback_data=f"staff:ticket:transfer_to:{ticket_id}:{int(m.tg_user_id)}",
                )
            ]
        )
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer(f"Кому передать тикет #{ticket_id}?", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("staff:ticket:transfer_to:"))
async def staff_transfer_to(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    raw = (callback.data or "").split("staff:ticket:transfer_to:", 1)[-1].strip()
    parts = raw.split(":")
    if len(parts) != 2:
        await callback.answer()
        return
    try:
        ticket_id = int(parts[0])
        to_tg = int(parts[1])
    except ValueError:
        await callback.answer()
        return

    ticket = await LeadTicket.get_by_id(session, ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден.", show_alert=True)
        return
    prev = ticket.assigned_to_tg_user_id
    ticket.assigned_to_tg_user_id = to_tg
    ticket.status = "open"
    ticket.updated_at = datetime.utcnow()
    await callback.answer("Передано.")

    # Notify new manager
    try:
        await callback.message.bot.send_message(
            chat_id=to_tg,
            text=f"Вам передан лид (тикет #{ticket_id}).",
            reply_markup=staff_ticket_keyboard(ticket_id),
        )
    except Exception:
        pass
    # Notify previous manager (best-effort)
    if prev and prev != to_tg:
        try:
            await callback.message.bot.send_message(
                chat_id=prev,
                text=f"Тикет #{ticket_id} передан другому менеджеру.",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("staff:chat:exit:"))
async def staff_exit_chat(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Вы вышли из чата.")


@router.message(StaffChat.active)
async def staff_forward_to_lead(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if not text:
        return
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not isinstance(ticket_id, int):
        return
    ticket = await LeadTicket.get_by_id(session, ticket_id)
    if not ticket or ticket.assigned_to_tg_user_id != message.from_user.id:
        return

    # Log staff message
    try:
        await DialogMessage.create(
            session,
            user_id=ticket.lead_user_id,
            username=ticket.lead_username,
            full_name=ticket.lead_full_name,
            phone=ticket.lead_phone,
            message_text=f"[staff_chat #{ticket_id}] {_fmt_user(message.from_user)}: {text}",
            role="staff",
            chat_id=ticket.lead_chat_id,
            message_id=None,
        )
    except Exception:
        pass

    if ticket.chat_enabled != 1:
        await message.answer(
            "Лид ещё не подтвердил консультацию/чат. Нажмите «Запросить чат» в карточке лида.",
            reply_markup=staff_ticket_keyboard(ticket_id),
        )
        return

    try:
        await message.bot.send_message(
            chat_id=ticket.lead_chat_id,
            text=f"Сообщение от менеджера:\n\n{text}",
        )
    except Exception:
        await message.answer("Не удалось доставить сообщение лиду.")


