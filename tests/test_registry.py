from tools.registry import ToolRegistry, _coerce_arguments


def test_coerce_stringified_true_to_bool():
    schema = {"parameters": {"properties": {"recursive": {"type": "boolean"}}}}
    result = _coerce_arguments({"recursive": "True"}, schema)
    assert result["recursive"] is True


def test_coerce_stringified_false_to_bool():
    # The important case: a non-empty string is truthy in Python, so
    # "False" must be explicitly coerced or it silently behaves as True.
    schema = {"parameters": {"properties": {"overwrite": {"type": "boolean"}}}}
    result = _coerce_arguments({"overwrite": "False"}, schema)
    assert result["overwrite"] is False


def test_coerce_leaves_real_bool_unchanged():
    schema = {"parameters": {"properties": {"recursive": {"type": "boolean"}}}}
    result = _coerce_arguments({"recursive": False}, schema)
    assert result["recursive"] is False


def test_coerce_stringified_int():
    schema = {"parameters": {"properties": {"timeout": {"type": "integer"}}}}
    result = _coerce_arguments({"timeout": "45"}, schema)
    assert result["timeout"] == 45
    assert isinstance(result["timeout"], int)


def test_registry_execute_applies_coercion_end_to_end():
    schema = {
        "name": "fake_tool",
        "parameters": {"properties": {"flag": {"type": "boolean"}}},
    }
    captured = {}

    def fake_tool(flag=False):
        captured["flag"] = flag
        captured["flag_type"] = type(flag).__name__
        return "ok"

    registry = ToolRegistry()
    registry.register("fake_tool", fake_tool, schema)
    registry.execute("fake_tool", {"flag": "False"})

    assert captured["flag"] is False
    assert captured["flag_type"] == "bool"


def test_registry_destructive_flag_is_not_in_schema():
    # destructive must be registry-level metadata, never mixed into the
    # schema dict that gets sent to the LLM provider as a function
    # declaration -- providers reject unrecognized schema fields.
    schema = {"name": "run_command", "parameters": {"properties": {}}}
    registry = ToolRegistry()
    registry.register("run_command", lambda: "ok", schema, destructive=True)

    assert registry.is_destructive("run_command") is True
    assert "destructive" not in registry.get_schemas()[0]


def test_registry_unknown_tool_defaults_to_destructive():
    registry = ToolRegistry()
    assert registry.is_destructive("never_registered") is True
