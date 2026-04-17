"""add_style_guide_chunks

Revision ID: b2c3d4e5f6a7
Revises: 010126822022
Create Date: 2026-04-17 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = '010126822022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""
        CREATE TABLE style_guide_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_title TEXT NOT NULL,
            source_url TEXT NOT NULL,
            language TEXT NOT NULL,
            style_guide_version TEXT NOT NULL,
            rule_id TEXT,
            last_fetched TIMESTAMPTZ NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding vector(3072)
        )
    """)
    op.create_index(
        "ix_style_guide_chunks_language",
        "style_guide_chunks",
        ["language"],
    )
    # NOTE: vector(3072) exceeds pgvector HNSW/IVFFlat index cap of 2000 dims.
    # Exact cosine scan is used instead; acceptable at expected row counts
    # (~5 style guides × few hundred rules). Team lead should confirm or amend
    # spec to use dimensions=1536 if ANN index is required.

def downgrade() -> None:
    op.drop_index("ix_style_guide_chunks_language", table_name="style_guide_chunks")
    op.execute("DROP TABLE IF EXISTS style_guide_chunks")
