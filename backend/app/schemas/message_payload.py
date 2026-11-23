"""
Structured Message Payload Schema and Extraction Utilities.

Provides versioned serialization for rich assistant turns (research, developer, direct_qa)
and safe plain-text extraction for memory assembly, token counting, summarization, and legacy consumers.
"""

import json
import logging
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("orchestra.message_payload")

CURRENT_PAYLOAD_VERSION = 1


class StructuredMessagePayload(BaseModel):
    version: int = CURRENT_PAYLOAD_VERSION
    intent: str  # "research", "developer", "direct_qa"
    answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "completed"
    question: Optional[str] = None
    evidence_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


def serialize_assistant_payload(
    intent: str,
    answer: str,
    citations: Optional[list[dict[str, Any]]] = None,
    claims: Optional[list[dict[str, Any]]] = None,
    status: str = "completed",
    question: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    """Serializes assistant output into a versioned JSON payload string."""
    payload = StructuredMessagePayload(
        version=CURRENT_PAYLOAD_VERSION,
        intent=intent,
        answer=answer,
        citations=citations or [],
        claims=claims or [],
        status=status,
        question=question,
        evidence_count=len(citations or []),
        metadata=metadata or {},
    )
    return payload.model_dump_json()


def extract_plain_content(content: str) -> str:
    """
    Safely extracts plain display/conversational text from message content.
    Works across plain-text strings, versioned JSON, legacy JSON, and malformed strings.
    Guarantees zero exceptions.
    """
    if not content or not isinstance(content, str):
        return ""
    trimmed = content.strip()
    if not (trimmed.startswith("{") and trimmed.endswith("}")):
        return content
    try:
        data = json.loads(trimmed)
        if isinstance(data, dict):
            text = data.get("answer") or data.get("summary")
            if text is not None and isinstance(text, str):
                return text
    except Exception as exc:
        logger.debug("extract_plain_content fallback to raw content: %s", exc)
    return content
