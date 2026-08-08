"""baseline

Revision ID: 3572107a2072
Revises:
Created: 2026-08-08 15:43:15.929751
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "3572107a2072"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
