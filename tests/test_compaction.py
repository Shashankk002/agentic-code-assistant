from llm.base import ChatMessage
from agents.agent import _compact_messages, CONTEXT_CHAR_THRESHOLD, KEEP_RECENT_TOOL_MESSAGES


def _make_messages_over_threshold():
    messages = [
        ChatMessage(role="system", content="system prompt"),
        ChatMessage(role="user", content="do a big task"),
    ]
    # Enough large tool results to exceed CONTEXT_CHAR_THRESHOLD.
    per_message_size = (CONTEXT_CHAR_THRESHOLD // 5) + 100
    for i in range(8):
        messages.append(ChatMessage(role="assistant", content=None))
        messages.append(
            ChatMessage(role="tool", name="read_file", content="x" * per_message_size)
        )
    return messages


def test_compaction_does_nothing_under_threshold():
    messages = [
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="tool", name="read_file", content="short content"),
    ]
    original = messages[1].content
    _compact_messages(messages)
    assert messages[1].content == original


def test_compaction_shrinks_total_size_over_threshold():
    messages = _make_messages_over_threshold()
    before = sum(len(m.content or "") for m in messages)

    _compact_messages(messages)

    after = sum(len(m.content or "") for m in messages)
    assert after < before


def test_compaction_preserves_most_recent_tool_messages():
    messages = _make_messages_over_threshold()
    tool_messages_before = [m.content for m in messages if m.role == "tool"]

    _compact_messages(messages)

    tool_messages_after = [m for m in messages if m.role == "tool"]
    # The most recent KEEP_RECENT_TOOL_MESSAGES must be untouched.
    for original, current in zip(
        tool_messages_before[-KEEP_RECENT_TOOL_MESSAGES:],
        tool_messages_after[-KEEP_RECENT_TOOL_MESSAGES:],
    ):
        assert current.content == original


def test_compaction_marks_truncated_messages():
    messages = _make_messages_over_threshold()
    _compact_messages(messages)

    tool_messages = [m for m in messages if m.role == "tool"]
    older_ones = tool_messages[:-KEEP_RECENT_TOOL_MESSAGES]
    assert any("truncated" in (m.content or "") for m in older_ones)
