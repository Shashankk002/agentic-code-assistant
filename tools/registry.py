from typing import Any, Callable


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

        func, _ = self._tools[name]
        try:
            result = func(**arguments)
            return str(result)
        except TypeError as e:
            return f"Invalid arguments for tool '{name}': {e}"
        except Exception as e:
            return f"Error executing tool '{name}': {e}"
