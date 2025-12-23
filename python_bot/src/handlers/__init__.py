from aiogram import Router

from src.handlers.lead import router as lead_router
from src.handlers.services import router as services_router
from src.handlers.start import router as start_router
from src.handlers.subsidies import router as subsidies_router


def get_routers() -> list[Router]:
    return [start_router, services_router, lead_router, subsidies_router]


