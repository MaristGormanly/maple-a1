"""add instructor account fields and rubric ownership

Revision ID: 20260513001
Revises: 20260512002
Create Date: 2026-05-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260513001"
down_revision: Union[str, Sequence[str], None] = "20260512002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(length=160), nullable=True))
    op.add_column("users", sa.Column("username", sa.String(length=80), nullable=True))
    op.add_column("users", sa.Column("school", sa.String(length=160), nullable=True))
    op.create_unique_constraint("users_username_key", "users", ["username"])

    op.add_column("rubrics", sa.Column("instructor_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "rubrics_instructor_id_fkey",
        "rubrics",
        "users",
        ["instructor_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("assignments_instructor_id_fkey", "assignments", type_="foreignkey")
    op.create_foreign_key(
        "assignments_instructor_id_fkey",
        "assignments",
        "users",
        ["instructor_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("assignments_rubric_id_fkey", "assignments", type_="foreignkey")
    op.create_foreign_key(
        "assignments_rubric_id_fkey",
        "assignments",
        "rubrics",
        ["rubric_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint("submissions_student_id_fkey", "submissions", type_="foreignkey")
    op.create_foreign_key(
        "submissions_student_id_fkey",
        "submissions",
        "users",
        ["student_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute(
        """
        UPDATE rubrics
        SET instructor_id = owner.instructor_id
        FROM (
            SELECT rubric_id, min(instructor_id::text)::uuid AS instructor_id
            FROM assignments
            WHERE rubric_id IS NOT NULL
            GROUP BY rubric_id
        ) AS owner
        WHERE rubrics.id = owner.rubric_id
        """
    )


def downgrade() -> None:
    op.drop_constraint("submissions_student_id_fkey", "submissions", type_="foreignkey")
    op.create_foreign_key(
        "submissions_student_id_fkey",
        "submissions",
        "users",
        ["student_id"],
        ["id"],
    )

    op.drop_constraint("assignments_rubric_id_fkey", "assignments", type_="foreignkey")
    op.create_foreign_key(
        "assignments_rubric_id_fkey",
        "assignments",
        "rubrics",
        ["rubric_id"],
        ["id"],
    )

    op.drop_constraint("assignments_instructor_id_fkey", "assignments", type_="foreignkey")
    op.create_foreign_key(
        "assignments_instructor_id_fkey",
        "assignments",
        "users",
        ["instructor_id"],
        ["id"],
    )

    op.drop_constraint("rubrics_instructor_id_fkey", "rubrics", type_="foreignkey")
    op.drop_column("rubrics", "instructor_id")

    op.drop_constraint("users_username_key", "users", type_="unique")
    op.drop_column("users", "school")
    op.drop_column("users", "username")
    op.drop_column("users", "name")
