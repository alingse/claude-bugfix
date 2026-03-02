"""Tests for file operation tools."""

import pytest
import tempfile
import os
from pathlib import Path

from claude_bugfix.tools.file_operations import (
    ReadFileTool,
    WriteFileTool,
    ListFilesTool,
    ReplaceInFileTool,
    SearchCodebaseTool,
)


@pytest.mark.asyncio
async def test_read_file_tool():
    """Test reading a file."""
    tool = ReadFileTool()

    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Hello, World!")
        temp_path = f.name

    try:
        result = await tool.execute(file_path=temp_path)
        assert result.success is True
        assert "Hello, World!" in result.data
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
async def test_read_file_not_found():
    """Test reading a non-existent file."""
    tool = ReadFileTool()
    result = await tool.execute(file_path="/nonexistent/file.txt")
    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_write_file_tool():
    """Test writing to a file."""
    tool = WriteFileTool()

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "test.txt")
        content = "Test content"

        result = await tool.execute(file_path=file_path, content=content)
        assert result.success is True

        # Verify file was written
        with open(file_path, "r") as f:
            assert f.read() == content


@pytest.mark.asyncio
async def test_list_files_tool():
    """Test listing files in a directory."""
    tool = ListFilesTool()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files
        Path(tmpdir, "file1.py").touch()
        Path(tmpdir, "file2.py").touch()
        Path(tmpdir, "file3.txt").touch()

        # List all files
        result = await tool.execute(directory=tmpdir, recursive=False)
        assert result.success is True
        assert "file1.py" in result.data
        assert "file2.py" in result.data
        assert "file3.txt" in result.data

        # List only Python files
        result = await tool.execute(directory=tmpdir, pattern="*.py", recursive=False)
        assert result.success is True
        assert "file1.py" in result.data
        assert "file2.py" in result.data
        assert "file3.txt" not in result.data


@pytest.mark.asyncio
async def test_replace_in_file_tool():
    """Test replacing content in a file."""
    tool = ReplaceInFileTool()

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Hello, World!")
        temp_path = f.name

    try:
        result = await tool.execute(
            file_path=temp_path,
            search="World",
            replace="Python",
        )
        assert result.success is True

        # Verify replacement
        with open(temp_path, "r") as f:
            content = f.read()
            assert "Hello, Python!" == content
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
async def test_replace_in_file_not_unique():
    """Test replacing non-unique content fails."""
    tool = ReplaceInFileTool()

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("test test test")
        temp_path = f.name

    try:
        result = await tool.execute(
            file_path=temp_path,
            search="test",
            replace="replaced",
        )
        assert result.success is False
        assert "unique" in result.error.lower()
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
async def test_search_codebase_tool():
    """Test searching across codebase."""
    tool = SearchCodebaseTool()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files with content
        file1 = Path(tmpdir, "file1.py")
        file1.write_text("def hello():\n    print('Hello')\n")

        file2 = Path(tmpdir, "file2.py")
        file2.write_text("def world():\n    print('World')\n")

        # Search for "hello"
        result = await tool.execute(search_text="hello", directory=tmpdir)
        assert result.success is True
        assert "file1.py" in result.data
        assert "file2.py" not in result.data

        # Search for "print" (should find both)
        result = await tool.execute(search_text="print", directory=tmpdir)
        assert result.success is True
        assert "file1.py" in result.data
        assert "file2.py" in result.data
