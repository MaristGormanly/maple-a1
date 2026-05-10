"""merge_review_columns_with_pgvector_chain

Merges the two heads that diverged from 010126822022:
  - 20260419001 (review_status + instructor_notes columns)
  - c3d4e5f6a7b8 (pgvector embedding resize + HNSW index)

This is a no-op merge revision; it linearises the migration graph so
`alembic upgrade head` works without a "Multiple head revisions" error.

Revision ID: 20260430001
Revises: 20260419001, c3d4e5f6a7b8
Create Date: 2026-04-30
"""
from typing import Sequence, Union


revision: str = '20260430001'
down_revision: Union[str, Sequence[str], None] = ('20260419001', 'c3d4e5f6a7b8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
