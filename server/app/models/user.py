import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    username: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    school: Mapped[str | None] = mapped_column(String(160), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    github_username: Mapped[str | None] = mapped_column(String, nullable=True)
    github_pat_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    github_pat_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_token_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    assignments = relationship("Assignment", back_populates="instructor")
    rubrics = relationship("Rubric", back_populates="instructor")
    submissions = relationship("Submission", back_populates="student")
