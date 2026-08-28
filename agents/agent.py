from llm.base import BaseLLM, ChatMessage
from tools.registry import ToolRegistry
import json


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
    """Print a running count of messages and approximate size, per loop iteration."""
    total_chars = sum(len(m.content or "") for m in messages)
    # Rough rule of thumb: ~4 characters per token for English text/code.
    approx_tokens = total_chars // 4
    print(
        f"[DEBUG] iteration {iteration}: {len(messages)} messages, "
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


class Agent:
    def __init__(
        self,
        llm: BaseLLM,
        tools: ToolRegistry | None = None,
        system_prompt: str | None = None,
        max_iterations: int = 10,
    ):
        self.llm = llm
        self.tools = tools
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations

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
            response = self.llm.generate(messages, tools=tools_schema)

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
                if self.tools:
                    tool_result = self.tools.execute(
                        tool_call.name, tool_call.arguments
                    )
                else:
                    tool_result = f"Tool '{tool_call.name}' could not be executed: No tool registry configured."

                print(f"[TOOL RESULT] {tool_call.name}: {tool_result}")

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