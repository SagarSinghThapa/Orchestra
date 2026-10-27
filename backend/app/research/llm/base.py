from dataclasses import dataclass
from typing import Optional, Protocol, Type, TypeVar, runtime_checkable
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    usage_tokens: Optional[dict] = None


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol defining the interface for LLM text and structured generation."""

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> str:
        """Generate unstructured prose response for prompt."""
        ...

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> T:
        """Generate structured response validated against a concrete Pydantic schema."""
        ...
