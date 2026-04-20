import uuid

from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.app.models.database import Base


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String, nullable=False)
    instructor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    test_suite_repo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    rubric_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rubrics.id"), nullable=True
    )
    enable_lint_review: Mapped[bool] = mapped_column(Boolean, default=False)
    language_override: Mapped[str | None] = mapped_column(String, nullable=True)

    instructor = relationship("User", back_populates="assignments")
    rubric = relationship("Rubric", back_populates="assignments")
    submissions = relationship("Submission", back_populates="assignment")
