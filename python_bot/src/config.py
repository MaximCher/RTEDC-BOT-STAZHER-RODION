from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_bot_username: str = Field("", alias="TELEGRAM_BOT_USERNAME")
    manager_chat_ids: str = Field("", alias="MANAGER_CHAT_IDS")

    # Database
    database_url_override: str = Field("", alias="DATABASE_URL")
    postgres_host: str = Field("db", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    postgres_db: str = Field("srvt_bot", alias="POSTGRES_DB")
    postgres_user: str = Field("srvt", alias="POSTGRES_USER")
    postgres_password: str = Field(..., alias="POSTGRES_PASSWORD")
    postgres_sslmode: str = Field("prefer", alias="POSTGRES_SSLMODE")

    # OpenAI
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")
    embedding_model: str = Field(
        "text-embedding-3-small", alias="EMBEDDING_MODEL"
    )

    # Bitrix
    bitrix24_webhook_url: str = Field("", alias="BITRIX24_WEBHOOK_URL")
    bitrix_responsible_default_id: Optional[int] = Field(
        default=None, alias="BITRIX_RESPONSIBLE_DEFAULT_ID"
    )
    bitrix_default_category_id: Optional[int] = Field(
        default=None, alias="BITRIX_DEFAULT_CATEGORY_ID"
    )
    bitrix_uf_tg_id: str = Field("UF_CRM_TG_ID", alias="BITRIX_UF_TG_ID")
    bitrix_uf_tg_username: str = Field(
        "UF_CRM_TG_USERNAME", alias="BITRIX_UF_TG_USERNAME"
    )
    bitrix_uf_service_key: str = Field(
        "UF_CRM_SRV_SERVICE", alias="BITRIX_UF_SERVICE_KEY"
    )

    # App
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    debug_mode: bool = Field(False, alias="DEBUG_MODE")

    # Admin panel
    admin_password: str = Field(
        "ChangeThisPassword123!", alias="ADMIN_PASSWORD"
    )
    web_session_secret: str = Field(
        "ChangeThisSecretKey123!", alias="WEB_SESSION_SECRET"
    )  # used to sign admin sessions
    web_host: str = Field("0.0.0.0", alias="WEB_HOST")
    web_port: int = Field(8000, alias="WEB_PORT")
    webapp_public_url: str = Field(
        "https://example.com/admin", alias="WEBAPP_PUBLIC_URL"
    )
    admin_user_ids: str = Field("", alias="ADMIN_USER_IDS")

    @field_validator(
        "bitrix_responsible_default_id",
        "bitrix_default_category_id",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @property
    def manager_chat_ids_list(self) -> List[int]:
        raw = (self.manager_chat_ids or "").strip()
        if not raw:
            return []
        result: List[int] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                result.append(int(part))
            except ValueError:
                continue
        return result

    @property
    def admin_user_ids_list(self) -> List[int]:
        raw = (self.admin_user_ids or "").strip()
        if not raw:
            return []
        result: List[int] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                result.append(int(part))
            except ValueError:
                continue
        return result

    @property
    def database_url(self) -> str:
        raw = (self.database_url_override or "").strip()
        if raw:
            # Accept common sync DSN formats and convert to async SQLAlchemy dialect.
            if raw.startswith("postgresql://"):
                return "postgresql+asyncpg://" + raw[len("postgresql://") :]
            if raw.startswith("postgres://"):
                return "postgresql+asyncpg://" + raw[len("postgres://") :]
            return raw

        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()

# ============================================================
# SRVT services (6 directions)
# ============================================================

ServiceKey = str

SERVICES: Dict[ServiceKey, str] = {
    "subsidies_financing": "💰 Субсидии и льготное финансирование",
    "logistics_ved": "🚚 Логистика и ВЭД",
    "international_payments": "💸 Международные транзакции/платежи",
    "analytics_tnved": "🔎 Аналитика и ТН ВЭД",
    "quick_audit_inn": "🧾 Проверка компании по ИНН (quick audit)",
    "club_partnership": "🤝 Клуб экспортёров и партнёрство",
}

SERVICE_FLOWS: Dict[ServiceKey, Dict[str, Any]] = {
    "subsidies_financing": {
        "direction_label": "Субсидии и финансирование",
        "description": (
            "💰 Подберём меры господдержки и льготное финансирование под ваш кейс.\n"
            "Отвечайте коротко — после анкеты можно сразу передать кейс эксперту."
        ),
        "questions": [
            "1) Как вас зовут?",
            "2) Компания/форма: ИП, ООО, самозанятый? (можно: «пока не зарегистрирована»)",
            "3) Регион регистрации/реализации проекта",
            "4) Отрасль/вид деятельности (1–2 фразы)",
            "5) Что финансируем/компенсируем? (оборудование/логистика/сертификация/маркетинг/НИОКР/ФОТ/выставки)",
            "6) Бюджет проекта/расходов (диапазон в ₽)",
            "7) Есть экспорт/план экспорта? Если да — страны",
            "8) Срок: срочно/планово (когда нужны деньги/компенсация)",
            "9) Контакт для связи (телефон/Telegram/почта)",
        ],
        "final_text": "Спасибо! Я зафиксировал вводные по субсидиям/финансированию.",
    },
    "logistics_ved": {
        "direction_label": "Логистика и ВЭД",
        "description": (
            "🚚 Поможем выстроить международную логистику и закрыть вопросы ВЭД: маршруты, таможня, документы, риски.\n"
            "Ответьте на несколько вопросов — соберу заявку для эксперта."
        ),
        "questions": [
            "1) Как вас зовут?",
            "2) Откуда → куда (страны/города)?",
            "3) Тип груза/товара + код ТН ВЭД (если есть)",
            "4) Объём/вес/партии и периодичность",
            "5) Инкотермс (если известно) / кто оплачивает доставку",
            "6) Узкое место: сроки/стоимость/таможня/сертификаты/риски",
            "7) Есть ли готовые контракты/инвойсы? (да/нет/в процессе)",
            "8) Срок запуска поставки",
            "9) Контакт для связи (телефон/Telegram/почта)",
        ],
        "final_text": "Спасибо! Зафиксировал вводные по логистике и ВЭД.",
    },
    "international_payments": {
        "direction_label": "Международные платежи",
        "description": (
            "💸 Поможем провести безопасный международный платёж и снизить риски блокировок/комплаенса.\n"
            "Ответьте на несколько вопросов — соберу заявку."
        ),
        "questions": [
            "1) Как вас зовут?",
            "2) Отправитель/получатель: страна и тип компании",
            "3) Валюта и сумма: разово или регулярно?",
            "4) Назначение платежа (товар/услуга/роялти и т.п.)",
            "5) Были ли блокировки/отказы банков раньше?",
            "6) Нужен валютный контроль/подтверждающие документы? (если знаете)",
            "7) Срок: когда должен пройти платёж",
            "8) Контакт для связи (телефон/Telegram/почта)",
        ],
        "final_text": "Спасибо! Я зафиксировал вводные по международным платежам.",
    },
    "analytics_tnved": {
        "direction_label": "Аналитика и ТН ВЭД",
        "description": (
            "🔎 Поможем с аналитикой ВЭД: подбор кода ТН ВЭД, пошлины/ограничения, требования и сертификация.\n"
            "Ответьте на вопросы — передам эксперту."
        ),
        "questions": [
            "1) Как вас зовут?",
            "2) Товар/услуга (описание) и страна направления",
            "3) Что нужно: код ТН ВЭД / пошлины / запреты / сертификация / маркировка?",
            "4) Объёмы/частота поставок",
            "5) Что уже известно/что хотите выяснить дополнительно",
            "6) Срок и формат результата (справка/отчёт)",
            "7) Контакт для связи (телефон/Telegram/почта)",
        ],
        "final_text": "Спасибо! Зафиксировал вводные по аналитике и ТН ВЭД.",
    },
    "quick_audit_inn": {
        "direction_label": "Проверка по ИНН",
        "description": (
            "🧾 Быстрый аудит контрагента: риски, суды, санкции, репутация.\n"
            "Соберу вводные и передам аналитикам."
        ),
        "questions": [
            "1) Как вас зовут?",
            "2) ИНН компании (или название + страна, если иностранная)",
            "3) Роль компании: поставщик/покупатель/партнёр/перевозчик",
            "4) Сумма/значимость сделки (ориентир)",
            "5) Что проверить в приоритете: финансы/суды/санкции/аффилированность/репутация/бенефициары",
            "6) Срок: когда нужен результат",
            "7) Контакт для связи (телефон/Telegram/почта)",
        ],
        "final_text": "Спасибо! Зафиксировал вводные для quick audit.",
    },
    "club_partnership": {
        "direction_label": "Клуб и партнёрство",
        "description": (
            "🤝 Клуб экспортёров и партнёрство: доступ к экспертам, контактам и практикам ВЭД.\n"
            "Ответьте на вопросы — направлю заявку менеджеру."
        ),
        "questions": [
            "1) Как вас зовут?",
            "2) Компания и отрасль",
            "3) Экспортируете сейчас? (да/нет) Если да — страны",
            "4) Что ищете: партнёры/маршруты/платежи/субсидии/закупки/сообщество",
            "5) Объём/оборот (диапазон, можно «не готов»)",
            "6) Когда актуально: сейчас/в течение месяца/позже",
            "7) Контакт для связи (телефон/Telegram/почта)",
        ],
        "final_text": "Спасибо! Я зафиксировал заявку по клубу/партнёрству.",
    },
}

# ============================================================
# Bitrix routing (defaults; override later with real IDs)
# ============================================================

BITRIX_ROUTING: Dict[ServiceKey, Dict[str, Any]] = {
    key: {
        "category_name": SERVICES[key],
        "assigned_by_id": settings.bitrix_responsible_default_id,
        "category_id": settings.bitrix_default_category_id,
        "tags": ["srvt", key],
    }
    for key in SERVICES.keys()
}

# ============================================================
# Messages (used by handlers)
# ============================================================

MESSAGES: Dict[str, str] = {
    "welcome": (
        "Здравствуйте! Я SRVT Assistant.\n\n"
        "Помогаю по субсидиям, логистике и ВЭД, международным платежам, аналитике и проверке контрагентов.\n\n"
        "Выберите направление ниже 👇"
    ),
    "choose_service": "Пожалуйста, выберите направление:",
    "back_to_menu": "Вы вернулись в меню. Выберите направление 👇",
    "unknown_service": "Не удалось определить направление. Попробуйте ещё раз через меню.",
    "questionnaire_done": "Анкета завершена. Спасибо! Если хотите — передам кейс эксперту, нажмите кнопку ниже.",
    "lead_contact_request": "Оставьте, пожалуйста, ФИО и телефон (можно одной строкой):\n\nИванов Иван +79991234567",
    "lead_meeting_window_request": (
        "Спасибо! Теперь подскажите удобное время для встречи/созвона (МСК).\n"
        "Например: «завтра 14:00–18:00» или «в будни после 19:00».\n\n"
        "Можно выбрать кнопкой ниже или написать вручную. Если не важно — напишите: «не важно»."
    ),
    "lead_received": (
        "Спасибо! Заявка принята ✅\n"
        "Персональный менеджер SRVT свяжется с вами в течение 15 минут (в рабочее время)."
    ),
    "subsidy_calc_intro": (
        "Ок, давайте рассчитаем ориентировочный объём субсидии.\n"
        "Это займёт ~2 минуты. Отвечайте коротко."
    ),
    "subsidy_calc_result_header": (
        "Готово. Предварительная оценка по вашему кейсу:"
    ),
    "subsidy_calc_no_context": (
        "⚠️ В базе знаний не нашёл точные проценты/лимиты под ваш кейс.\n"
        "Я всё равно могу передать вводные менеджеру SRVT — он подберёт программу и рассчитает точно."
    ),
}
