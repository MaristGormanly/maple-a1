"""add student_name to submissions

Revision ID: 20260506001
Revises: 20260505001_add_cascade_delete
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = '20260506001'
down_revision = '20260505001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('submissions', sa.Column('student_name', sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column('submissions', 'student_name')
