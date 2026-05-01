# ai-contained-provider-shell

A shell provider for [AI-Contained](https://github.com/AI-Contained) giving your AI agent controlled access to run bash commands, with elicitation-based user approval for every execution.

## Tools

- **`execute_bash`** - Execute a bash command and return stdout, stderr, and exit status. Requires user approval via elicitation before running.

## Installation

### Local Development

```bash
pip install -e ".[dev]" --break-system-packages
```

### Production

```bash
pip install "ai-contained-provider-shell @ git+https://github.com/AI-Contained/ai-contained-provider-shell.git@main"
```

## Running Tests

```bash
pytest -v
```
