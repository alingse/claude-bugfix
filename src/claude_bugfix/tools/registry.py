"""Tool registry for managing and executing tools."""

import logging
from typing import Any, Dict, List, Optional

from claude_bugfix.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing tools available to the agent."""

    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool in the registry."""
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all_tools(self) -> List[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Get all tools in OpenAI function calling format."""
        return [tool.to_openai_format() for tool in self._tools.values()]

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name with the given arguments."""
        tool = self.get_tool(name)
        if not tool:
            logger.error(f"Tool not found: {name}")
            return ToolResult(success=False, error=f"Tool '{name}' not found")

        try:
            logger.info(f"Executing tool: {name} with args: {arguments}")
            result = await tool.execute(**arguments)
            logger.info(f"Tool {name} executed successfully")
            return result
        except Exception as e:
            logger.error(f"Error executing tool {name}: {str(e)}", exc_info=True)
            return ToolResult(success=False, error=f"Tool execution failed: {str(e)}")

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
