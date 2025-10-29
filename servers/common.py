from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol

from pydantic import BaseModel, Field


class ToolRequest(BaseModel):
    """Inbound MCP-style payload."""

    name: str
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)


class ToolCallable(Protocol):
    async def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


def make_endpoint(handler: ToolCallable) -> Callable[[ToolRequest], Awaitable[Any]]:
    """Produce an async FastAPI endpoint that unwraps args/kwargs payload."""

    async def _endpoint(request: ToolRequest) -> Any:
        if request.args:
            return await handler(*request.args, **request.kwargs)
        return await handler(**request.kwargs)

    return _endpoint
