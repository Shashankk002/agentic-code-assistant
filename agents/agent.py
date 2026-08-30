from llm.base import BaseLLM, ChatMessage
from tools.registry import ToolRegistry
import json
import logging

logger = logging.getLogger("agent")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _file_handler = logging.FileHandler("agent_debug.log")
    _file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(_file_handler)
    logger.propagate = False  # never bubble up to the console


def _dump_messages(messages, path="debug_messages.json"):
    """Write the full message list to a JSON file for manual inspection."""
    serializable = [
        {
            "role": m.role,
            "name": getattr(m, "name", None),
            "content": m.content,
            "tool_call_id": getattr(m, "tool_call_id", None),
        }
        for m in messages
    ]
    with open(path, "w") as f:
        json.dump(serializable, f, indent=2)


def _debug_print_size(messages, iteration):
    """Log a running count of messages and approximate size, per loop iteration."""
    total_chars = sum(len(m.content or "") for m in messages)
    approx_tokens = total_chars // 4
    logger.debug(
        f"iteration {iteration}: {len(messages)} messages, "
        f"~{total_chars} chars, ~{approx_tokens} tokens (estimate)"
    )


CONTEXT_CHAR_THRESHOLD = 12_000   # ~3,000 tokens; tune based on your model's window
KEEP_RECENT_TOOL_MESSAGES = 3     # always leave the N most recent tool results untouched
TRUNCATE_TO_CHARS = 300           # how much of an older tool result survives compaction
_TRUNCATION_MARKER = "...[truncated to save context"


def _compact_messages(messages: list[ChatMessage]) -> None:
    """
    Once the running conversation exceeds CONTEXT_CHAR_THRESHOLD characters,
    shrink OLDER tool-result messages down to a short preview instead of
    their full content. Mutates messages in place.

    The most recent KEEP_RECENT_TOOL_MESSAGES tool results are always left
    full-size, since those are what the model is most likely to need
    verbatim on its very next step. This is truncation-based (not
    LLM-summarized): cheap, dependency-free, and if the model needs a
    truncated result's detail later, it can just re-call the tool.
    """
    total_chars = sum(len(m.content or "") for m in messages)
    if total_chars <= CONTEXT_CHAR_THRESHOLD:
        return

    tool_indices = [i for i, m in enumerate(messages) if m.role == "tool"]
    if len(tool_indices) <= KEEP_RECENT_TOOL_MESSAGES:
        return

    for i in tool_indices[:-KEEP_RECENT_TOOL_MESSAGES]:
        content = messages[i].content or ""
        if _TRUNCATION_MARKER in content or len(content) <= TRUNCATE_TO_CHARS:
            continue
        original_len = len(content)
        messages[i].content = (
            content[:TRUNCATE_TO_CHARS]
            + f"\n{_TRUNCATION_MARKER}; original was {original_len} chars. "
            "Re-call the tool if you need the full content.]"
        )


def _short_args(arguments: dict, max_len: int = 60) -> str:
    """Render tool arguments compactly for terminal display, truncating long values
    (file content, shell commands) so a single tool call doesn't flood the line."""
    parts = []
    for k, v in arguments.items():
        s = str(v)
        if len(s) > max_len:
            s = s[:max_len] + "..."
        parts.append(f"{k}={s!r}")
    return ", ".join(parts)


class Agent:
    def __init__(
        self,
        llm: BaseLLM,
        tools: ToolRegistry | None = None,
        system_prompt: str | None = None,
        max_iterations: int = 10,
        require_confirmation: bool = True,
    ):
        self.llm = llm
        self.tools = tools
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.require_confirmation = require_confirmation
        self._always_allowed: set[str] = set()  # tool names approved for the rest of this session

    def _confirm(self, tool_call) -> bool:
        """
        Permission gate for destructive tools (write_file, edit_file, run_command).
        Prints the proposed action and asks for y/n, with an "always" option that
        skips future prompts for that tool name for the rest of this run.
        Returns True if the call should proceed.
        """
        if not self.require_confirmation:
            return True
        if not (self.tools and self.tools.is_destructive(tool_call.name)):
            return True
        if tool_call.name in self._always_allowed:
            return True

        print(f"\n[PERMISSION] Agent wants to call: {tool_call.name}({_short_args(tool_call.arguments, max_len=200)})")
        choice = input("Allow? [y]es / [n]o / [a]lways allow this tool: ").strip().lower()

        if choice == "a":
            self._always_allowed.add(tool_call.name)
            return True
        return choice == "y"

    def run(self, prompt: str) -> str:
        """Run the agent loop until the task is complete or max_iterations is reached."""
        messages: list[ChatMessage] = []

        if self.system_prompt:
            messages.append(
                ChatMessage(role="system", content=self.system_prompt)
            )

        messages.append(ChatMessage(role="user", content=prompt))

        for iteration in range(self.max_iterations):
            _compact_messages(messages)
            _debug_print_size(messages, iteration)

            tools_schema = self.tools.get_schemas() if self.tools else None
            try:
                response = self.llm.generate(messages, tools=tools_schema)
            except Exception as e:
                # Don't let an API failure (rate limit, network issue, provider
                # outage) kill the whole interactive session -- the error
                # message itself already says what went wrong.
                _dump_messages(messages)
                return f"Agent stopped: the model call failed ({e})."

            if not response.tool_calls:
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=response.content or "",
                    )
                )
                _dump_messages(messages)
                return response.content or ""

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )

            for tool_call in response.tool_calls:
                logger.debug(f"[TOOL CALL] {tool_call.name}({tool_call.arguments})")

                if not self._confirm(tool_call):
                    tool_result = f"Tool call '{tool_call.name}' was denied by the user."
                elif self.tools:
                    tool_result = self.tools.execute(
                        tool_call.name, tool_call.arguments
                    )
                else:
                    tool_result = f"Tool '{tool_call.name}' could not be executed: No tool registry configured."

                logger.debug(f"[TOOL RESULT] {tool_call.name}: {tool_result}")
                print(f"  → {tool_call.name}({_short_args(tool_call.arguments)})")

                messages.append(
                    ChatMessage(
                        role="tool",
                        name=tool_call.name,
                        content=tool_result,
                        tool_call_id=tool_call.id,
                    )
                )

        _dump_messages(messages)
        return (
            "Agent stopped: maximum iteration limit "
            f"({self.max_iterations}) reached without completion."
        )