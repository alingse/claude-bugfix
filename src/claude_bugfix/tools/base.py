"""Base tool interface for the agent system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Represents a parameter for a tool."""

    name: str
    type: str
    description: str
    required: bool = True
    enum: Optional[List[str]] = None


class ToolResult(BaseModel):
    """Represents the result of a tool execution."""

    success: bool
    data: Any = None
    error: Optional[str] = None

    def to_message(self) -> str:
        """Convert result to a message string for the LLM."""
        if self.success:
            if isinstance(self.data, str):
                return self.data
            return str(self.data)
        return f"Error: {self.error}"


class Tool(ABC):
    """Abstract base class for all tools."""

    def __init__(self):
        """Initialize the tool."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the tool description."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> List[ToolParameter]:
        """Return the list of tool parameters."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with the given arguments."""
        pass

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert tool definition to OpenAI function calling format."""
        properties = {}
        required = []

        for param in self.parameters:
            param_def = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                param_def["enum"] = param.enum

            properties[param.name] = param_def
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
