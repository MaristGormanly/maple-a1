"""resize_embedding_vector_add_hnsw

Reduces embedding column from vector(3072) to vector(1536) using OpenAI's
supported dimensions parameter, which fits within pgvector's HNSW index cap
(2000 dims). Adds a cosine-distance HNSW index for fast ANN retrieval.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-18 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop and re-add the column — table is empty at migration time so no data loss.
    op.execute("ALTER TABLE style_guide_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE style_guide_chunks ADD COLUMN embedding vector(1536)")
    op.execute("""
        CREATE INDEX ix_style_guide_chunks_embedding_hnsw
        ON style_guide_chunks
        USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_style_guide_chunks_embedding_hnsw")
    op.execute("ALTER TABLE style_guide_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE style_guide_chunks ADD COLUMN embedding vector(3072)")
