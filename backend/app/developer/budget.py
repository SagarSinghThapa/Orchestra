import logging
from typing import Optional
from app.developer.errors import DeveloperBaseException, ErrorTaxonomy

logger = logging.getLogger(__name__)


class LLMCallBudgetExceededError(DeveloperBaseException):
    """Raised when an LLM call budget is exhausted in the Developer pipeline."""
    def __init__(
        self,
        message: str = "LLM call budget exceeded: maximum 2 LLM calls allowed per request.",
        context: Optional[dict] = None
    ):
        super().__init__(ErrorTaxonomy.VALIDATION_INPUT, message, context)


class LLMCallBudget:
    """
    Request-local call budget controller for Developer Intelligence.
    Enforces a strict runtime ceiling on LLM generation calls per developer request.
    Thread-safe and async-safe for an isolated request execution.
    """

    def __init__(self, max_calls: int = 2) -> None:
        self.max_calls = max_calls
        self.used_calls: int = 0

    def consume(self) -> None:
        """
        Consumes one call credit from the budget.
        Raises LLMCallBudgetExceededError if the budget is exhausted.
        """
        if self.used_calls >= self.max_calls:
            logger.warning(
                "Developer LLM call budget exhausted: %s/%s calls used",
                self.used_calls,
                self.max_calls,
            )
            raise LLMCallBudgetExceededError(
                f"LLM call budget exhausted: maximum {self.max_calls} LLM calls allowed per request."
            )
        self.used_calls += 1

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.used_calls)
