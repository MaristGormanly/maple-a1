"""add override_grades and student_comment to evaluation_results

Revision ID: 20260507001
Revises: 20260506001
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = '20260507001'
down_revision = '20260506001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('evaluation_results', sa.Column('override_grades', sa.JSON, nullable=True))
    op.add_column('evaluation_results', sa.Column('student_comment', sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column('evaluation_results', 'student_comment')
    op.drop_column('evaluation_results', 'override_grades')
