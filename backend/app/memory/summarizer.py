import logging
from typing import Optional
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.developer.logging import scrub_secrets
from app.memory.exceptions import StaleWriteError, WatermarkRegressionError
from app.memory.prompts import build_summarization_prompt
from app.memory.schemas import ContextAssemblerConfig, SummarizationResponse
from app.models.message import Message as MessageModel
from app.models.session_summary import SessionSummary
from app.research.llm.base import LLMProvider

logger = logging.getLogger("orchestra.memory.summarizer")


class SummarizerService:
    """
    Incremental conversation summarizer.
    Compresses messages beyond the sliding window into a durable summary
    with watermark tracking, bounded batch processing, secret scrubbing,
    and optimistic concurrency protection.
    """

    def __init__(
        self,
        db: Session,
        llm_provider: LLMProvider,
        config: Optional[ContextAssemblerConfig] = None,
    ):
        self.db = db
        self.llm_provider = llm_provider
        self.config = config or ContextAssemblerConfig()

    async def maybe_summarize(
        self,
        session_id: int,
        project_id: int,
    ) -> Optional[SessionSummary]:
        """
        Checks if summarization is needed and performs it if triggered.
        Returns the updated SessionSummary or None if no summarization was needed.

        Trigger condition:
            unsummarized candidate count >= config.summarization_threshold (default 30)
        """
        # 1. Fetch current watermark and existing summary row
        summary_row = (
            self.db.query(SessionSummary)
            .filter(SessionSummary.session_id == session_id)
            .first()
        )
        watermark_id = summary_row.message_watermark_id if summary_row else 0
        expected_version = summary_row.version if summary_row else None

        # 2. Anomaly detection: if messages were deleted such that MAX(id) < watermark_id,
        # invalidate the watermark and rebuild from message 0
        max_id = (
            self.db.query(func.max(MessageModel.id))
            .filter(MessageModel.session_id == session_id)
            .scalar()
        )
        if max_id is not None and max_id < watermark_id:
            logger.warning(
                "Message deletion anomaly detected for session %s. Resetting watermark %s -> 0",
                session_id,
                watermark_id,
            )
            watermark_id = 0

        # 3. Query all messages in session in strictly ascending ID order
        all_messages = (
            self.db.query(MessageModel)
            .filter(MessageModel.session_id == session_id)
            .order_by(MessageModel.id.asc())
            .all()
        )
        total_count = len(all_messages)
        if total_count <= self.config.window_size:
            return None

        # The sliding window boundary is the earliest message inside the sliding window
        window_boundary_msg = all_messages[-self.config.window_size]
        window_boundary_id = window_boundary_msg.id

        # 4. Select candidate messages between watermark and window boundary
        candidates = [
            m for m in all_messages
            if m.id > watermark_id and m.id < window_boundary_id
        ]
        if len(candidates) < self.config.summarization_threshold:
            return None

        # 5. Bound the summarization input batch: at most max_messages_per_summarization (40)
        # and at most max_summarization_input_chars (12,000)
        batch: list[MessageModel] = []
        batch_chars = 0
        for m in candidates[: self.config.max_messages_per_summarization]:
            m_len = len(m.content or "")
            if batch and (batch_chars + m_len > self.config.max_summarization_input_chars):
                break
            batch.append(m)
            batch_chars += m_len

        if not batch:
            return None

        new_watermark_id = batch[-1].id
        if new_watermark_id <= watermark_id:
            raise WatermarkRegressionError(
                f"New watermark {new_watermark_id} must be strictly greater than current {watermark_id}"
            )

        # 6. Apply secret scrubbing before text enters prompt
        batch_dicts = [
            {"role": m.role, "content": scrub_secrets(m.content or "")}
            for m in batch
        ]
        existing_summary_text = scrub_secrets(summary_row.summary_text) if summary_row else None

        prompt = build_summarization_prompt(
            messages=batch_dicts,
            existing_summary=existing_summary_text,
        )

        # 7. Generate structured summary (at most 1 LLM call)
        res = await self.llm_provider.generate_structured(
            prompt=prompt,
            schema=SummarizationResponse,
            system_prompt=None,
            temperature=0.0,
        )

        # 8. Apply secret scrubbing again to the generated summary before persistence
        clean_summary = scrub_secrets(res.summary.strip())

        # 9. Upsert with optimistic locking & insert race protection
        return self._upsert_summary(
            session_id=session_id,
            project_id=project_id,
            summary_text=clean_summary,
            watermark_id=new_watermark_id,
            message_count=len(batch),
            expected_version=expected_version,
        )

    def _upsert_summary(
        self,
        session_id: int,
        project_id: int,
        summary_text: str,
        watermark_id: int,
        message_count: int,
        expected_version: Optional[int],
    ) -> SessionSummary:
        """
        Upserts summary with atomic optimistic concurrency and INSERT race resolution.
        """
        if expected_version is None:
            summary = SessionSummary(
                session_id=session_id,
                project_id=project_id,
                summary_text=summary_text,
                message_watermark_id=watermark_id,
                message_count_summarized=message_count,
                status="active",
                version=1,
            )
            try:
                with self.db.begin_nested():
                    self.db.add(summary)
                    self.db.flush()
                self.db.commit()
                self.db.refresh(summary)
                return summary
            except IntegrityError:
                # Concurrent insert race collision! Savepoint rollback preserves transaction
                existing = (
                    self.db.query(SessionSummary)
                    .filter(SessionSummary.session_id == session_id)
                    .first()
                )
                if not existing:
                    raise
                expected_version = existing.version

        # Atomic optimistic update
        update_result = (
            self.db.query(SessionSummary)
            .filter(
                SessionSummary.session_id == session_id,
                SessionSummary.version == expected_version,
            )
            .update(
                {
                    "summary_text": summary_text,
                    "message_watermark_id": watermark_id,
                    "message_count_summarized": SessionSummary.message_count_summarized + message_count,
                    "version": SessionSummary.version + 1,
                },
                synchronize_session="fetch",
            )
        )
        if update_result == 0:
            raise StaleWriteError(
                f"Concurrent update conflict on session {session_id} memory (version {expected_version})"
            )

        self.db.commit()
        return self.db.query(SessionSummary).filter(SessionSummary.session_id == session_id).one()
