# agentic-code-assistant

A terminal coding agent: give it a task in plain English and it reads files, searches
the codebase, edits or creates files, and runs shell commands through an LLM tool-calling
loop, asking for permission before anything destructive. Backed by Gemini; the provider
is behind a small interface.

```
User: can you list all the files in the current repo and the number of lines they
contain, and ignore the files inside .gitignore

  → read_file(file_path='.gitignore')
  → list_directory(recursive=True)

[PERMISSION] Agent wants to call: run_command(command='git ls-files | xargs wc -l')
Allow? [y]es / [n]o / [a]lways allow this tool: y
  → run_command(command='git ls-files | xargs wc -l')

Agent:
| File Path        | Line Count |
|------------------|------------|
| README.md        | 149        |
| agents/agent.py  | 199        |
...
```

## Architecture

```
main.py                 CLI entry point (interactive REPL or one-shot)
agents/agent.py         The loop: query the model, execute requested tools, repeat
llm/base.py             Provider-agnostic interface: BaseLLM, ChatMessage, ToolCall
llm/gemini.py           Gemini implementation of BaseLLM
tools/
  registry.py           name -> (function, schema, destructive) + argument coercion
  dispatcher.py         registers the default tool set
  read_file.py / write_file.py / edit_file.py
  list_directory.py     non-recursive by default, recursive=True walks the tree
  search_code.py        ripgrep-backed text search
  run_command.py        sandboxed shell execution
```

Each `Agent.run()` call is one loop: send the conversation plus tool schemas to the
model; if it returns tool calls, execute them (through the permission gate), append the
results, and go again; if it returns plain text, that's the answer. The loop stops after
`max_iterations` (default 10) model calls.

`BaseLLM` has a single abstract method, `generate()`. Swapping providers means
implementing that one method; the loop and tools don't change.

| Tool | Requires confirmation |
|---|---|
| `read_file`, `search_code`, `list_directory` | No |
| `write_file`, `edit_file`, `run_command` | Yes |

Whether a tool is destructive is set at registration time in `dispatcher.py`, not
hardcoded in the agent. Unregistered tool names are treated as destructive.

## Engineering decisions

**Diff-based editing.** `edit_file` replaces `old_text` only if it occurs exactly once in
the file. Zero or multiple matches return an error and leave the file untouched, so the
model has to supply more context rather than have the tool guess.

**Sandboxed shell execution.** `run_command` runs the command through `sh` in its own
process group with:

- a timeout, clamped to a 45 s ceiling regardless of what the model requests. On
  timeout the whole process group is killed, not just the shell, so a `sleep 100 | cat`
  doesn't leave `sleep` running after the tool reports failure.
- `RLIMIT_CPU` (10 s) and `RLIMIT_AS` (512 MB) set in the child via `preexec_fn`. Each
  limit is applied in its own `try/except`: macOS rejects `RLIMIT_AS`, and if that
  exception escaped, `subprocess` would fail the whole `preexec_fn` and the command would
  never run.
- a working-directory jail (`cwd` must resolve inside the repo root) and a 20k-char cap
  on captured output.

`RLIMIT_NPROC` was originally set too, as a fork-bomb guard. It was removed: the limit
counts every process owned by the user, not the command's subtree, so with a small value
the shell couldn't fork at all. Single commands still worked because `sh` `exec()`s them
directly, but pipelines and `a && b` failed with `fork: Resource temporarily unavailable`.
This showed up in a real session as an unexplained exit code 128 from `git ls-files |
while read f; ...`.

**Context compaction.** Before each model call, if the conversation exceeds 12k
characters, tool results older than the three most recent are truncated to a 300-char
preview with a marker telling the model to re-call the tool if it needs the detail. This
is truncation, not LLM summarization: no extra API call, no extra dependency.

**Argument coercion at the registry.** Gemini sometimes sends `"True"`/`"False"` as
strings. In Python `"False"` is truthy, so passing it straight through would silently
invert a flag like `overwrite`. The registry coerces string values to the type declared
in the tool's schema before calling the function, so individual tools don't have to.

**`destructive` is registry metadata, not schema.** The tool schema dict is sent to
Gemini verbatim as a function declaration, and Gemini rejects unknown fields. Putting
`destructive: true` in the schema broke the first request after it was added; it now
lives in the registry entry alongside the schema.

**Permission gate.** Destructive tool calls are printed and require `y`, `n`, or `a`
(always allow this tool for the session). `--yes` disables the gate. EOF at the prompt
counts as a denial, and the denial is fed back to the model as the tool result.

The terminal shows one `→ tool_name(...)` line per call. Full tool results, per-iteration
context size, and the final message list go to `agent_debug.log` and
`debug_messages.json` (both gitignored).

## Tests

```bash
pytest
```

23 tests, all offline (the agent loop is tested against fake LLMs):

- `test_edit_file.py` – unique-match replacement; ambiguous and missing matches leave the
  file untouched
- `test_registry.py` – string-to-bool/int coercion; `destructive` never leaks into schemas
- `test_compaction.py` – threshold, recent-message preservation, truncation markers
- `test_agent_loop.py` – iteration limit, early finish, model-call failure
- `test_run_command.py` – pipelines can fork, timeout kills child processes, workdir
  jail, output truncation, `rg` queries beginning with `-`

## Setup

Python 3.11+ and [ripgrep](https://github.com/BurntSushi/ripgrep) on `PATH`. Developed
and tested on macOS; the sandbox uses POSIX `resource` limits and `sh`, so Linux should
behave the same and Windows is untested (the code falls back to timeout-only there).

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

## Limitations

- The sandbox is not a security boundary. The workdir jail stops a command from
  *starting* outside the repo, but `ls /etc` inside the sandbox returns real system
  directory contents, and network access is unrestricted. A real boundary needs a
  container.
- `write_file` refuses paths outside the repo root; `read_file` and `edit_file` do not
  have the same check. The permission prompt shows the path for `edit_file`, but that is
  the only safeguard.
- `RLIMIT_AS` is rejected on macOS, so the memory cap only applies on Linux. The CPU cap
  applies on both.
- Only `run_command` output is capped. A very large `read_file` or `search_code` result
  is sent to the model in full on the turn it's produced; compaction only shrinks it on
  later turns.
- Each `run()` starts a fresh conversation, so interactive mode has no memory across
  turns.
- Compaction is truncation-based. If the model needs an old result it has to re-call
  the tool.
- The model has occasionally created a file to satisfy a task that referred to a
  nonexistent one. The only mitigation is a system-prompt instruction to ask instead.
