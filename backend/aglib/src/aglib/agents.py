from typing import Any, Dict, List, Optional
from uuid import uuid4

from .client import Client, CompletionClient, Response
from .tools import FuncTool, ToolCall, ToolNotFoundError, ToolOutput
from .context import Context


# === AGENT ===


class Agent:
    def __init__(
        self,
        name: Optional[str] = None,
        *,
        system_prompt: str = None,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        client: Optional[CompletionClient] = None,
        tools: Optional[List[object]] = None,
        **kwargs,
    ):
        """Agent with a system prompt, tools, and a model.

        system_prompt is positional for ergonomics; other params are keyword-only.
        """
        self.name = name or "Agent"
        self.id = str(uuid4())
        self.system_prompt = system_prompt or getattr(self, "system_prompt", "")
        self.llm = client or Client.completion(provider=provider, model=model, **kwargs)
        self.tools: List[object] = tools or []

    def set_model(self, *, provider: str, model: str, **kwargs):
        """Allows dynamic changing of model."""
        self.llm = Client.completion(provider=provider, model=model, **kwargs)

    def request(self, context: Context, **kwargs) -> Response:
        messages = context.build_messages(self.system_prompt)
        return self.llm.request(messages=messages, tools=self.tools, system_prompt=None, **kwargs)

    def _find_tool(self, name: str) -> Optional[object]:
        for t in self.tools:
            if t.name == name:
                return t
        return None

    def execute_tools(self, tool_calls: List[ToolCall]) -> List[ToolOutput]: # TODO: consider moving this logic, include valid, to tool exec? What do you think?
        results: List[ToolOutput] = []
        for call in tool_calls:
            tool = self._find_tool(call.name)
            if tool is None:
                raise ToolNotFoundError(f"tool '{call.name}' not found.")
            if not isinstance(tool, FuncTool):
                results.append(ToolOutput(call_id=call.id, tool_name=call.name, content=None, error=None)) #TODO: handle Hosted or MCP calls.
            else:
                results.append(tool.execute(call))
        return results

    def has_tool_errors(self, outputs: List[ToolOutput]) -> bool:
        """Quick check to see if any tool calls failed."""
        return any(o.error for o in outputs)

    def get_tool_errors(self, outputs: List[ToolOutput]) -> List[str]:
        """Return error messages for failed tool calls."""
        return [str(o.error) for o in outputs if o.error]


