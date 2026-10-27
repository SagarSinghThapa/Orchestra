import logging
from app.research.exceptions import ResearchPipelineError

logger = logging.getLogger(__name__)


class LLMCallBudgetExceededError(ResearchPipelineError):
    """Raised when an LLM call budget is exhausted."""
    pass


class LLMCallBudget:
    """
    Request-local call budget controller.
    Enforces a strict runtime ceiling on LLM generation calls per research request.
    Thread-safe and async-safe for an isolated request execution.
    """

    def __init__(self, max_calls: int = 3) -> None:
        self.max_calls = max_calls
        self.used_calls: int = 0

    def consume(self) -> None:
        """
        Consumes one call credit from the budget.
        Raises LLMCallBudgetExceededError if the budget is exhausted.
        """
        if self.used_calls >= self.max_calls:
            logger.warning(
                "LLM call budget exhausted: %s/%s calls used",
                self.used_calls,
                self.max_calls,
            )
            raise LLMCallBudgetExceededError(
                f"LLM call budget exhausted (max {self.max_calls} calls allowed per request)"
            )
        self.used_calls += 1

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.used_calls)
