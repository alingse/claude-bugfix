"""File operation tools for the agent."""

import asyncio
import os
import shlex
from pathlib import Path
from typing import List, Optional

from claude_bugfix.tools.base import Tool, ToolParameter, ToolResult
from claude_bugfix.utils.file_utils import (
    read_file_async,
    write_file_async,
    list_files_in_directory,
    search_in_file,
)


class ReadFileTool(Tool):
    """Tool to read file contents."""

    def __init__(self, max_file_size_mb: int = 10):
        super().__init__()
        self.max_file_size_mb = max_file_size_mb

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file. Use this to examine code and understand context."

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="Path to the file to read (absolute or relative to current directory)",
                required=True,
            )
        ]

    async def execute(self, file_path: str) -> ToolResult:
        """Execute the read file operation."""
        try:
            content = await read_file_async(file_path, self.max_file_size_mb)
            return ToolResult(
                success=True,
                data=f"File: {file_path}\n\n{content}",
            )
        except FileNotFoundError as e:
            return ToolResult(success=False, error=str(e))
        except ValueError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to read file: {str(e)}")


class WriteFileTool(Tool):
    """Tool to write content to a file."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file. Creates the file if it doesn't exist. Use for new files or complete rewrites."

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="Path to the file to write",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="Content to write to the file",
                required=True,
            ),
        ]

    async def execute(self, file_path: str, content: str) -> ToolResult:
        """Execute the write file operation."""
        try:
            await write_file_async(file_path, content)
            return ToolResult(
                success=True,
                data=f"Successfully wrote to {file_path}",
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to write file: {str(e)}")


class ListFilesTool(Tool):
    """Tool to list files in a directory."""

    def __init__(
        self,
        excluded_dirs: Optional[set] = None,
        excluded_patterns: Optional[set] = None,
    ):
        super().__init__()
        self.excluded_dirs = excluded_dirs
        self.excluded_patterns = excluded_patterns

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return "List files in a directory. Supports glob patterns (e.g., '*.py', '**/*.js'). Respects .gitignore."

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="directory",
                type="string",
                description="Directory path to list files from (default: current directory)",
                required=False,
            ),
            ToolParameter(
                name="pattern",
                type="string",
                description="Glob pattern to filter files (e.g., '*.py', '**/*.js')",
                required=False,
            ),
            ToolParameter(
                name="recursive",
                type="boolean",
                description="Whether to search recursively (default: true)",
                required=False,
            ),
        ]

    async def execute(
        self,
        directory: str = ".",
        pattern: Optional[str] = None,
        recursive: bool = True,
    ) -> ToolResult:
        """Execute the list files operation."""
        try:
            files = list_files_in_directory(
                directory,
                pattern,
                self.excluded_dirs,
                self.excluded_patterns,
                recursive,
            )

            if not files:
                return ToolResult(
                    success=True,
                    data=f"No files found in {directory}" + (f" matching '{pattern}'" if pattern else ""),
                )

            file_list = "\n".join(f"  - {f}" for f in files)
            return ToolResult(
                success=True,
                data=f"Found {len(files)} file(s) in {directory}:\n{file_list}",
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to list files: {str(e)}")


class ReplaceInFileTool(Tool):
    """Tool to replace content in a file."""

    @property
    def name(self) -> str:
        return "replace_in_file"

    @property
    def description(self) -> str:
        return "Replace content in a file using search and replace. The search text must be unique in the file."

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description="Path to the file to modify",
                required=True,
            ),
            ToolParameter(
                name="search",
                type="string",
                description="Text to search for (must be unique in the file)",
                required=True,
            ),
            ToolParameter(
                name="replace",
                type="string",
                description="Text to replace with",
                required=True,
            ),
        ]

    async def execute(self, file_path: str, search: str, replace: str) -> ToolResult:
        """Execute the replace in file operation."""
        try:
            # Read the file
            content = await read_file_async(file_path)

            # Check if search text exists
            if search not in content:
                return ToolResult(
                    success=False,
                    error=f"Search text not found in {file_path}",
                )

            # Check if search text is unique
            count = content.count(search)
            if count > 1:
                return ToolResult(
                    success=False,
                    error=f"Search text appears {count} times in {file_path}. Must be unique.",
                )

            # Perform replacement
            new_content = content.replace(search, replace, 1)

            # Write back
            await write_file_async(file_path, new_content)

            return ToolResult(
                success=True,
                data=f"Successfully replaced content in {file_path}",
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to replace content: {str(e)}")


class SearchCodebaseTool(Tool):
    """Tool to search for text across the codebase."""

    def __init__(
        self,
        excluded_dirs: Optional[set] = None,
        excluded_patterns: Optional[set] = None,
        max_results: int = 100,
    ):
        super().__init__()
        self.excluded_dirs = excluded_dirs
        self.excluded_patterns = excluded_patterns
        self.max_results = max_results

    @property
    def name(self) -> str:
        return "search_codebase"

    @property
    def description(self) -> str:
        return "Search for text or patterns across the codebase. Returns matching lines with file paths and line numbers."

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="search_text",
                type="string",
                description="Text to search for",
                required=True,
            ),
            ToolParameter(
                name="directory",
                type="string",
                description="Directory to search in (default: current directory)",
                required=False,
            ),
            ToolParameter(
                name="file_pattern",
                type="string",
                description="File pattern to limit search (e.g., '*.py')",
                required=False,
            ),
            ToolParameter(
                name="case_sensitive",
                type="boolean",
                description="Whether search should be case sensitive (default: false)",
                required=False,
            ),
        ]

    async def execute(
        self,
        search_text: str,
        directory: str = ".",
        file_pattern: Optional[str] = None,
        case_sensitive: bool = False,
    ) -> ToolResult:
        """Execute the search codebase operation."""
        try:
            # Get list of files to search
            files = list_files_in_directory(
                directory,
                file_pattern,
                self.excluded_dirs,
                self.excluded_patterns,
                recursive=True,
            )

            all_matches = []
            for file_path in files:
                matches = search_in_file(file_path, search_text, case_sensitive)
                all_matches.extend(matches)

                if len(all_matches) >= self.max_results:
                    break

            if not all_matches:
                return ToolResult(
                    success=True,
                    data=f"No matches found for '{search_text}' in {directory}",
                )

            # Limit results
            all_matches = all_matches[: self.max_results]

            # Format results
            result_lines = []
            for match in all_matches:
                result_lines.append(
                    f"{match['file']}:{match['line_number']}: {match['line']}"
                )

            result_text = "\n".join(result_lines)
            summary = f"Found {len(all_matches)} match(es) for '{search_text}':\n\n{result_text}"

            if len(all_matches) >= self.max_results:
                summary += f"\n\n(Limited to first {self.max_results} results)"

            return ToolResult(success=True, data=summary)
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to search codebase: {str(e)}")


class BashTool(Tool):
    """Tool to execute bash commands."""

    def __init__(
        self,
        timeout: int = 60,
        allowed_commands: Optional[List[str]] = None,
        blocked_commands: Optional[List[str]] = None,
        working_directory: Optional[str] = None,
    ):
        super().__init__()
        self.timeout = timeout
        self.allowed_commands = set(allowed_commands) if allowed_commands else None
        self.blocked_commands = set(blocked_commands) if blocked_commands else {
            "rm -rf /",
            "rm -rf /*",
            "> /dev/sda",
            "dd if=/dev/zero",
            "mkfs",
            "format",
            "shutdown",
            "reboot",
            "halt",
            "poweroff",
        }
        self.working_directory = working_directory or os.getcwd()

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return (
            "Execute a bash command. Use this to run tests, build commands, "
            "check git status, or perform system operations. "
            "Commands run with a timeout and security restrictions."
        )

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="command",
                type="string",
                description="The bash command to execute",
                required=True,
            ),
            ToolParameter(
                name="cwd",
                type="string",
                description="Working directory for the command (default: current directory)",
                required=False,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description=f"Timeout in seconds (default: {self.timeout})",
                required=False,
            ),
            ToolParameter(
                name="description",
                type="string",
                description="Optional description of what the command does",
                required=False,
            ),
        ]

    def _is_command_safe(self, command: str) -> bool:
        """Check if the command is safe to execute."""
        # Check blocked commands
        if self.blocked_commands:
            for blocked in self.blocked_commands:
                if blocked in command.lower():
                    return False
        
        # Check allowed commands whitelist
        if self.allowed_commands:
            # Parse the command to get the main command
            try:
                parsed = shlex.split(command)
                if parsed:
                    main_cmd = parsed[0]
                    if main_cmd not in self.allowed_commands:
                        return False
            except ValueError:
                pass
        
        return True

    async def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        description: Optional[str] = None,
    ) -> ToolResult:
        """Execute the bash command."""
        try:
            # Validate command safety
            if not self._is_command_safe(command):
                return ToolResult(
                    success=False,
                    error=f"Command blocked for security reasons: {command}",
                )

            # Determine working directory
            work_dir = cwd or self.working_directory
            work_dir = os.path.abspath(work_dir)

            # Ensure working directory exists
            if not os.path.exists(work_dir):
                return ToolResult(
                    success=False,
                    error=f"Working directory does not exist: {work_dir}",
                )

            # Use provided timeout or default
            cmd_timeout = timeout or self.timeout

            # Execute the command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=cmd_timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    success=False,
                    error=f"Command timed out after {cmd_timeout} seconds",
                )

            # Decode output
            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

            # Prepare result
            result_lines = []
            if description:
                result_lines.append(f"Description: {description}")
            result_lines.append(f"Command: {command}")
            result_lines.append(f"Working directory: {work_dir}")
            result_lines.append(f"Exit code: {process.returncode}")
            
            if stdout_str:
                result_lines.append(f"\n--- STDOUT ---\n{stdout_str}")
            if stderr_str:
                result_lines.append(f"\n--- STDERR ---\n{stderr_str}")

            result_text = "\n".join(result_lines)

            if process.returncode == 0:
                return ToolResult(success=True, data=result_text)
            else:
                return ToolResult(
                    success=False,
                    error=f"Command failed with exit code {process.returncode}\n{result_text}",
                )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to execute command: {str(e)}")
