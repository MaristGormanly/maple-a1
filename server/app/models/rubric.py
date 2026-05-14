import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Integer, JSON, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Rubric(Base):
    __tablename__ = "rubrics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    instructor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    instructor = relationship("User", back_populates="rubrics")
    assignments = relationship("Assignment", back_populates="rubric")
