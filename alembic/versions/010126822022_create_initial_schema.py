"""create_initial_schema

Revision ID: 010126822022
Revises: 
Create Date: 2026-03-28 20:51:39.507161

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '010126822022'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("github_username", sa.String(), nullable=True),
        sa.Column("github_pat_hash", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "rubrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("total_points", sa.Integer(), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("instructor_id", sa.Uuid(), nullable=False),
        sa.Column("test_suite_repo_url", sa.String(), nullable=True),
        sa.Column("rubric_id", sa.Uuid(), nullable=True),
        sa.Column("enable_lint_review", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("language_override", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["instructor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["rubric_id"], ["rubrics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=True),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("github_repo_url", sa.String(), nullable=False),
        sa.Column("commit_hash", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default='Pending', nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("deterministic_score", sa.Float(), nullable=True),
        sa.Column("ai_feedback_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id"),
    )


def downgrade() -> None:
    op.drop_table("evaluation_results")
    op.drop_table("submissions")
    op.drop_table("assignments")
    op.drop_table("rubrics")
    op.drop_table("users")
