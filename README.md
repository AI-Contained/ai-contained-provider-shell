# ai-contained-provider-shell

A shell provider for [AI-Contained](https://github.com/AI-Contained) giving your AI agent controlled, privilege-dropped access to run shell commands, with elicitation-based user approval for every execution.

## Tools

### `read_bash` — run read-only shell commands

Runs an arbitrary shell command via `/bin/sh -c` and returns stdout, stderr, and exit status. Intended for read-only operations such as inspection, searching, and listing.

Every invocation requires explicit user approval via elicitation (tagged `shell::read`). The command is executed through [`downgrade_exec`](#downgrade_exec), which locks the process identity and optionally asserts filesystem access constraints before running.

**Parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `command` | string | yes | Shell command to run. Supports pipes, redirects, `&&`, subshells, etc. |
| `working_dir` | string | no | Directory to run in (default: cwd). Shown as a relative path in the elicitation. |
| `summary` | string | no | Human-readable description shown beneath the elicitation prompt. |

**Return value (JSON)**

```json
{ "exit_status": "0", "stdout": "...", "stderr": "..." }
```

> `exit_status` is always a string. A non-zero exit status does **not** set `is_error=true` — always check it explicitly.

---

### `write_command` — run a single program directly

Runs a single program without a shell. Intended for write operations such as copying, moving, and creating files. Arguments are passed directly to the binary — no shell expansion, no glob expansion.

A blocklist of shells, interpreters, and read-only utilities is enforced. Both the supplied command name and the resolved binary name are checked.

Every invocation requires explicit user approval via elicitation (tagged `shell::write`, shown in red in color-enabled terminals).

**Parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `command` | string | yes | Program to run (name or absolute path). Resolved via `PATH`. |
| `arguments` | list[string] | no | Arguments passed directly to the program (default: `[]`). |
| `working_dir` | string | no | Directory to run in (default: cwd). |
| `environment` | dict[string, string] | no | Additional environment variables. Values support `$VAR` expansion. |
| `summary` | string | no | Human-readable description shown beneath the elicitation prompt. |

**Return value (JSON)**

```json
{ "exit_status": "0", "stdout": "...", "stderr": "..." }
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DOWNGRADE_EXEC` | *(searched via `PATH`, then `/usr/local/bin/downgrade_exec`)* | Path to the `downgrade_exec` binary used by `read_bash`. Point to a pass-through stub to disable privilege dropping in development. |
| `DOWNGRADE_ARGS` | `--check=writable` | Arguments passed to `downgrade_exec` before `--`. Set to an empty string to skip all permission checks. See [`downgrade_exec`](#downgrade_exec) for valid values. |
| `COLOR` | `ascii` | Set to `ascii` to enable ANSI color in elicitation prompts. Any other value disables color. |

---

## `downgrade_exec`

`downgrade_exec` is a small Go binary that locks the process to its current effective UID/GID (all three of real, effective, and saved) before executing a command. It must **not** be run as root — it is designed to run as an already-unprivileged user (typically UID/GID 65534, `nobody`) and prevent any subsequent privilege escalation.

**Synopsis**

```
downgrade_exec [--chdir=<path>] [--check=<modes>] -- <program> [args...]
```

**Flags**

| Flag | Description |
|---|---|
| `--chdir=<path>` | Change to `path` before running `--check` or exec. |
| `--check=writable` | Fail if any paths under the working directory are writable by the running identity. |
| `--check=unreadable` | Fail if any paths under the working directory are unreadable by the running identity. |
| `--check=writable,unreadable` | Apply both checks. |
| *(omitted)* | No permission check is performed. |

If `--check` finds violations the process exits with code 3 and prints the offending paths to stderr. The command is never executed.

**Exit codes**

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Usage error |
| 2 | Security error (e.g. called as root) |
| 3 | Permission check violations found |
| 4 | Runtime error (chdir, exec, etc.) |

---

## Installation

### Local development

```bash
uv sync --extra dev
```

### Production

```bash
uv pip install "ai-contained-provider-shell @ git+https://github.com/AI-Contained/ai-contained-provider-shell.git@main"
```

## Running tests

```bash
uv run pytest
```
