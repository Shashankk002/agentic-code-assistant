# agentic-code-assistant

A terminal coding agent that reads files, searches a codebase, edits content, and runs
shell commands through an LLM-driven tool-calling loop, in the style of Claude Code's
agent mode.

## Overview

The agent accepts a task in plain English and reads files, searches the codebase, edits
content, creates new files, and runs shell commands autonomously — deciding what to call
and in what order, requesting permission before anything destructive, and retrying when
a step fails.

Example session, unedited:

```
User: can you list all the files in the current repo and the number of lines they
contain, and ignore the files inside .gitignore

[the agent reads .gitignore, cross-references it against the tracked files, requests
permission to run a script that counts lines, and executes it once approved]

Agent: Here is the list of all tracked files in the repository (ignoring files
specified in .gitignore), along with their line counts:

| File Path              | Line Count |
|-------------------------|------------|
| README.md               | 149        |
| agents/agent.py          | 199        |
| tools/run_command.py     | 138        |
...
```

## What distinguishes this from a basic agent loop

Most introductory "build a coding agent" guides stop at: the model requests a tool, the
tool runs, the cycle repeats. This project goes further in four specific respects:

- **Diff-based editing.** `edit_file` only modifies a file when the text being replaced
  matches *exactly once*. If the match is ambiguous, it refuses rather than guessing —
  the same safeguard production coding agents use to avoid corrupting the wrong section
  of a file.
- **Sandboxed shell execution.** `run_command` enforces a timeout, CPU/memory/process
  limits, and restricts the directory a command can start from. This is not a complete
  security boundary (see Known Limitations), but it is a substantial improvement over
  unguarded `subprocess.run`.
- **Context compaction.** Long sessions truncate older tool results once the
  conversation exceeds a size threshold, preventing multi-file tasks from silently
  exceeding the model's context window. This behavior was verified live during a
  nine-file summarization task.
- **A permission gate.** Before `write_file`, `edit_file`, or `run_command` executes,
  the proposed call is shown and confirmation is required. Approving a tool with "always
  allow" suppresses further prompts for that tool for the remainder of the session.

The terminal output is intentionally minimal: each tool call is shown as a single
`→ tool_name(...)` line. Verbose detail — per-iteration size tracking and full tool
results — is written to `agent_debug.log` instead, keeping the terminal readable without
discarding any information.

## Architecture

```
main.py                 CLI entry point (interactive REPL or one-shot)
agents/agent.py          The loop: query the model, execute requested tools, repeat
llm/base.py              Provider-agnostic interface -- BaseLLM, ChatMessage, ToolCall
llm/gemini.py             Gemini implementation of BaseLLM
tools/
  registry.py             name -> (function, schema, destructive) + argument coercion
  dispatcher.py           wires up the default set of tools
  read_file.py / write_file.py / edit_file.py
  list_directory.py       non-recursive by default, recursive=True walks the tree
  search_code.py          ripgrep-backed text search
  run_command.py          sandboxed shell execution
```

`BaseLLM` exposes a single abstract method, `generate()`, by design. Replacing Gemini
with another provider requires only a new implementation of this interface — the agent
loop and tools remain unchanged.

## Tools

| Tool | Function | Requires confirmation |
|---|---|---|
| `read_file` | Reads a file | No |
| `search_code` | Searches files via ripgrep | No |
| `list_directory` | Lists a directory (optionally recursive, noise-filtered) | No |
| `write_file` | Creates a file, or overwrites one entirely | **Yes** |
| `edit_file` | Replaces a unique text snippet within a file | **Yes** |
| `run_command` | Executes a sandboxed shell command | **Yes** |

The distinction between destructive and non-destructive tools is not hardcoded into the
agent itself; it is set at registration time (`dispatcher.py`), so introducing a new
destructive tool does not require modifying `agent.py`.

## Setup

