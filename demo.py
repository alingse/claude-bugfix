#!/usr/bin/env python3
"""
Demo script showing how the agent would work (without requiring API key).
This demonstrates the tool system and agent loop structure.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from claude_bugfix.tools.registry import ToolRegistry
from claude_bugfix.tools.file_operations import (
    ReadFileTool,
    WriteFileTool,
    ListFilesTool,
    SearchCodebaseTool,
)
from rich.console import Console
from rich.panel import Panel

console = Console()


async def demo_tool_system():
    """Demonstrate the tool system without calling the LLM."""
    console.print(
        Panel(
            "[bold cyan]Claude Bugfix - Tool System Demo[/bold cyan]\n"
            "This demonstrates how the agent interacts with the codebase",
            border_style="cyan",
        )
    )
    console.print()

    # Create and populate registry
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ListFilesTool())
    registry.register(SearchCodebaseTool())

    console.print(f"[green]✓[/green] Registered {len(registry)} tools\n")

    # Demonstrate tool execution
    console.print("[bold]Step 1: List Python files[/bold]")
    result = await registry.execute_tool(
        "list_files", {"directory": "examples", "pattern": "*.py", "recursive": False}
    )
    if result.success:
        console.print(f"[dim]{result.data}[/dim]\n")

    console.print("[bold]Step 2: Read the example buggy file[/bold]")
    result = await registry.execute_tool("read_file", {"file_path": "examples/example_bug.py"})
    if result.success:
        lines = result.data.split("\n")[:15]  # Show first 15 lines
        console.print(f"[dim]{''.join(line + chr(10) for line in lines)}...[/dim]\n")

    console.print("[bold]Step 3: Search for 'divide' function[/bold]")
    result = await registry.execute_tool(
        "search_codebase",
        {"search_text": "def divide", "directory": "examples", "case_sensitive": False},
    )
    if result.success:
        console.print(f"[dim]{result.data}[/dim]\n")

    # Show OpenAI format
    console.print("[bold]Step 4: Tool definitions for OpenAI[/bold]")
    tools = registry.get_openai_tools()
    console.print(f"[dim]Generated {len(tools)} tool definitions in OpenAI format[/dim]")
    console.print(f"[dim]Example tool: {tools[0]['function']['name']}[/dim]\n")

    console.print(
        Panel(
            "[bold green]✓ Demo Complete[/bold green]\n\n"
            "In actual usage, the LLM would:\n"
            "1. Receive these tool definitions\n"
            "2. Decide which tools to call\n"
            "3. Execute them through the registry\n"
            "4. Analyze results and propose fixes\n\n"
            "To use with a real LLM, set OPENAI_API_KEY and run:\n"
            "[cyan]uv run claude-bugfix fix \"your bug description\"[/cyan]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    asyncio.run(demo_tool_system())
