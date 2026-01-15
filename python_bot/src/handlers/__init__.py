from aiogram import Router

from src.handlers.analytics import router as analytics_router
from src.handlers.club import router as club_router
from src.handlers.fallback import router as fallback_router
from src.handlers.financing import router as financing_router
from src.handlers.logistics import router as logistics_router
from src.handlers.lead import router as lead_router
from src.handlers.main_menu import router as main_menu_router
from src.handlers.payments import router as payments_router
from src.handlers.quick_audit import router as quick_audit_router
from src.handlers.services import router as services_router
from src.handlers.start import router as start_router
from src.handlers.staff_chat import router as staff_chat_router
from src.handlers.subsidies import router as subsidies_router


def get_routers() -> list[Router]:
    return [
        start_router,
        main_menu_router,
        staff_chat_router,
        services_router,
        lead_router,
        subsidies_router,
        financing_router,
        payments_router,
        logistics_router,
        analytics_router,
        quick_audit_router,
        club_router,
        # Must be the last router (lowest priority).
        fallback_router,
    ]


