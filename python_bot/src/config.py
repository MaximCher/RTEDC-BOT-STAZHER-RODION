from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, Field, field_validator  # type: ignore
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore

# NOTE: Local IDE/pyright may not have third-party stubs installed.
# In production (Docker) these deps are installed, so we silence only
# the editor warnings for this file.
# pyright: reportMissingImports=false, reportMissingModuleSource=false


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: str = Field(
        ...,
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "BOT_TOKEN"),
    )
    telegram_bot_username: str = Field("", alias="TELEGRAM_BOT_USERNAME")
    manager_chat_ids: str = Field(
        "",
        validation_alias=AliasChoices("MANAGER_CHAT_IDS", "CHAT_ID"),
    )
    main_group_id: int = Field(
        0,
        validation_alias=AliasChoices(
            "MAIN_GROUP_ID",
        ),
    )

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

    # Uniteller платежи
    uniteller_enabled: bool = Field(False, alias="UNITELLER_ENABLED")
    uniteller_upid: str = Field("", alias="UNITELLER_UPID")
    uniteller_password: str = Field("", alias="UNITELLER_PASSWORD")
    uniteller_api_url: str = Field(
        "https://api.uniteller.ru/simple/register", alias="UNITELLER_API_URL"
    )
    uniteller_results_url: str = Field(
        "https://wpay.uniteller.ru/results/", alias="UNITELLER_RESULTS_URL"
    )
    uniteller_login: str = Field("", alias="UNITELLER_LOGIN")
    uniteller_results_format: str = Field(
        "4", alias="UNITELLER_RESULTS_FORMAT"
    )
    uniteller_order_lifetime: str = Field("", alias="UNITELLER_ORDER_LIFETIME")
    uniteller_form_lifetime: str = Field("", alias="UNITELLER_FORM_LIFETIME")
    uniteller_currency: str = Field("RUB", alias="UNITELLER_CURRENCY")
    consultation_price_rub: Optional[Decimal] = Field(
        default=None, alias="CONSULTATION_PRICE_RUB"
    )

    # App
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    debug_mode: bool = Field(False, alias="DEBUG_MODE")

    # Admin panel
    admin_password: str = Field(
        "ChangeThisPassword123!",
        validation_alias=AliasChoices("ADMIN_PASSWORD", "DASHBOARD_PASSWORD"),
    )
    web_session_secret: str = Field(
        "ChangeThisSecretKey123!", alias="WEB_SESSION_SECRET"
    )  # used to sign admin sessions
    web_host: str = Field("0.0.0.0", alias="WEB_HOST")
    web_port: int = Field(8000, alias="WEB_PORT")
    webapp_public_url: str = Field(
        "https://example.com/admin", alias="WEBAPP_PUBLIC_URL"
    )
    admin_user_ids: str = Field(
        "",
        validation_alias=AliasChoices("ADMIN_USER_IDS", "ADMIN_IDS"),
    )

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

    @field_validator("consultation_price_rub", mode="before")
    @classmethod
    def _price_empty_str_to_none(cls, v: Any) -> Any:
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
            # Accept common sync DSN formats and convert to async dialect.
            if raw.startswith("postgresql://"):
                return "postgresql+asyncpg://" + raw[len("postgresql://") :]
            if raw.startswith("postgres://"):
                return "postgresql+asyncpg://" + raw[len("postgres://") :]
            return raw

        user = self.postgres_user
        pwd = self.postgres_password
        return (
            "postgresql+asyncpg://"
            f"{user}:{pwd}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()

# ============================================================
# SRVT services (main menu)
# ============================================================

ServiceKey = str

SERVICES: Dict[ServiceKey, str] = {
    "subsidies_financing": "💰 Субсидии и льготное финансирование",
    "logistics_ved": "🚚 Логистика и ВЭД",
    "international_payments": "💸 Международные транзакции/платежи",
    "analytics_tnved": "🔎 Аналитика и ТН ВЭД",
    "club_partnership": "🤝 Клуб экспортёров и партнёрство",
}

SERVICE_FLOWS: Dict[ServiceKey, Dict[str, Any]] = {
    "subsidies_financing": {
        "direction_label": "Субсидии и финансирование",
        "description": (
            "💰 Подберём меры господдержки и льготное финансирование "
            "под ваш кейс.\n"
            "Отвечайте коротко — оформим заявку на консультацию и передадим "
            "кейс эксперту."
        ),
        "questions": [
            "1) ИНН вашей компании (10 или 12 цифр)",
            (
                "2) Коротко опишите задачу (что финансируем/компенсируем, "
                "сумма, сроки — 1–2 фразы)"
            ),
        ],
        "final_text": (
            "Спасибо! Я зафиксировал вводные по субсидиям/финансированию."
        ),
    },
    "logistics_ved": {
        "direction_label": "Логистика и ВЭД",
        "description": (
            "🚚 Поможем выстроить международную логистику и закрыть вопросы "
            "ВЭД: "
            "маршруты, таможня, документы, риски.\n"
            "Ответьте на несколько вопросов — оформим заявку на консультацию."
        ),
        "questions": [
            "1) ИНН вашей компании (10 или 12 цифр)",
            (
                "2) Коротко опишите задачу (маршрут, груз, объёмы, сроки — "
                "1–2 фразы)"
            ),
        ],
        "final_text": "Спасибо! Зафиксировал вводные по логистике и ВЭД.",
    },
    "international_payments": {
        "direction_label": "Международные платежи",
        "description": (
            "💸 Поможем провести безопасный международный платёж и снизить "
            "риски блокировок/комплаенса.\n"
            "Ответьте на несколько вопросов — оформим заявку на консультацию."
        ),
        "questions": [
            "1) ИНН вашей компании (10 или 12 цифр)",
            (
                "2) Коротко опишите задачу (страны, сумма/валюта, "
                "назначение — "
                "1–2 фразы)"
            ),
        ],
        "final_text": (
            "Спасибо! Я зафиксировал вводные по международным платежам."
        ),
    },
    "analytics_tnved": {
        "direction_label": "Аналитика и ТН ВЭД",
        "description": (
            "🔎 Поможем с аналитикой ВЭД: подбор кода ТН ВЭД, "
            "пошлины/ограничения, "
            "требования и сертификация.\n"
            "Ответьте на вопросы — оформим заявку на консультацию."
        ),
        "questions": [
            "1) ИНН вашей компании (10 или 12 цифр)",
            "2) Коротко опишите задачу (товар/страна/что нужно — 1–2 фразы)",
        ],
        "final_text": "Спасибо! Зафиксировал вводные по аналитике и ТН ВЭД.",
    },
    "club_partnership": {
        "direction_label": "Клуб и партнёрство",
        "description": (
            "🤝 Клуб экспортёров и партнёрство: доступ к экспертам, контактам "
            "и практикам ВЭД.\n"
            "Ответьте на вопросы — оформим заявку на консультацию."
        ),
        "questions": [
            "1) ИНН вашей компании (10 или 12 цифр)",
            (
                "2) Коротко опишите задачу/интерес (клуб, партнёрство, "
                "что хотите получить — 1–2 фразы)"
            ),
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
        "Помогаю по субсидиям, логистике и ВЭД, международным платежам "
        "и аналитике.\n\n"
        "Выберите направление ниже 👇"
    ),
    "choose_service": "Пожалуйста, выберите направление:",
    "back_to_menu": "Вы вернулись в меню. Выберите направление ниже 👇",
    "unknown_service": (
        "Не удалось определить направление. Попробуйте ещё раз через меню."
    ),
    "questionnaire_done": (
        "Заявка завершена. Спасибо! Если хотите — передам кейс эксперту, "
        "нажмите кнопку ниже."
    ),
    "lead_inn_request": (
        "Укажите ИНН вашей компании (10 или 12 цифр, без пробелов)."
    ),
    "lead_contact_request": (
        "Оставьте, пожалуйста, ФИО и телефон (можно одной строкой):\n\n"
        "Иванов Иван +79991234567"
    ),
    "lead_meeting_window_request": (
        "Спасибо! Теперь подскажите удобное время для встречи/созвона (МСК).\n"
        "Например: «завтра 14:00–18:00» или «в будни после 19:00».\n\n"
        "Можно выбрать кнопкой ниже или написать вручную. "
        "Если не важно — напишите: «не важно»."
    ),
    "lead_received": (
        "Спасибо! Заявка принята ✅\n"
        "Персональный менеджер SRVT свяжется с вами в ближайшее время "
        "(в рабочее время)."
    ),
    "lead_payment_prompt": (
        "Для отправки заявки нужна оплата консультации. "
        "Оплатите, пожалуйста, по кнопке ниже."
    ),
    "lead_payment_pending": (
        "Оплата пока не подтверждена. Обычно это занимает 1–2 минуты."
    ),
    "lead_payment_error": (
        "Не удалось сформировать ссылку на оплату. "
        "Попробуйте позже или напишите менеджеру."
    ),
    "lead_payment_received": (
        "Оплата подтверждена ✅\n" "Заявка передана менеджеру."
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
        "Я всё равно могу передать вводные менеджеру SRVT — он подберёт "
        "программу и рассчитает точно."
    ),
}