Requires Python 3.11+ and [ripgrep](https://github.com/BurntSushi/ripgrep) on the system
`PATH` (`brew install ripgrep`, or `apt install ripgrep`).

```bash
git clone <your-repo-url>
cd agentic-code-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add a real GEMINI_API_KEY
```

## Usage

```bash
python main.py                            # interactive
python main.py "list files in tools/"     # one-shot
python main.py "fix the bug" --yes        # skip permission prompts
```

In interactive mode, type `exit` or `quit` to end the session.

## Engineering notes

The following issues were identified and resolved through direct testing rather than
assumed to work correctly.

- **A macOS-specific resource-limit failure.** CPU, memory, and process-count limits
  on `run_command` were originally set in a single block. On macOS, memory and
  process-count limits are not reliably supported, so setting them raised an exception
  that terminated the *entire* command — including harmless ones such as `sleep 40`.
  Resolved by wrapping each limit in its own try/except, so an unsupported limit is
  skipped rather than aborting the command. The CPU limit was separately confirmed to
  function correctly by terminating a busy-loop and verifying the exit code decoded to
  `SIGXCPU`.
- **An inaccurate model-generated summary of a tool result.** A timed-out `run_command`
  call was once summarized by the model as having "finished successfully," despite the
  tool's actual return value correctly indicating a timeout. This was identified only
  because every raw tool result was logged, not just the model's final answer. Mitigated
  with an explicit instruction requiring the model to verify tool output before
  summarizing it.
- **Inconsistent behavior traced to missing tools, not randomness.** Editing a file that
  did not yet exist succeeded inconsistently, because no `write_file` tool existed;
  success depended on the model improvising a shell-based workaround. A comparable issue
  affected directory listing, where the absence of a dedicated tool caused the model to
  exhaust iterations attempting to approximate one using `search_code`. Both were
  resolved by introducing dedicated tools once the pattern was identified.
- **Stringified boolean arguments producing incorrect behavior.** The model occasionally
  passed `"True"`/`"False"` as strings rather than native booleans. In Python, any
  non-empty string evaluates as truthy — including the string `"False"` — which could
  silently invert a flag such as `overwrite` without raising an error. Resolved by
  coercing argument types against each tool's schema at the registry level, rather than
  within individual tool implementations.
- **An internal metadata field breaking the provider API call.** A `destructive: true`
  flag was initially added directly to each tool's schema dictionary so the permission
  gate could reference it. That same dictionary is sent to Gemini as a function
  declaration, and Gemini's schema validation rejects unrecognized fields. The first
  request following this change failed outright. Resolved by storing `destructive` as
  separate registry metadata, set at registration time, and never merged into the schema
  transmitted to the provider.
- **The agent fabricated a file it was not asked to create.** When instructed to edit "a
  file where 'foo' appears twice" and no such file existed, the agent created one to
  satisfy the request rather than asking for clarification. A complete fix is still
  pending; the current mitigation is a system-prompt instruction directing the model to
  ask rather than invent content when a task references a file or condition that does
  not exist.

## Known limitations

- `run_command`'s sandboxing is genuine but does not constitute a security boundary.
  This was confirmed directly: `ls /etc` executed within the sandbox returned real
  system directory contents. The working-directory restriction prevents a command from
  *starting* outside the repository, but does not prevent an absolute path referenced
  *within* the command. A genuine boundary would require containerized execution.
- Compaction is truncation-based rather than summarization-based. Older tool results are
  shortened to a preview rather than condensed with an additional model call. If
  detail is later required, the tool is simply re-invoked — a deliberate trade-off for
  simplicity, not an oversight.
- No automated test suite exists yet. All behavior described above was verified manually
  across repeated runs, which is how these issues were found, but this does not provide
  the same guarantee against regression as automated testing would.

## Planned work

- [ ] A minimal test suite covering `edit_file`'s ambiguous-match rejection, compaction
      behavior, argument coercion, and the agent loop's iteration limit under a mocked LLM
- [ ] A more robust fix for the fabrication behavior described above
- [ ] Possible future work: container-based sandboxing for `run_command`