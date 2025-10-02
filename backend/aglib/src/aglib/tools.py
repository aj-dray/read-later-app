from typing import Any, Dict, Optional
from dataclasses import dataclass


# === TYPES ===


class ToolValidationError(Exception):
    pass


class ToolNotFoundError(Exception):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolOutput:
    """Typed result for a tool execution."""
    call_id: str
    tool_name: str
    content: Any
    error: Optional[str] = None


# === BASE TOOL TYPES ===


class HostedTool:
    """Placeholder for non-local provider tools (e.g., web_search).

    # TODO: Define a minimal common interface if/when hosted tools are executed locally.
    """


class MCPTool:
    """Placeholder for MCP server-backed tools.

    # TODO: Define shape for MCP config to include server details and allowed tools.
    """


class FuncTool:
    """Function-style local tool with required name, description, and schema.

    Subclassing pattern (keep it simple):
    - Set `self.schema` in __init__ to a dict: {"args": {...}, "required": [...]} 
    - Implement `func(self, **kwargs)` to perform the action.
    - Optionally implement `validate(self, args)` for extra checks; default is no-op.
    """

    def __init__(self, name: str, description: str, schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.schema = schema

    def _validate_types_and_defaults(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Extract schema elements
        if not self.schema:
            raise ToolValidationError(f"tool '{self.name}' must define a schema")
        schema = self.schema or {}
        props: Dict[str, Dict[str, Any]] = dict(schema.get("args", {}) or {})
        required = list(schema.get("required", []) or [])

        # Apply defaults
        new_args = dict(args or {})
        for key, meta in props.items():
            if key not in new_args and isinstance(meta, dict) and "default" in meta:
                new_args[key] = meta["default"]

        # Required checks
        for r in required:
            if r not in new_args:
                raise ToolValidationError(f"missing required arg '{r}' for tool '{self.name}'")

        # Type checks
        for key, val in list(new_args.items()):
            meta = props.get(key)
            if not meta:
                # ignore extras for now
                continue
            expected = meta.get("type")
            if expected is None:
                continue
            if expected == "string" and not isinstance(val, str):
                raise ToolValidationError(f"arg '{key}' must be string for tool '{self.name}'")
            if expected == "number" and not isinstance(val, (int, float)):
                raise ToolValidationError(f"arg '{key}' must be number for tool '{self.name}'")
            if expected == "integer" and not isinstance(val, int):
                raise ToolValidationError(f"arg '{key}' must be integer for tool '{self.name}'")
            if expected == "boolean" and not isinstance(val, bool):
                raise ToolValidationError(f"arg '{key}' must be boolean for tool '{self.name}'")
            if expected == "object" and not isinstance(val, dict):
                raise ToolValidationError(f"arg '{key}' must be object for tool '{self.name}'")
            if expected == "array" and not isinstance(val, list):
                raise ToolValidationError(f"arg '{key}' must be array for tool '{self.name}'")

        return new_args

    def _validate(self, **kwargs) -> Dict[str, Any]:
        """Validate and sanitize tool arguments before execution."""
        args = self._validate_types_and_defaults(kwargs)
        self.validate(args)
        return args

    def execute(self, call: ToolCall) -> Any:
        try:
            validated = self._validate(**call.arguments)
            content = self.func(**validated)
            return ToolOutput(call_id=call.id, tool_name=call.name, content=content, error=None)
        except Exception as e:
            return ToolOutput(call_id=call.id, tool_name=call.name, content=None, error=str(e))

    # TODO: required methods for subclasses
    def func(self, **kwargs) -> Any:
        raise NotImplementedError("FuncTool.func() must be implemented by subclasses")

    def validate(self, args: Dict[str, Any]) -> None:
        # optional override
        return None


# === EXAMPLE TOOL (for reference only) ===

'''
class EchoTool(FuncTool):
    """Example FuncTool implementation."""

    def __init__(self):
        super().__init__(name="echo", description="Echo text back")
        self.schema = {
            "args": {
                "text": {"type": "string", "description": "Text to echo back"},
                "uppercase": {"type": "boolean", "description": "Uppercase the text", "default": False},
            },
            "required": ["text"],
        }

    def func(self, text: str, uppercase: bool = False) -> str:
        output = text.upper() if uppercase else text
        return output
'''


