from __future__ import annotations

from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.config import SERVICES, settings
from src.logger import logger


SRVT_SYSTEM_PROMPT = """
Ты — SRVT Assistant, деловой AI-консультант по внешнеэкономической деятельности.

Задача:
- Помочь предпринимателю уточнить вводные, дать предварительные рекомендации и привести к передаче кейса эксперту.
- Используй предоставленные выдержки из базы знаний, если они есть. Не выдумывай факты.

Правила:
- Пиши по-русски, коротко и структурировано (3–6 буллетов максимум).
- Если информации недостаточно — задай 1–2 уточняющих вопроса.
- Не обещай гарантированный результат/выплату/одобрение.
- Нельзя писать «мы уже передали кейс» — передача происходит после оставления контакта.
""".strip()

SUBSIDY_SYSTEM_PROMPT = """
Ты — SRVT Assistant, эксперт по субсидиям/грантам/мерам господдержки.

Ключевое:
- Используй ТОЛЬКО факты из предоставленных выдержек базы знаний. Если факта нет — так и скажи.
- Если в контексте есть проценты компенсации и лимиты (например «до 80%», «до 300 000 000 руб») — можно сделать предварительную оценку суммы, но всегда с дисклеймером.
- Если используешь формулировки «до X%» или «лимит» — объясни простыми словами, что это значит, и приведи короткий пример по формуле: min(расходы × %, лимит).
- Структура ответа:
  1) Коротко: что может подойти из мер поддержки (1–3 пункта)
  2) Предварительная оценка (если есть бюджет клиента и условия из контекста)
  3) Что нужно подготовить (документы/условия — только если упомянуто в контексте)
  4) 1–2 уточняющих вопроса (регион, экспорт, сумма, тип затрат) — если данных мало

Запрещено:
- Придумывать «конкурс открыт/закрыт», сроки, суммы, проценты, если их нет в контексте.
- Гарантировать получение субсидии или точную сумму.
""".strip()


LEAD_SUMMARY_PROMPT = """
Ты — помощник SRVT. Сгенерируй короткое резюме заявки для менеджера.
Формат: 6–10 строк, без воды, только факты. Укажи:
- Что хочет клиент (суть)
- Суммы/сроки/страны (если были)
- Риски/узкие места
- Какие действия предложить первым шагом
""".strip()


class AIAgent:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            self.client: Optional[AsyncOpenAI] = None
        else:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate_answer(
        self,
        *,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        vector_context: Optional[str] = None,
        user_name: Optional[str] = None,
        selected_service: Optional[str] = None,
    ) -> str:
        if not self.client:
            return (
                "Сейчас AI‑модуль временно недоступен. "
                "Нажмите «Передать эксперту», и команда СРВТ свяжется с вами."
            )

        system_prompt = SUBSIDY_SYSTEM_PROMPT if selected_service == "subsidies_financing" else SRVT_SYSTEM_PROMPT
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

        context_parts: List[str] = []
        if user_name:
            context_parts.append(f"Клиент: {user_name}")
        if selected_service:
            context_parts.append(f"Услуга: {SERVICES.get(selected_service, selected_service)}")
        if vector_context:
            context_parts.append(f"KB_CONTEXT:\n{vector_context}")

        if context_parts:
            messages.append({"role": "system", "content": "\n\n".join(context_parts)})

        for msg in conversation_history[-10:]:
            role = msg.get("role")
            content = msg.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_message})

        try:
            resp = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                temperature=0.4,
                max_tokens=700,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error("openai_generate_answer_failed", error=str(e))
            return (
                "Не удалось получить ответ AI из‑за технической ошибки. "
                "Нажмите «Передать эксперту», и мы подключим специалиста."
            )

    async def generate_subsidy_answer(
        self,
        *,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        vector_context: Optional[str] = None,
        calc_estimates: Optional[str] = None,
    ) -> str:
        if not self.client:
            return (
                "Сейчас AI‑модуль временно недоступен. "
                "Нажмите «Передать эксперту», и команда СРВТ свяжется с вами."
            )

        messages: List[Dict[str, str]] = [{"role": "system", "content": SUBSIDY_SYSTEM_PROMPT}]

        system_blocks: List[str] = []
        if vector_context:
            system_blocks.append(f"KB_CONTEXT:\n{vector_context}")
        if calc_estimates:
            system_blocks.append(f"CALC_ESTIMATES:\n{calc_estimates}")
        if system_blocks:
            messages.append({"role": "system", "content": "\n\n".join(system_blocks)})

        for msg in conversation_history[-10:]:
            role = msg.get("role")
            content = msg.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})

        try:
            resp = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                temperature=0.25,
                max_tokens=650,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error("openai_generate_subsidy_failed", error=str(e))
            return (
                "Не удалось получить ответ AI из‑за технической ошибки. "
                "Нажмите «Передать эксперту», и мы подключим специалиста."
            )

    async def summarize_lead(
        self,
        *,
        selected_service: str,
        user_name: str,
        phone: str,
        conversation_history: List[Dict[str, Any]],
    ) -> str:
        if not self.client:
            return f"Заявка: {SERVICES.get(selected_service, selected_service)}. Клиент: {user_name}, контакт: {phone}."

        transcript_lines: List[str] = []
        for msg in conversation_history[-20:]:
            role = msg.get("role")
            content = msg.get("content")
            if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
                prefix = "Клиент" if role == "user" else "SRVT"
                transcript_lines.append(f"{prefix}: {content.strip()}")

        payload = (
            "НОВЫЙ ЛИД ИЗ TELEGRAM\n"
            f"Услуга: {SERVICES.get(selected_service, selected_service)}\n"
            f"Клиент: {user_name}\n"
            f"Контакт: {phone}\n\n"
            "ДИАЛОГ (фрагмент):\n"
            + "\n".join(transcript_lines)
        )

        try:
            resp = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": LEAD_SUMMARY_PROMPT},
                    {"role": "user", "content": payload},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error("openai_summarize_lead_failed", error=str(e))
            return f"Заявка: {SERVICES.get(selected_service, selected_service)}. Клиент: {user_name}, контакт: {phone}."


