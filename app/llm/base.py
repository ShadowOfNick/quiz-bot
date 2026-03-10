from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_response: Any = field(default=None, repr=False)


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 500,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> LLMResponse: ...
