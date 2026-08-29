# agentic-code-assistant

A CLI coding agent — read, search, edit, and run code in a repository through an LLM-driven
tool-calling loop, in the spirit of Claude Code / Cursor's agent mode.

This isn't a tutorial clone. It started from studying that pattern, but every tool here was
extended, hardened, or added after finding a real bug or gap through actual testing — not just
built and left alone. See [Engineering notes](#engineering-notes) below for specifics.

## What it does

Give it a task in plain English and it will read files, search the codebase, make targeted edits,
create new files, and run shell commands — deciding for itself which tools to call and in what
order, retrying when a tool call fails, until the task is done.

```
User: read every file in tools/, summarize each one, then tell me which has the most lines

Agent: [calls list_directory, then read_file nine times, then run_command('wc -l tools/*.py')]

Here is a summary of every file in the `tools/` directory...
...
`tools/schemas.py` has the most lines with 143 lines (closely followed by `run_command.py`, 137).
```

## Why this is more than a basic agent loop

Most "build your own coding agent" tutorials stop at: LLM asks for a tool, run it, repeat. This
project pushes past that baseline in four specific ways:

- **Diff-based editing, not full-file overwrites.** `edit_file` requires the text being replaced
  to match *exactly once* in the file — if it's ambiguous or missing, it refuses and asks for more
  context instead of guessing. This is the same safety mechanism real coding agents use to avoid
  silently corrupting the wrong part of a file.
- **Sandboxed command execution.** `run_command` enforces a wall-clock timeout, CPU/memory/process
  resource limits, and a working-directory jail that stops commands from operating outside the
  repo root. Timeout and resource limits are independent layers — one failing doesn't take down
  the other (see engineering notes: this distinction was not academic).
- **Context compaction.** Long sessions truncate older tool results once the conversation crosses
  a size threshold, so multi-step tasks over large codebases don't silently blow the model's
  context window. The most recent results are always kept in full.
- **A complete-enough toolset to avoid dangerous workarounds.** Early versions lacked a way to
  create new files or list a directory's contents — which meant the model would either get stuck
  or improvise unsafe workarounds through the shell. Both gaps were found through testing and
  closed with dedicated tools (see below).

## Architecture

```
main.py                 Entry point: wires an LLM + tool registry into an Agent, runs a prompt
agents/agent.py          The tool-calling loop: ask LLM -> execute requested tools -> repeat
llm/base.py              Provider-agnostic interface (BaseLLM, ChatMessage, ToolCall)
llm/gemini.py            Gemini implementation of BaseLLM
tools/                   Each tool is a plain function; schemas.py describes them to the LLM
  registry.py             Name -> (function, schema) map; executes tools, catches exceptions
  dispatcher.py           Wires up the default set of tools
  read_file.py            Read a file's contents
  write_file.py           Create a file, or fully overwrite one
  edit_file.py            Replace a unique text snippet in an existing file
  list_directory.py       Non-recursive directory listing, noise-filtered
  search_code.py          ripgrep-backed text search across files
  run_command.py          Sandboxed shell command execution
```

The LLM layer is provider-agnostic by design — `BaseLLM` is an abstract interface with one method
(`generate`). Swapping Gemini for another provider means writing one new file, not touching the
agent loop or tools.

## Available tools

| Tool | Purpose |
|---|---|
| `read_file` | Read a file's full contents |
| `write_file` | Create a new file, or fully overwrite an existing one |
| `edit_file` | Replace a unique occurrence of text in an existing file |
| `list_directory` | List a directory's immediate contents (noise-filtered) |
| `search_code` | Search across files by text pattern (via ripgrep) |
| `run_command` | Run a sandboxed shell command (timeout, resource limits, path jail) |

## Setup

Requires Python 3.11+ and [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) installed and on
your `PATH` (`brew install ripgrep` on macOS, `apt install ripgrep` on Debian/Ubuntu).

```bash
git clone <your-repo-url>
cd agentic-code-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your real GEMINI_API_KEY
```

## Usage

```bash
python main.py
```

> Currently runs a single hardcoded prompt in `main.py` while the interactive CLI is in progress.
> Edit the `prompt` variable in `main.py` to try your own task in the meantime.

Set `DEBUG=1` (or however you wire up the debug flag) to see per-iteration message counts and
size estimates, plus a full `debug_messages.json` dump of the conversation after each run — useful
for understanding what the agent actually did, not just what it says it did (see engineering notes
on why that distinction matters).

## Engineering notes

A few things worth calling out, found and fixed through actual testing rather than assumed to work:

- **A resource-limit bug that only showed up on macOS.** Setting `RLIMIT_AS` (memory) and
  `RLIMIT_NPROC` (process count) in one unguarded block meant that on macOS — where these limits
  are unreliable — the whole `preexec_fn` would fail and kill otherwise-harmless commands like
  `sleep 40`. Fixed by applying each resource limit independently with its own try/except, so an
  unsupported limit on a given platform is skipped rather than aborting the command. CPU limits
  (which *are* reliably supported cross-platform) were confirmed working by intentionally killing
  a CPU-bound infinite loop and checking the exit code decoded to `SIGXCPU`.
- **A model-hallucination bug, not a code bug.** A timed-out `run_command` call once produced a
  final summary claiming the command "finished successfully" — the tool's return value was
  correct, but the model's own recap of it wasn't. Traced with per-tool-call debug logging (every
  raw tool result is printed and saved, not just the model's final answer), and mitigated with an
  explicit system-prompt instruction to cross-check tool output before summarizing.
- **A missing-tool bug that looked like flakiness at first.** Asking the agent to edit a file that
  didn't exist yet worked inconsistently — because there was no `write_file` tool, so success
  depended on the model happening to improvise a shell workaround. Fixed by adding a dedicated
  `write_file` tool with the same path-jail safety as `run_command`.
- **An iteration-budget bug caused by a missing tool, not bad luck.** A multi-file summarization
  task once hit the max-iteration limit — not because of task complexity, but because the model
  burned 4 of its 10 iterations trying to grep its way to a directory listing (`search_code`
  requires a text pattern; it isn't built for enumeration). Fixed by adding a dedicated
  `list_directory` tool and updating the system prompt to point at it explicitly.

## Known limitations

- `run_command`'s sandboxing is process-level (timeout, resource limits, directory jail), not a
  real security boundary — commands can still read/write/delete anything inside the allowed
  working directory, and network access is unrestricted. A stronger boundary would mean running
  commands inside a container.
- Context compaction is truncation-based, not LLM-summarized: older tool results are shortened to
  a preview rather than intelligently condensed. If the model needs detail from a truncated
  result, it re-calls the tool — a deliberate simplicity/cost trade-off, not an oversight.
- No automated test suite yet in this repo (in progress).

## Roadmap

- [ ] Interactive CLI entrypoint (currently single hardcoded prompt in `main.py`)
- [ ] Re-introduce a test suite (mocked-LLM tests for the agent loop, unit tests per tool)
- [ ] Optional: container-based sandboxing for `run_command` as a stronger security boundary