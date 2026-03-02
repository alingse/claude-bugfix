# Claude Bugfix - Quick Start Guide

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/claude-bugfix.git
   cd claude-bugfix
   ```

2. **Install with uv (recommended):**
   ```bash
   uv sync
   uv pip install -e .
   ```

3. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

## Basic Usage

### Fix a Bug

```bash
uv run claude-bugfix fix "Fix the division by zero error in calculator.py"
```

### Example Workflow

1. **Create a buggy file:**
   ```bash
   cat > bug.py << 'EOF'
   def divide(a, b):
       return a / b

   print(divide(10, 0))
   EOF
   ```

2. **Run the agent:**
   ```bash
   uv run claude-bugfix fix "Fix the division by zero error in bug.py"
   ```

3. **The agent will:**
   - Read the file
   - Identify the missing zero check
   - Propose a fix
   - Show you the diff
   - Wait for your approval

## Testing the Example

The repository includes an example buggy file at `examples/example_bug.py` with several common bugs:

```bash
# Try fixing one of the bugs
uv run claude-bugfix fix "Fix the division by zero error in examples/example_bug.py"
```

## Running Tests

```bash
# Run all tests
PYTHONPATH=src .venv/bin/python -m pytest tests/ -v

# Run specific test file
PYTHONPATH=src .venv/bin/python -m pytest tests/test_tools/test_file_operations.py -v
```

## Configuration

### Environment Variables

Required:
- `OPENAI_API_KEY`: Your OpenAI API key

Optional:
- `OPENAI_API_BASE`: API base URL (default: https://api.openai.com/v1)
- `OPENAI_MODEL`: Model to use (default: gpt-4)

### Config File

Create a custom config file:

```yaml
llm:
  model: "gpt-4"
  temperature: 0.1
  max_tokens: 4096

agent:
  max_iterations: 20
  max_tool_calls_per_iteration: 5

file_operations:
  max_file_size_mb: 10
  excluded_directories:
    - node_modules
    - .git
```

Use it:
```bash
uv run claude-bugfix fix "bug description" --config my_config.yaml
```

## Command Options

```bash
claude-bugfix fix [OPTIONS] BUG_DESCRIPTION

Options:
  -p, --path TEXT    Path to the codebase (default: current directory)
  -m, --model TEXT   LLM model to use (default: from config or env)
  -c, --config TEXT  Path to configuration file
  -v, --verbose      Enable verbose logging
```

## Troubleshooting

### "OPENAI_API_KEY environment variable is required"
- Make sure you've created a `.env` file with your API key
- Or export it: `export OPENAI_API_KEY=your_key_here`

### "Module not found" errors
- Run `uv sync` to install dependencies
- Run `uv pip install -e .` to install the package

### Tests failing
- Make sure to set PYTHONPATH: `PYTHONPATH=src`
- Use the venv python: `.venv/bin/python -m pytest`

## Next Steps

1. Try fixing bugs in your own codebase
2. Experiment with different models (gpt-3.5-turbo for faster/cheaper)
3. Customize the system prompt in `config/prompts/system_prompt.txt`
4. Add more tools to extend functionality

## Support

- Report issues: https://github.com/yourusername/claude-bugfix/issues
- Read the full README: [README.md](README.md)
