"""add review_status and instructor_notes to evaluation_results

Revision ID: 20260419001
Revises: 010126822022
Create Date: 2026-04-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260419001'
down_revision: Union[str, Sequence[str], None] = '010126822022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'evaluation_results',
        sa.Column('review_status', sa.String(), nullable=False, server_default='pending'),
    )
    op.add_column(
        'evaluation_results',
        sa.Column('instructor_notes', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('evaluation_results', 'instructor_notes')
    op.drop_column('evaluation_results', 'review_status')
