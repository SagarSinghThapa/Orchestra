from abc import ABC, abstractmethod
from app.evaluations.schemas import EvaluationCaseResultResponse, GoldenCase


class BaseEvaluator(ABC):
    """
    Abstract interface for deterministic evaluation components.
    """

    @abstractmethod
    async def evaluate_case(self, case: GoldenCase, run_id: str = "") -> EvaluationCaseResultResponse:
        """
        Evaluates a single GoldenCase and returns a validated case result.
        """
        pass
