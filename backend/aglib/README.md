# aglib

Lightweight agent toolkit providing a minimal, stable API:

- `Agent`: wraps a model selection, tools, and a base system prompt.
- `Context`: manages full `history` and per-turn `frame` for message building.
- `Response` / `EmbeddingResponse`: minimal wrappers around provider payloads.
- `tools`: function-style tools via `FuncTool`.

Dev layout:

aglib/
├── pyproject.toml
├── src/
│   └── aglib/
│       ├── __init__.py
│       ├── agents.py
│       ├── client.py
│       ├── context.py
│       └── tools.py


## Quick Start (aglib)

Minimal tool + agent + context example:

```python
from aglib import Agent, Client, Context
from aglib.tools import FuncTool

class EchoTool(FuncTool):
    def __init__(self):
        super().__init__(
            name="EchoTool",
            description="Echoes text; uppercases if it contains 'agent'",
            schema={
                "arguments": {
                    "text": {"type": "string"},
                    "uppercase": {"type": "boolean", "default": False},
                },
                "required": ["text"],
            },
        )

    def func(self, text: str, uppercase: bool = False):
        return text.upper() if "agent" in text.lower() else text
agent = Agent(
    "You are a helpful agent.",
    tools=[EchoTool()],
    provider="openai",
    model="gpt-4o-mini",
)

ctx = Context()
ctx.clear()  # start clean frame
ctx.add_instruction("Objective: repeat the user's message; use tools if needed.")
ctx.add_user_query("Hello there, little agent!")

# Make the request
resp = agent.request(ctx, tool_choice="required")
ctx.add_model_response(resp)

# Execute tools if any
outs = agent.execute_tools(resp.tool_calls)
ctx.add_tool_outputs(outs)
```

Direct client usage when an Agent is unnecessary:

```python
llm = Client.completion(provider="mistral", model="mistral-medium-latest")
resp = llm.request(messages=[{"role": "user", "content": "Hello!"}])
print(resp.content)
```

Bring forward prior results to the next turn:

```python
# Distilled (default): single system message summarizing prior tool outputs
ctx.include_tool_outputs(outs, mode="content")

# Or full tool messages (more tokens, more structure)
ctx.include_tool_outputs(outs, mode="full")
```

Multi‑agent handoff (pattern):

```python
# After finishing Agent A
prev_outs = outs

# Prepare frame for Agent B
ctx.clear()
ctx.add_instruction("Objective for Agent B: plan next steps.")
ctx.include_tool_outputs(prev_outs, mode="content")
resp_b = agent_b.request(ctx)
```

Notes:
- `Context.history` retains the full log; `Context.frame` is only what the LLM sees this turn (plus the system message).
- Multiple system messages are supported and are sent in order; if a provider only accepts one, collapse in the adapter layer.
