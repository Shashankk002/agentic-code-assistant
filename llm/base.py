from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    id: str | None = None
    # Gemini thinking models attach an opaque signature to each function
    # call that must be echoed back on the next turn.
    thought_signature: Any | None = None


@dataclass
class ChatMessage:
    role: str  # "system", "user", "assistant", or "tool"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class BaseLLM(ABC):
    @abstractmethod
    def generate(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Return the model's reply to `messages`, given optional tool declarations."""
