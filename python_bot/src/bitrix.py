from __future__ import annotations

import re
from typing import Any, Dict, Optional

import httpx

from src.config import BITRIX_ROUTING, SERVICES, settings
from src.logger import logger


class BitrixClient:
    def __init__(self) -> None:
        self.base_url = (settings.bitrix24_webhook_url or "").strip()

    def _lead_add_endpoint(self) -> str:
        url = self.base_url.rstrip("/")
        if not url:
            return ""
        if "crm.lead.add" in url:
            return url
        return f"{url}/crm.lead.add"

    async def create_lead(
        self,
        *,
        full_name: str,
        phone: str,
        service_key: str,
        comment: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        endpoint = self._lead_add_endpoint()
        if not endpoint:
            return {"success": False, "error": "bitrix_webhook_not_configured"}

        routing = BITRIX_ROUTING.get(service_key, {})
        service_name_raw = SERVICES.get(service_key, service_key)
        service_name = re.sub(r"[^\w\s\-()А-Яа-яA-Za-z]", "", service_name_raw).strip()

        name_parts = (full_name or "").strip().split()
        last_name = name_parts[0] if len(name_parts) >= 1 else ""
        first_name = name_parts[1] if len(name_parts) >= 2 else ""

        fields: Dict[str, Any] = {
            "TITLE": f"SRVT Bot — {service_name}",
            "NAME": first_name,
            "LAST_NAME": last_name,
            "PHONE": [{"VALUE": phone, "VALUE_TYPE": "WORK"}] if phone else [],
            "COMMENTS": self._format_comment(service_key, comment, user_id, username),
        }

        # Optional routing
        assigned_by_id = routing.get("assigned_by_id", settings.bitrix_responsible_default_id)
        if isinstance(assigned_by_id, int):
            fields["ASSIGNED_BY_ID"] = assigned_by_id

        category_id = routing.get("category_id", settings.bitrix_default_category_id)
        if isinstance(category_id, int):
            fields["CATEGORY_ID"] = category_id

        # Optional UF fields
        if user_id is not None and settings.bitrix_uf_tg_id:
            fields[settings.bitrix_uf_tg_id] = str(user_id)
        if username and settings.bitrix_uf_tg_username:
            fields[settings.bitrix_uf_tg_username] = username
        if settings.bitrix_uf_service_key:
            fields[settings.bitrix_uf_service_key] = service_key

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(endpoint, json={"fields": fields})
                payload = resp.json()
            if resp.status_code == 200 and payload.get("result"):
                return {"success": True, "lead_id": int(payload["result"])}
            error_msg = payload.get("error_description") or payload.get("error") or f"HTTP_{resp.status_code}"
            logger.error("bitrix_lead_create_failed", error=error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            logger.error("bitrix_lead_create_exception", error=str(e))
            return {"success": False, "error": str(e)}

    def _format_comment(
        self,
        service_key: str,
        comment: str,
        user_id: Optional[int],
        username: Optional[str],
    ) -> str:
        service_name = SERVICES.get(service_key, service_key)
        parts = [
            "Источник: Telegram бот SRVT",
            f"Услуга: {service_name}",
        ]
        if user_id is not None:
            parts.append(f"Telegram ID: {user_id}")
        if username:
            parts.append(f"Telegram username: @{username}")

        if comment and comment.strip():
            parts.append("\n" + "=" * 40)
            parts.append("РЕЗЮМЕ ЗАПРОСА")
            parts.append("=" * 40)
            parts.append(comment.strip())

        return "\n".join(parts)


