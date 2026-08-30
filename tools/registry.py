from typing import Any, Callable


def _coerce_arguments(arguments: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """
    Coerce string-typed argument values to match their declared schema type,
    where the LLM sent e.g. "True"/"false"/"3" as a string instead of a real
    bool/int. This happens in practice -- some models stringify JSON values
    inconsistently -- and it's a real footgun: in Python, ANY non-empty
    string (including the string "False") is truthy, so passing a stringified
    boolean through unchanged can silently invert the caller's intent.
    """
    properties = schema.get("parameters", {}).get("properties", {})
    coerced = dict(arguments)

    for key, value in arguments.items():
        expected_type = properties.get(key, {}).get("type")
        if not isinstance(value, str):
            continue  # already the right kind of value, nothing to coerce

        if expected_type == "boolean":
            lowered = value.strip().lower()
            if lowered in ("true", "false"):
                coerced[key] = lowered == "true"
        elif expected_type == "integer":
            try:
                coerced[key] = int(value)
            except ValueError:
                pass  # leave as-is; the tool's own error handling will catch it
        elif expected_type == "number":
            try:
                coerced[key] = float(value)
            except ValueError:
                pass

    return coerced


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, tuple[Callable[..., Any], dict[str, Any]]] = {}

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        schema: dict[str, Any],
    ) -> None:
        """Register a tool with its execution function and schema."""
        self._tools[name] = (func, schema)

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get the JSON schemas of all registered tools."""
        return [schema for _, schema in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name with arguments and return a string result."""
        if name not in self._tools:
            return f"Unknown tool: {name}"

        func, schema = self._tools[name]
        arguments = _coerce_arguments(arguments, schema)
        try:
            result = func(**arguments)
            return str(result)
        except TypeError as e:
            return f"Invalid arguments for tool '{name}': {e}"
        except Exception as e:
            return f"Error executing tool '{name}': {e}"