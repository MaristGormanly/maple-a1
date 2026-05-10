"""add test_discovery_mode to assignments

Revision ID: 20260510001
Revises: 20260509001
Create Date: 2026-05-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260510001"
down_revision: Union[str, Sequence[str], None] = "20260509001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assignments",
        sa.Column(
            "test_discovery_mode",
            sa.String(),
            nullable=False,
            server_default="instructor_suite",
        ),
    )


def downgrade() -> None:
    op.drop_column("assignments", "test_discovery_mode")
