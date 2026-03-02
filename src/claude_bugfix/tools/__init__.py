"""Tools module for claude-bugfix."""

from claude_bugfix.tools.base import Tool, ToolParameter, ToolResult
from claude_bugfix.tools.file_operations import (
    ReadFileTool,
    WriteFileTool,
    ListFilesTool,
    ReplaceInFileTool,
    SearchCodebaseTool,
    BashTool,
)
from claude_bugfix.tools.registry import ToolRegistry

__all__ = [
    "Tool",
    "ToolParameter",
    "ToolResult",
    "ReadFileTool",
    "WriteFileTool",
    "ListFilesTool",
    "ReplaceInFileTool",
    "SearchCodebaseTool",
    "BashTool",
    "ToolRegistry",
]
