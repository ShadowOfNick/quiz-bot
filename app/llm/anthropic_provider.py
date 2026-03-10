import json

from anthropic import AsyncAnthropic

from app.llm.base import LLMResponse


class AnthropicProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 500,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> LLMResponse:
        # Extract system message if present
        system_text = ""
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                api_messages.append(msg)

        if response_format == "json" and system_text:
            system_text += "\n\nYou must respond with valid JSON only."
        elif response_format == "json":
            system_text = "You must respond with valid JSON only."

        kwargs: dict = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_text:
            kwargs["system"] = system_text

        response = await self._client.messages.create(**kwargs)
        content = response.content[0].text if response.content else ""

        return LLMResponse(
            content=content,
            model=response.model,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            raw_response=response,
        )
