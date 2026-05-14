"""add notes and filename to rubrics

Revision ID: 20260512002
Revises: 20260512001
Create Date: 2026-05-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260512002"
down_revision: Union[str, Sequence[str], None] = "20260512001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rubrics", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("rubrics", sa.Column("filename", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("rubrics", "filename")
    op.drop_column("rubrics", "notes")
