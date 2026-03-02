# Contributing to Claude Bugfix

Thank you for your interest in contributing to Claude Bugfix!

## Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/yourusername/claude-bugfix.git
   cd claude-bugfix
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   uv pip install -e .
   ```

3. **Set up environment:**
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY for testing
   ```

## Running Tests

```bash
# Run all tests
PYTHONPATH=src .venv/bin/python -m pytest tests/ -v

# Run specific test file
PYTHONPATH=src .venv/bin/python -m pytest tests/test_tools/test_file_operations.py -v

# Run with coverage
PYTHONPATH=src .venv/bin/python -m pytest tests/ --cov=claude_bugfix --cov-report=html
```

## Code Style

We use:
- **Black** for code formatting
- **Ruff** for linting
- **Type hints** where appropriate

```bash
# Format code
uv run black src/ tests/

# Lint code
uv run ruff check src/ tests/
```

## Adding New Tools

To add a new tool:

1. Create a new class in `src/claude_bugfix/tools/` that inherits from `Tool`
2. Implement required properties: `name`, `description`, `parameters`
3. Implement the `execute` method
4. Register it in `src/claude_bugfix/cli.py` in the `create_tool_registry` function
5. Add tests in `tests/test_tools/`

Example:

```python
from claude_bugfix.tools.base import Tool, ToolParameter, ToolResult

class MyNewTool(Tool):
    @property
    def name(self) -> str:
        return "my_new_tool"

    @property
    def description(self) -> str:
        return "Description of what this tool does"

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="param1",
                type="string",
                description="Description of param1",
                required=True,
            )
        ]

    async def execute(self, param1: str) -> ToolResult:
        try:
            # Your tool logic here
            result = do_something(param1)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

## Project Structure

```
src/claude_bugfix/
├── agent/          # Agent loop and state management
├── llm/            # LLM client and configuration
├── tools/          # Tool implementations
├── utils/          # Utility functions
└── cli.py          # CLI interface
```

## Pull Request Process

1. Create a new branch for your feature: `git checkout -b feature/my-feature`
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass
5. Update documentation if needed
6. Commit with clear messages
7. Push to your fork
8. Create a Pull Request

## Commit Message Guidelines

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues and pull requests liberally

Examples:
- `Add support for TypeScript files`
- `Fix division by zero in calculator`
- `Update README with new examples`

## Areas for Contribution

### High Priority
- [ ] Interactive REPL mode
- [ ] Diff approval workflow with user confirmation
- [ ] Git integration (auto-commit fixes)
- [ ] Support for more programming languages

### Medium Priority
- [ ] Tree-sitter integration for AST analysis
- [ ] Test generation for fixed code
- [ ] Multi-file fix coordination
- [ ] Caching for repeated operations

### Low Priority
- [ ] Web UI
- [ ] Plugin system for custom tools
- [ ] Learning system to store successful patterns
- [ ] Integration with popular IDEs

## Questions?

Feel free to open an issue for:
- Bug reports
- Feature requests
- Questions about the codebase
- Suggestions for improvements

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
