# claude-bugfix

AI-Powered Code Repair Agent – Your autonomous debugging assistant powered by OpenAI.

## Overview

`claude-bugfix` is a Python-based coding agent that uses OpenAI's API to automatically analyze codebases, identify root causes of bugs, and propose fixes. It uses an agentic loop with tool calling to interact with your codebase through file operations.

## Features

- 🔍 **Intelligent Bug Analysis**: Uses GPT-4 to understand and analyze bugs
- 🛠️ **Tool-Based Interaction**: Reads, searches, and modifies files through a tool system
- 🎯 **Root Cause Identification**: Goes beyond symptoms to find the actual cause
- ✅ **Safe Changes**: Shows diffs before applying any modifications
- 🌐 **Language Agnostic**: Works with Python, JavaScript/TypeScript, Go, and more
- 🔄 **Iterative Problem Solving**: Agent loop continues until solution is found
- 📦 **Context Compression**: Automatically compresses conversation context when token usage is high or iterations exceed limits, allowing the agent to continue working on complex tasks

## Installation

### Prerequisites

- Python 3.10 or higher
- OpenAI API key
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/claude-bugfix.git
cd claude-bugfix

# Install dependencies with uv
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/yourusername/claude-bugfix.git
cd claude-bugfix

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package
pip install -e .

# Set up environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Configuration

Create a `.env` file with your OpenAI API credentials:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4
```

## Usage

### Basic Usage

```bash
# Fix a bug by describing it
uv run claude-bugfix fix "Fix the division by zero error in calculator.py"

# Or if installed with pip
claude-bugfix fix "Fix the division by zero error in calculator.py"
```

### Specify a Different Directory

```bash
claude-bugfix fix "Fix authentication bug" --path /path/to/project
```

### Use a Different Model

```bash
claude-bugfix fix "Fix the bug" --model gpt-3.5-turbo
```

### Verbose Output

```bash
claude-bugfix fix "Fix the bug" --verbose
```

## How It Works

1. **Exploration**: The agent uses `list_files` and `search_codebase` to understand your project structure
2. **Analysis**: It reads relevant files with `read_file` to understand the context
3. **Root Cause**: The agent identifies the actual cause of the bug, not just symptoms
4. **Fix Proposal**: It proposes minimal, targeted changes using `replace_in_file` or `write_file`
5. **Verification**: Shows you a diff of proposed changes before applying them

## Available Tools

The agent has access to these tools:

- **read_file**: Read file contents
- **write_file**: Create or overwrite files
- **list_files**: List files with glob pattern support
- **replace_in_file**: Make targeted replacements in files
- **search_codebase**: Search for text across the codebase

## Example

```bash
# Create a buggy file
cat > bug.py << 'EOF'
def divide(a, b):
    return a / b

print(divide(10, 0))
EOF

# Fix it
claude-bugfix fix "Fix the division by zero error in bug.py"
```

The agent will:
1. Read `bug.py`
2. Identify the missing zero check
3. Propose adding a check for `b == 0`
4. Show you the diff
5. Apply the fix after your approval

## Development

### Running Tests

```bash
# With uv
uv run pytest

# With pip
pytest
```

### Project Structure

```
claude-bugfix/
├── src/claude_bugfix/
│   ├── agent/          # Agent loop and state management
│   ├── llm/            # OpenAI client and configuration
│   ├── tools/          # File operation tools
│   ├── utils/          # Utilities (logging, file ops, diff viewer)
│   └── cli.py          # CLI interface
├── config/
│   ├── default_config.yaml
│   └── prompts/
│       └── system_prompt.txt
├── tests/              # Test suite
└── examples/           # Example buggy code
```

## Configuration File

You can customize behavior with a YAML config file:

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
    - __pycache__
```

Use it with: `claude-bugfix fix "bug description" --config my_config.yaml`

## Limitations

- Requires OpenAI API access (costs apply)
- Works best with well-structured codebases
- May need multiple iterations for complex bugs
- Limited by context window size (mitigated by automatic context compression)

### Context Compression

When the agent approaches token limits (64K) or maximum iterations (20), it automatically compresses conversation context by:
- Summarizing early tool results
- Extracting key findings and modified files
- Preserving recent context for continuity

This allows the agent to continue working on complex tasks that would otherwise exceed limits. See [docs/context_compression.md](docs/context_compression.md) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Acknowledgments

Built with:
- [OpenAI API](https://openai.com/api/) for LLM capabilities
- [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- [Click](https://click.palletsprojects.com/) for CLI interface
- [uv](https://github.com/astral-sh/uv) for fast Python package management
