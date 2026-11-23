from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedPage:
    """Represents text extracted from a single isolated document page."""
    page_number: int  # 1-indexed
    text: str
    char_count: int


@dataclass
class ExtractedDocument:
    """Represents a fully extracted document composed of page units."""
    pages: list[ExtractedPage]
    total_pages: int
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    """Abstract interface for file format parsers."""

    @abstractmethod
    def parse(self, content: bytes, filename: str) -> ExtractedDocument:
        """Parse raw document bytes into an ExtractedDocument."""
        ...
