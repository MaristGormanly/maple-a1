"""add detected_language to assignments

Revision ID: 20260512001
Revises: 20260510001
Create Date: 2026-05-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260512001"
down_revision: Union[str, Sequence[str], None] = "20260510001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assignments",
        sa.Column("detected_language", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assignments", "detected_language")
