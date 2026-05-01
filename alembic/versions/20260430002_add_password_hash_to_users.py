"""add password_hash to users

Adds the missing password_hash column referenced by auth.register and
auth.login. Without this column, both endpoints crash at runtime
(SQLAlchemy rejects the unmapped kwarg in register; AttributeError on
the model attribute access in login).

Nullable=True so existing users (provisioned manually before pilot)
can persist without a hash; a follow-up migration can tighten this
once a password-reset flow exists.

Revision ID: 20260430002
Revises: 20260430001
Create Date: 2026-04-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260430002'
down_revision: Union[str, Sequence[str], None] = '20260430001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('password_hash', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'password_hash')
