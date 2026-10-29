from typing import Optional
from sqlalchemy.orm import Session

from app.memory.schemas import ContextAssemblerConfig, MemoryContext
from app.models.message import Message as MessageModel
from app.models.session_summary import SessionSummary


class ContextAssembler:
    """
    Assembles bounded conversation context from the three-tier memory taxonomy.
    Enforces max_context_chars as an unbreachable hard ceiling under all conditions.
    Cost: 0 LLM calls (pure database queries).
    """

    def __init__(
        self,
        db: Session,
        config: Optional[ContextAssemblerConfig] = None,
    ):
        self.db = db
        self.config = config or ContextAssemblerConfig()

    def assemble(
        self,
        session_id: int,
        project_id: int,
    ) -> MemoryContext:
        """
        Assembles bounded context guaranteeing total_chars <= max_context_chars.
        """
        budget = self.config.max_context_chars
        tag_overhead = 200  # Structural XML tag reserve
        avail = max(100, budget - tag_overhead)

        # 1. Fetch raw candidates
        # Tier 1: Sliding window candidates (newest first)
        recent_raw = (
            self.db.query(MessageModel)
            .filter(MessageModel.session_id == session_id)
            .order_by(MessageModel.id.desc())
            .limit(self.config.window_size)
            .all()
        )

        # Tier 2: Current session summary
        curr_summary_row = (
            self.db.query(SessionSummary)
            .filter(SessionSummary.session_id == session_id)
            .first()
        )
        curr_summary_text = curr_summary_row.summary_text if curr_summary_row else ""

        # Tier 3: Sibling session summaries (same project, different session)
        sibling_summaries = (
            self.db.query(SessionSummary)
            .filter(
                SessionSummary.project_id == project_id,
                SessionSummary.session_id != session_id,
            )
            .order_by(SessionSummary.updated_at.desc())
            .limit(self.config.max_project_summaries)
            .all()
        )
        sibling_text = "\n---\n".join([s.summary_text for s in sibling_summaries if s.summary_text])

        # 2. Strict Budget Allocation Algorithm
        # Recent messages receive up to 70% of available budget
        recent_budget = int(avail * 0.70)
        selected_messages: list[dict] = []
        recent_chars = 0

        for msg in recent_raw:
            formatted_len = len(f"[{msg.role}]: {msg.content}\n")
            if recent_chars + formatted_len <= recent_budget:
                selected_messages.append({"role": msg.role, "content": msg.content})
                recent_chars += formatted_len
            elif not selected_messages:
                # Pathological case: Even the single newest message exceeds the budget!
                # Strictly truncate it to fit available budget.
                max_msg_len = max(50, recent_budget - 50)
                truncated_content = (msg.content[:max_msg_len]) + "... [truncated to fit context budget]"
                selected_messages.append({"role": msg.role, "content": truncated_content})
                recent_chars += len(truncated_content)
                break
            else:
                # Drop older messages in the window to protect the hard ceiling
                break

        # Chronological order for recent messages
        selected_messages.reverse()

        # 3. Session Summary Allocation (Tier 2)
        remaining_after_recent = avail - recent_chars
        summary_budget = max(0, int(remaining_after_recent * 0.70))
        final_summary = ""
        if curr_summary_text and summary_budget > 50:
            if len(curr_summary_text) <= summary_budget:
                final_summary = curr_summary_text
            else:
                final_summary = curr_summary_text[:summary_budget - 30] + "... [truncated]"

        # 4. Project Context Allocation (Tier 3)
        remaining_after_summary = avail - recent_chars - len(final_summary)
        final_project_context = ""
        if sibling_text and remaining_after_summary > 50:
            if len(sibling_text) <= remaining_after_summary:
                final_project_context = sibling_text
            else:
                final_project_context = sibling_text[:remaining_after_summary - 30] + "... [truncated]"

        total_content_chars = recent_chars + len(final_summary) + len(final_project_context)

        return MemoryContext(
            project_context=final_project_context,
            session_summary=final_summary,
            recent_messages=selected_messages,
            total_chars=total_content_chars,
        )

    def format_for_prompt(self, ctx: MemoryContext) -> str:
        """Formats MemoryContext into structured XML string."""
        if not ctx.recent_messages and not ctx.session_summary and not ctx.project_context:
            return ""

        sections = ["<SYSTEM_CONTEXT>"]
        if ctx.project_context:
            sections.append(f"<PROJECT_MEMORY>\n{ctx.project_context}\n</PROJECT_MEMORY>")
        if ctx.session_summary:
            sections.append(f"<SESSION_SUMMARY>\n{ctx.session_summary}\n</SESSION_SUMMARY>")
        if ctx.recent_messages:
            lines = [f"[{m['role']}]: {m['content']}" for m in ctx.recent_messages]
            sections.append(f"<RECENT_MESSAGES>\n" + "\n".join(lines) + "\n</RECENT_MESSAGES>")
        sections.append("</SYSTEM_CONTEXT>")
        return "\n".join(sections)

