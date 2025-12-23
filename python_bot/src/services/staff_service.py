from __future__ import annotations

from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.staff import StaffMember


async def bootstrap_staff(session: AsyncSession) -> None:
    """Seed initial admins from env ADMIN_USER_IDS (idempotent)."""
    admin_ids = settings.admin_user_ids_list
    if not admin_ids:
        return
    existing = await session.execute(
        select(StaffMember.tg_user_id).where(
            StaffMember.role == "admin", StaffMember.tg_user_id.in_(admin_ids)
        )
    )
    existing_ids = set(int(x) for x in existing.scalars().all())
    for tg_id in admin_ids:
        if tg_id in existing_ids:
            continue
        session.add(StaffMember(tg_user_id=tg_id, role="admin"))
    await session.commit()


async def is_admin(session: AsyncSession, tg_user_id: int) -> bool:
    q = select(StaffMember.id).where(
        StaffMember.tg_user_id == tg_user_id, StaffMember.role == "admin"
    )
    res = await session.execute(q)
    return res.scalar_one_or_none() is not None


async def list_staff(session: AsyncSession) -> List[StaffMember]:
    res = await session.execute(select(StaffMember).order_by(StaffMember.created_at.desc()))
    return list(res.scalars().all())


async def add_staff(session: AsyncSession, tg_user_id: int, role: str) -> StaffMember:
    member = StaffMember(tg_user_id=tg_user_id, role=role)
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member


async def remove_staff(session: AsyncSession, tg_user_id: int, role: Optional[str] = None) -> int:
    stmt = delete(StaffMember).where(StaffMember.tg_user_id == tg_user_id)
    if role:
        stmt = stmt.where(StaffMember.role == role)
    res = await session.execute(stmt)
    await session.commit()
    return int(res.rowcount or 0)


