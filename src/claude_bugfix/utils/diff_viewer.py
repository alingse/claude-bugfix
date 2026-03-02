"""Diff viewer for displaying file changes."""

import difflib
from typing import List, Tuple
from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel


def generate_unified_diff(
    original: str,
    modified: str,
    filename: str = "file",
    context_lines: int = 3,
) -> str:
    """Generate a unified diff between original and modified content."""
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm="",
        n=context_lines,
    )

    return "".join(diff)


def display_diff(
    original: str,
    modified: str,
    filename: str,
    console: Console,
    context_lines: int = 3,
) -> None:
    """Display a diff using rich formatting."""
    diff_text = generate_unified_diff(original, modified, filename, context_lines)

    if not diff_text:
        console.print("[yellow]No changes detected[/yellow]")
        return

    # Display with syntax highlighting
    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
    panel = Panel(
        syntax,
        title=f"[bold cyan]Changes to {filename}[/bold cyan]",
        border_style="cyan",
    )
    console.print(panel)


def display_multiple_diffs(
    changes: List[Tuple[str, str, str]],
    console: Console,
    context_lines: int = 3,
) -> None:
    """
    Display multiple file diffs.

    Args:
        changes: List of (filename, original_content, modified_content) tuples
        console: Rich console for output
        context_lines: Number of context lines in diff
    """
    if not changes:
        console.print("[yellow]No changes to display[/yellow]")
        return

    console.print(f"\n[bold]Proposed changes to {len(changes)} file(s):[/bold]\n")

    for filename, original, modified in changes:
        display_diff(original, modified, filename, console, context_lines)
        console.print()  # Add spacing between diffs


def get_change_summary(original: str, modified: str) -> dict:
    """Get a summary of changes between two strings."""
    original_lines = original.splitlines()
    modified_lines = modified.splitlines()

    diff = list(
        difflib.unified_diff(
            original_lines,
            modified_lines,
            lineterm="",
        )
    )

    additions = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

    return {
        "additions": additions,
        "deletions": deletions,
        "total_changes": additions + deletions,
    }
