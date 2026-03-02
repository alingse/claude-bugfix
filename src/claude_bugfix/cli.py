"""CLI interface for claude-bugfix - Interactive mode."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.rule import Rule
from rich.prompt import Prompt, Confirm
from rich.text import Text

from claude_bugfix.agent.interactive_loop import (
    InteractiveAgentLoop,
    AgentAction,
    ActionType,
)
from claude_bugfix.llm.client import OpenAIClient
from claude_bugfix.llm.config import LLMConfig
from claude_bugfix.tools.registry import ToolRegistry
from claude_bugfix.tools.file_operations import (
    ReadFileTool,
    WriteFileTool,
    ListFilesTool,
    ReplaceInFileTool,
    SearchCodebaseTool,
)
from claude_bugfix.utils.logger import setup_logger

console = Console()


def load_config(config_path: Optional[str] = None) -> dict:
    """Load configuration from YAML file."""
    if config_path and Path(config_path).exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    # Try default config
    default_config = Path(__file__).parent.parent.parent / "config" / "default_config.yaml"
    if default_config.exists():
        with open(default_config, "r") as f:
            return yaml.safe_load(f)

    # Return minimal default
    return {
        "llm": {"model": "gpt-4", "temperature": 0.1, "max_tokens": 4096},
        "agent": {"max_iterations": 20, "max_tool_calls_per_iteration": 5},
        "file_operations": {
            "max_file_size_mb": 10,
            "excluded_directories": ["node_modules", ".git", "__pycache__"],
            "excluded_patterns": ["*.pyc", "*.pyo"],
        },
    }


def create_tool_registry(config: dict) -> ToolRegistry:
    """Create and populate the tool registry."""
    registry = ToolRegistry()

    file_ops_config = config.get("file_operations", {})
    excluded_dirs = set(file_ops_config.get("excluded_directories", []))
    excluded_patterns = set(file_ops_config.get("excluded_patterns", []))
    max_file_size = file_ops_config.get("max_file_size_mb", 10)
    max_search_results = file_ops_config.get("search_max_results", 100)

    # Register tools
    registry.register(ReadFileTool(max_file_size_mb=max_file_size))
    registry.register(WriteFileTool())
    registry.register(ListFilesTool(excluded_dirs=excluded_dirs, excluded_patterns=excluded_patterns))
    registry.register(ReplaceInFileTool())
    registry.register(
        SearchCodebaseTool(
            excluded_dirs=excluded_dirs,
            excluded_patterns=excluded_patterns,
            max_results=max_search_results,
        )
    )

    return registry


def format_tool_args(tool_name: str, tool_args: dict) -> str:
    """Format tool arguments for display."""
    if tool_name == "read_file":
        return f"📖 读取文件: {tool_args.get('file_path', 'unknown')}"
    elif tool_name == "write_file":
        return f"📝 写入文件: {tool_args.get('file_path', 'unknown')}"
    elif tool_name == "list_files":
        directory = tool_args.get('directory', '.')
        pattern = tool_args.get('pattern', '')
        if pattern:
            return f"📁 列出文件: {directory}/ (匹配: {pattern})"
        return f"📁 列出文件: {directory}/"
    elif tool_name == "search_codebase":
        return f"🔍 搜索代码: '{tool_args.get('search_text', '')}'"
    elif tool_name == "replace_in_file":
        return f"🔄 替换内容: {tool_args.get('file_path', 'unknown')}"
    else:
        return f"🔧 {tool_name}: {tool_args}"


def display_tool_result(tool_name: str, result):
    """Display tool execution result."""
    if not result.success:
        console.print(f"[red]❌ 执行失败: {result.error}[/red]")
        return

    data = result.data
    if not data:
        console.print("[dim]无返回数据[/dim]")
        return

    # Format based on tool type
    if tool_name == "read_file":
        # Extract file content from result
        lines = str(data).split('\n')
        if len(lines) > 2 and lines[0].startswith("File:"):
            content = '\n'.join(lines[2:])
            file_path = lines[0].replace("File:", "").strip()
            syntax = Syntax(content, "python", theme="monokai", line_numbers=True)
            console.print(syntax)
        else:
            console.print(data)
    elif tool_name == "search_codebase":
        # Display search results
        console.print("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")
        lines = str(data).split('\n')
        for line in lines:
            if line.startswith("Found"):
                console.print(f"[cyan]{line}[/cyan]")
            elif ':' in line and any(ext in line for ext in ['.py', '.js', '.ts', '.java', '.go', '.rs']):
                parts = line.split(':', 2)
                if len(parts) >= 2:
                    file_info = f"[green]{parts[0]}[/green]:[yellow]{parts[1]}[/yellow]"
                    content = parts[2] if len(parts) > 2 else ""
                    console.print(f"  {file_info}: {content}")
                else:
                    console.print(f"  {line}")
            else:
                console.print(f"  {line}")
        console.print("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")
    elif tool_name == "list_files":
        console.print("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")
        lines = str(data).split('\n')
        for line in lines:
            if line.strip().startswith("-"):
                console.print(f"  [green]{line}[/green]")
            else:
                console.print(f"[cyan]{line}[/cyan]")
        console.print("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")
    else:
        # Default display
        console.print("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")
        console.print(data)
        console.print("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")


def create_action_callback(yolo_mode: bool = False):
    """Create action callback for interactive mode.

    Args:
        yolo_mode: If True, skip all confirmations. If False, only skip confirmations
                   for read-only tools (read_file, search_codebase, list_files).
    """
    skip_confirmations = False

    # Tools that don't need confirmation in normal mode
    readonly_tools = {'read_file', 'search_codebase', 'list_files'}
    # Tools that always need confirmation in normal mode
    write_tools = {'write_file', 'replace_in_file'}

    def callback(action: AgentAction) -> bool:
        nonlocal skip_confirmations

        if action.type == ActionType.THINKING:
            console.print(f"\n[bold cyan][第{action.iteration}步/20] 🤔 Agent 正在思考...[/bold cyan]")
            return True

        elif action.type == ActionType.TOOL_CALL:
            # In yolo mode, skip all confirmations
            if yolo_mode:
                console.print(f"\n[yellow]▶ {format_tool_args(action.tool_name, action.tool_args)}[/yellow]")
                return True

            # In normal mode, skip confirmation for read-only tools
            if action.tool_name in readonly_tools:
                console.print(f"\n[yellow]▶ {format_tool_args(action.tool_name, action.tool_args)}[/yellow]")
                return True

            # User selected "skip all" during this session
            if skip_confirmations:
                console.print(f"\n[yellow]▶ {format_tool_args(action.tool_name, action.tool_args)}[/yellow]")
                return True

            # Ask for confirmation (for write tools in normal mode)
            console.print(f"\n[yellow]▶ {format_tool_args(action.tool_name, action.tool_args)}[/yellow]")
            choices = "[Y/n/a(全部跳过)]"
            response = Prompt.ask(f"确认执行? {choices}", default="Y", show_default=False)

            if response.lower() == 'a':
                skip_confirmations = True
                return True
            elif response.lower() == 'n':
                return False
            return True

        elif action.type == ActionType.TOOL_RESULT:
            if action.tool_result:
                display_tool_result(action.tool_name, action.tool_result)
            return True

        elif action.type == ActionType.FINAL_ANSWER:
            console.print("\n")
            console.print(Panel(
                Markdown(action.content),
                title="[bold green]💡 分析完成[/bold green]",
                border_style="green"
            ))
            return True

        elif action.type == ActionType.ERROR:
            console.print(f"\n[red]❌ {action.content}[/red]")
            return True

        return True

    return callback


async def interactive_session(
    llm_client: OpenAIClient,
    tool_registry: ToolRegistry,
    system_prompt: str,
    config: dict,
    yolo_mode: bool = False,
):
    """Run interactive session."""
    agent_config = config.get("agent", {})
    max_iterations = agent_config.get("max_iterations", 20)
    max_tool_calls = agent_config.get("max_tool_calls_per_iteration", 5)

    # Print header
    console.print()
    yolo_indicator = " [bold yellow]⚡ YOLO MODE[/bold yellow]" if yolo_mode else ""
    console.print(Panel.fit(
        f"[bold cyan]🐛 Claude Bugfix[/bold cyan] - [dim]交互式代码修复助手[/dim]{yolo_indicator}\n"
        f"[dim]工作目录: {os.getcwd()}[/dim]",
        border_style="cyan"
    ))

    if yolo_mode:
        console.print("[yellow]⚡ YOLO 模式已启用: 所有操作将自动执行，无需确认[/yellow]\n")

    # Main conversation loop
    while True:
        console.print()
        user_input = Prompt.ask("[bold]请输入 bug 描述[/bold] (或 '[red]quit[/red]' 退出)")

        if user_input.lower() in ('quit', 'exit', 'q', '退出'):
            console.print("\n[dim]再见! 👋[/dim]")
            break

        if not user_input.strip():
            continue

        # Create action callback
        callback = create_action_callback(yolo_mode=yolo_mode)

        # Create agent
        agent = InteractiveAgentLoop(
            llm_client=llm_client,
            tool_registry=tool_registry,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            max_tool_calls_per_iteration=max_tool_calls,
            action_callback=callback,
        )

        # Run agent
        try:
            result = await agent.run(user_input)

            # Display token usage
            token_usage = result.get("token_usage", {})
            console.print()
            console.print(Rule(style="dim"))
            console.print(
                f"[dim]迭代次数: {result['iterations']} | "
                f"Token 使用: {token_usage.get('total_tokens', 0)} "
                f"(输入: {token_usage.get('prompt_tokens', 0)}, "
                f"输出: {token_usage.get('completion_tokens', 0)})[/dim]"
            )
            console.print(Rule(style="dim"))

            if not result["success"]:
                console.print(f"\n[red]⚠️ {result['result']}[/red]")

        except Exception as e:
            console.print(f"\n[red]❌ 发生错误: {str(e)}[/red]")

        console.print()
        console.print("[dim]可以继续输入新的 bug 描述，或输入 'quit' 退出[/dim]")


@click.command()
@click.option(
    "--path",
    "-p",
    default=".",
    help="Path to the codebase (default: current directory)",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="LLM model to use (default: from config or env)",
)
@click.option(
    "--config",
    "-c",
    default=None,
    help="Path to configuration file",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
@click.option(
    "--yolo",
    "-y",
    is_flag=True,
    help="YOLO mode: skip confirmations for read and search operations",
)
@click.version_option(version="0.1.0")
def main(path: str, model: Optional[str], config: Optional[str], verbose: bool, yolo: bool):
    """Claude Bugfix - AI-Powered Code Repair Agent

    直接运行进入交互式模式，与 Agent 对话修复代码问题。
    """
    # Setup logging
    setup_logger(verbose=verbose)

    # Load configuration
    cfg = load_config(config)

    # Change to target directory
    original_dir = os.getcwd()
    if path != ".":
        if not os.path.exists(path):
            console.print(f"[red]❌ 路径不存在: {path}[/red]")
            sys.exit(1)
        os.chdir(path)
        console.print(f"[dim]已切换到工作目录: {os.getcwd()}[/dim]\n")

    try:
        # Initialize LLM client
        llm_config = LLMConfig.from_env(model=model)
        llm_client = OpenAIClient(llm_config)

        # Create tool registry
        tool_registry = create_tool_registry(cfg)

        # Load system prompt
        prompt_path = Path(__file__).parent.parent.parent / "config" / "prompts" / "system_prompt.txt"
        system_prompt = asyncio.run(InteractiveAgentLoop.load_system_prompt(str(prompt_path)))

        # Run interactive session
        asyncio.run(interactive_session(
            llm_client=llm_client,
            tool_registry=tool_registry,
            system_prompt=system_prompt,
            config=cfg,
            yolo_mode=yolo,
        ))

    except ValueError as e:
        console.print(f"[bold red]❌ 配置错误:[/bold red] {str(e)}")
        console.print("\n[dim]请确保设置了 OPENAI_API_KEY 环境变量，或在 .env 文件中配置。[/dim]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n\n[dim]用户取消操作，退出...[/dim]")
    except Exception as e:
        console.print(f"[bold red]❌ 错误:[/bold red] {str(e)}")
        if verbose:
            console.print_exception()
        sys.exit(1)
    finally:
        os.chdir(original_dir)


if __name__ == "__main__":
    main()
