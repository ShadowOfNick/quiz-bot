from app.config import LLMSettings
from app.llm.base import LLMProvider, LLMResponse


def create_llm_provider(settings: LLMSettings) -> LLMProvider:
    if settings.provider == "openai":
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    elif settings.provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )
    elif settings.provider in ("gemini", "gemma"):
        from app.llm.gemini_provider import GeminiProvider

        return GeminiProvider(
            api_key=settings.gemma_api_key,
            model=settings.gemma_model,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.provider}")


__all__ = ["LLMProvider", "LLMResponse", "create_llm_provider"]
