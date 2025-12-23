"""baseline

Revision ID: 626bc432486f
Revises:
Create Date: 2025-12-23 13:30:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "626bc432486f"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Baseline revision.

    We keep current startup behavior (SQLAlchemy create_all) for now.
    Later we will replace create_all with real migrations and add an initial
    autogenerate revision against an empty DB for clean deploys.
    """


def downgrade() -> None:
    """No-op baseline."""


