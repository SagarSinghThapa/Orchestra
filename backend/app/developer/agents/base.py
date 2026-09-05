from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    """
    Base class for Developer Subgraph Agents.
    """

    @abstractmethod
    async def execute(self, params: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """
        Execute the agent logic.
        """
        pass
