from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class EvaluationRun(Base):
    """
    Persistent record of a benchmark evaluation run.
    Encapsulates dataset version signature, execution mode, summary metrics,
    and tenancy boundaries.
    """
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
    )

    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    suite_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    dataset_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    dataset_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    dataset_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    execution_mode: Mapped[str] = mapped_column(
        String(20),
        default="regression",
        nullable=False,
    )

    model_name: Mapped[str] = mapped_column(
        String(64),
        default="deterministic-test-provider",
        nullable=False,
    )

    metric_schema_version: Mapped[str] = mapped_column(
        String(16),
        default="1.0.0",
        nullable=False,
    )

    target_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
    )

    is_baseline: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    total_cases: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    passed_cases: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    failed_cases: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    duration_ms: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    summary_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    case_results: Mapped[List["EvaluationCaseResult"]] = relationship(
        "EvaluationCaseResult",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="EvaluationCaseResult.id",
    )


class EvaluationCaseResult(Base):
    """
    Granular result for a single evaluation case within a run.
    """
    __tablename__ = "evaluation_case_results"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True,
    )

    run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    case_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    duration_ms: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    failure_reason: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    run: Mapped["EvaluationRun"] = relationship(
        "EvaluationRun",
        back_populates="case_results",
    )
