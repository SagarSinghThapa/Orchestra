from abc import ABC, abstractmethod
from typing import Any, Dict
import asyncio

from app.developer.schemas import ToolRegistration


class BaseTool(ABC):
    """
    Base class for MCP Tools.
    """

    @property
    @abstractmethod
    def registration(self) -> ToolRegistration:
        """
        Returns the MCP tool registration schema (name, description, input_schema).
        """
        pass

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any], trace_id: str) -> Any:
        """
        Executes the tool with the given arguments and trace_id for logging.
        """
        pass
