"""add_cascade_delete

Revision ID: 20260505001
Revises: 010126822022
Create Date: 2026-05-05

"""
from typing import Sequence, Union

from alembic import op


revision: str = '20260505001'
down_revision: Union[str, Sequence[str], None] = '20260430002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('submissions_assignment_id_fkey', 'submissions', type_='foreignkey')
    op.create_foreign_key(
        'submissions_assignment_id_fkey', 'submissions', 'assignments',
        ['assignment_id'], ['id'], ondelete='CASCADE',
    )

    op.drop_constraint('evaluation_results_submission_id_fkey', 'evaluation_results', type_='foreignkey')
    op.create_foreign_key(
        'evaluation_results_submission_id_fkey', 'evaluation_results', 'submissions',
        ['submission_id'], ['id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('evaluation_results_submission_id_fkey', 'evaluation_results', type_='foreignkey')
    op.create_foreign_key(
        'evaluation_results_submission_id_fkey', 'evaluation_results', 'submissions',
        ['submission_id'], ['id'],
    )

    op.drop_constraint('submissions_assignment_id_fkey', 'submissions', type_='foreignkey')
    op.create_foreign_key(
        'submissions_assignment_id_fkey', 'submissions', 'assignments',
        ['assignment_id'], ['id'],
    )
