from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref

from app.database.base import Base


class SessionSummary(Base):
    """
    Derived conversational memory summary for a session.
    Encapsulates incremental summarization state, message watermarks,
    and optimistic concurrency versioning.
    """
    __tablename__ = "session_summaries"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    summary_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    message_watermark_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    message_count_summarized: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    session = relationship(
        "Session",
        backref=backref("summary", uselist=False, cascade="all, delete", passive_deletes=True),
    )
    project = relationship("Project")

