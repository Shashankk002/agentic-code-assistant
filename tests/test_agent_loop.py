from llm.base import ChatMessage, LLMResponse, ToolCall
from agents.agent import Agent


class MockLLM:
    """A fake LLM that always requests a tool call, never finishing on its
    own -- used to force the agent loop into its max_iterations limit
    without burning real API calls."""

    def __init__(self):
        self.call_count = 0

    def generate(self, messages, tools=None):
        self.call_count += 1
        return LLMResponse(
            content=None,
            tool_calls=[ToolCall(name="noop", arguments={}, id=f"call_{self.call_count}")],
        )


class FinishingLLM:
    """A fake LLM that answers directly with no tool calls, on the first turn."""

    def generate(self, messages, tools=None):
        return LLMResponse(content="done", tool_calls=[])


class NullRegistry:
    def get_schemas(self):
        return []

    def is_destructive(self, name):
        return False

    def execute(self, name, arguments):
        return "noop result"


def test_agent_stops_at_max_iterations():
    llm = MockLLM()
    agent = Agent(llm=llm, tools=NullRegistry(), max_iterations=3, require_confirmation=False)

    result = agent.run("do something that never finishes")

    assert "maximum iteration limit" in result
    assert llm.call_count == 3


def test_agent_finishes_early_when_llm_stops_requesting_tools():
    agent = Agent(llm=FinishingLLM(), tools=NullRegistry(), max_iterations=10, require_confirmation=False)

    result = agent.run("a simple question")

    assert result == "done"


def test_agent_does_not_crash_on_llm_failure():
    class FailingLLM:
        def generate(self, messages, tools=None):
            raise RuntimeError("simulated API failure")

    agent = Agent(llm=FailingLLM(), tools=NullRegistry(), require_confirmation=False)

    result = agent.run("anything")

    assert "Agent stopped" in result
    assert "simulated API failure" in result
