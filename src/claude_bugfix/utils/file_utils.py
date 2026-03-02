"""File system utilities."""

import os
from pathlib import Path
from typing import List, Optional, Set
import aiofiles
import pathspec


async def read_file_async(file_path: str, max_size_mb: int = 10) -> str:
    """Read a file asynchronously with size limit."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    # Check file size
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"File too large: {size_mb:.2f}MB (max: {max_size_mb}MB)")

    async with aiofiles.open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return await f.read()


async def write_file_async(file_path: str, content: str) -> None:
    """Write content to a file asynchronously."""
    path = Path(file_path)

    # Create parent directories if they don't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(content)


def load_gitignore_patterns(root_path: str) -> Optional[pathspec.PathSpec]:
    """Load .gitignore patterns from the root directory."""
    gitignore_path = Path(root_path) / ".gitignore"

    if not gitignore_path.exists():
        return None

    with open(gitignore_path, "r") as f:
        patterns = f.read().splitlines()

    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def should_exclude_path(
    path: Path,
    root_path: Path,
    excluded_dirs: Set[str],
    excluded_patterns: Set[str],
    gitignore_spec: Optional[pathspec.PathSpec] = None,
) -> bool:
    """Check if a path should be excluded based on various criteria."""
    # Check if any parent directory is in excluded_dirs
    for part in path.parts:
        if part in excluded_dirs:
            return True

    # Check excluded patterns
    for pattern in excluded_patterns:
        if path.match(pattern):
            return True

    # Check gitignore
    if gitignore_spec:
        try:
            rel_path = path.relative_to(root_path)
            if gitignore_spec.match_file(str(rel_path)):
                return True
        except ValueError:
            # Path is not relative to root_path
            pass

    return False


def list_files_in_directory(
    directory: str,
    pattern: Optional[str] = None,
    excluded_dirs: Optional[Set[str]] = None,
    excluded_patterns: Optional[Set[str]] = None,
    recursive: bool = True,
) -> List[str]:
    """List files in a directory with optional filtering."""
    if excluded_dirs is None:
        excluded_dirs = {
            "node_modules",
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "dist",
            "build",
        }

    if excluded_patterns is None:
        excluded_patterns = {"*.pyc", "*.pyo", "*.so", ".DS_Store"}

    root_path = Path(directory).resolve()
    gitignore_spec = load_gitignore_patterns(str(root_path))

    files = []
    glob_pattern = "**/*" if recursive else "*"

    if pattern:
        glob_pattern = f"**/{pattern}" if recursive else pattern

    for path in root_path.glob(glob_pattern):
        if not path.is_file():
            continue

        if should_exclude_path(path, root_path, excluded_dirs, excluded_patterns, gitignore_spec):
            continue

        files.append(str(path))

    return sorted(files)


def search_in_file(file_path: str, search_text: str, case_sensitive: bool = False) -> List[dict]:
    """Search for text in a file and return matching lines with context."""
    matches = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        search_lower = search_text if case_sensitive else search_text.lower()

        for line_num, line in enumerate(lines, start=1):
            line_to_check = line if case_sensitive else line.lower()

            if search_lower in line_to_check:
                matches.append(
                    {
                        "line_number": line_num,
                        "line": line.rstrip(),
                        "file": file_path,
                    }
                )

    except Exception:
        # Silently skip files that can't be read
        pass

    return matches
