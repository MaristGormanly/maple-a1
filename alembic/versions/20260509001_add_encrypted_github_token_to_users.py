"""add encrypted github token to users

Revision ID: 20260509001
Revises: 20260507001
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

revision = '20260509001'
down_revision = '20260507001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('github_pat_encrypted', sa.Text(), nullable=True))
    op.add_column(
        'users',
        sa.Column('github_token_updated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'github_token_updated_at')
    op.drop_column('users', 'github_pat_encrypted')
