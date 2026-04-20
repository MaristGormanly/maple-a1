import uuid
from datetime import datetime

from sqlalchemy import Float, JSON, ForeignKey, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id"), unique=True, nullable=False
    )
    deterministic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_feedback_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review_status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    instructor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    submission = relationship("Submission", back_populates="evaluation_result")
