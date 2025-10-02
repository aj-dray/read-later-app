from typing import Any, Dict, List, Optional, Sequence, Union
import json
from uuid import uuid4
import litellm
from dataclasses import dataclass, field


from .tools import FuncTool, ToolCall
from . import utils


# === TYPES ===


@dataclass
class Response:
    content: Any
    tool_calls: List[ToolCall] = field(default_factory=list)
    provider: Optional[str] = None
    model: Optional[str] = None
    usage: Dict[str, Any] = field(default_factory=dict)
    raw: Any = None  # original provider payload for debugging


@dataclass
class EmbeddingResponse:
    embeddings: List[List[float]]
    provider: Optional[str] = None
    model: Optional[str] = None
    usage: Dict[str, Any] = field(default_factory=dict)
    raw: Any = None  # original provider payload for debugging


# === ADAPTERS ===


class _LiteLLMCompletionAdapter:
    """LiteLLM-backed adapter for chat/completions."""

    def __init__(self, *, provider: str, model: str):
        self.provider = provider
        self.model = model

    def _add_system_prompt(self, messages, system_prompt):
        if system_prompt:
            # Prepend system prompt for providers that expect it in messages list.
            messages = [{"role": "system", "content": system_prompt}] + list(messages)
        return messages

    def _convert_tools(self, tools: Optional[List[object]]) -> Optional[List[Dict[str, Any]]]:
        if not tools:
            return None
        converted: List[Dict[str, Any]] = []
        for t in tools:
            if not isinstance(t, FuncTool):
                # Ignore tools we can't serialise into OpenAI-style schema.
                continue
            input_schema = dict(t.schema or {})
            properties = input_schema.pop("arguments", None)
            if properties is None:
                properties = input_schema.pop("args", {})
            input_schema["type"] = "object"  # openai convention
            input_schema["properties"] = properties  # openai convention
            converted.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": input_schema,
                    },
                }
            )
        return converted or None

    def _convert_model(self) -> str:
        if self.provider:
            return f"{self.provider}/{self.model}"
        return self.model

    def _parse_response(self, response: Any) -> Response:
        # expects LiteLLM object-style response
        message = response.choices[0].message
        content = getattr(message, "content", "") or ""
        tool_calls_raw = getattr(message, "tool_calls", None) or []

        parsed_calls: List[ToolCall] = []
        for tc in tool_calls_raw:
            fn = getattr(tc, "function", None)
            name = getattr(fn, "name", None) or getattr(tc, "name", "") or ""
            args_raw = getattr(fn, "arguments", None) or getattr(tc, "arguments", None) or "{}"
            tc_id = getattr(tc, "id", None) or str(uuid4())
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
            except Exception:
                args = {}
            parsed_calls.append(ToolCall(id=tc_id, name=name, arguments=args))

        usage = getattr(response, "usage", {}) or {}
        return Response(
            content=content,
            tool_calls=parsed_calls,
            provider=self.provider,
            model=self.model,
            usage=usage,
            raw=response,
        )

    def request(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[object]],
        system_prompt: Optional[str],
        **kwargs,
    ) -> Response:
        messages = self._add_system_prompt(messages, system_prompt)
        tools = self._convert_tools(tools)
        model = self._convert_model()
        resp = litellm.completion(model=model, messages=messages, tools=tools, **kwargs)
        return self._parse_response(resp)

    def token_counter(self, text: str) -> int:
        return utils.token_counter(text, provider=self.provider, model=self.model)


class _LiteLLMEmbeddingAdapter:
    """LiteLLM-backed adapter for embedding requests."""

    def __init__(self, *, provider: str, model: str):
        self.provider = provider
        self.model = model

    def _convert_model(self) -> str:
        if self.provider:
            return f"{self.provider}/{self.model}"
        return self.model

    def _extract_embeddings(self, response: Any) -> List[List[float]]:
        data = getattr(response, "data", None) or []
        embeddings: List[List[float]] = []
        for item in data:
            embed = getattr(item, "embedding", None)
            if embed is None and isinstance(item, dict):
                embed = item.get("embedding")
            if embed is None:
                continue
            embeddings.append(list(embed))
        return embeddings

    def request(self, *, input: Union[str, Sequence[str]], **kwargs) -> EmbeddingResponse:
        model = self._convert_model()
        response = litellm.embedding(model=model, input=input, **kwargs)
        embeddings = self._extract_embeddings(response)
        usage = getattr(response, "usage", {}) or {}
        return EmbeddingResponse(
            embeddings=embeddings,
            provider=self.provider,
            model=self.model,
            usage=usage,
            raw=response,
        )


# === PUBLIC CLIENTS ===


class CompletionClient:
    """Type-specific client for completion requests."""

    def __init__(self, *, provider: str, model: str, **kwargs):
        self.provider = provider
        self.model = model
        self._default_kwargs = kwargs
        self._adapter = _LiteLLMCompletionAdapter(provider=provider, model=model)

    def request(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[object]] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Response:
        adapter_kwargs = {**self._default_kwargs, **kwargs}
        return self._adapter.request(
            messages=messages,
            tools=tools,
            system_prompt=system_prompt,
            **adapter_kwargs,
        )


class EmbeddingClient:
    """Type-specific client for embedding requests."""

    def __init__(self, *, provider: str, model: str, **kwargs):
        self.provider = provider
        self.model = model
        self._default_kwargs = kwargs
        self._adapter = _LiteLLMEmbeddingAdapter(provider=provider, model=model)

    def request(self, *, input: Union[str, Sequence[str]], **kwargs) -> EmbeddingResponse:
        adapter_kwargs = {**self._default_kwargs, **kwargs}
        return self._adapter.request(input=input, **adapter_kwargs)

    def token_counter(self, text: str) -> int:
        return utils.token_counter(text, provider=self.provider, model=self.model)


class Client:
    """Factory for specific client types."""

    def __init__(self, *_args, **_kwargs):  # pragma: no cover - guard against old usage
        raise TypeError("Use `Client.completion(...)` or `Client.embedding(...)` instead of instantiating Client directly.")

    @staticmethod
    def completion(*, provider: str, model: str, **kwargs) -> CompletionClient:
        return CompletionClient(provider=provider, model=model, **kwargs)

    @staticmethod
    def embedding(*, provider: str, model: str, **kwargs) -> EmbeddingClient:
        return EmbeddingClient(provider=provider, model=model, **kwargs)


# === TESTING ===


if __name__ == "__main__":
    client = Client.completion(provider="anthropic", model="claude-3-haiku-20240307")
    messages = [{"role": "user", "content": "What is your name and who made you?"}]
    resp = client.request(messages=messages)
    print(resp.content)
    print(resp.model)


