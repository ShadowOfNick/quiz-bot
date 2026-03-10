import json
import logging
from google import genai
from google.genai import types

from app.llm.base import LLMResponse

logger = logging.getLogger(__name__)


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 500,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> LLMResponse:
        
        contents = []
        system_text = ""
        
        for msg in messages:
            role = msg["role"]
            text = msg["content"]
            
            if role == "system":
                # For Gemma models, system instructions aren't supported via config,
                # so we append it as context to the first user message
                system_text += text + "\n\n"
            elif role == "user":
                final_text = system_text + text if system_text else text
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=final_text)]))
                system_text = "" # Clear after injecting into first user message
            elif role == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=text)]))

        # Do not use system_instruction in config as it breaks gemma-3
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        try:
            # Note: the new genai SDK uses async generators or sync calls, 
            # we will use the async version
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=config
            )
            
            # Count tokens if provided by the API response
            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_tokens = response.usage_metadata.prompt_token_count
                completion_tokens = response.usage_metadata.candidates_token_count

            return LLMResponse(
                content=response.text or "",
                model=self._model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                raw_response=response,
            )
            
        except Exception as e:
            logger.exception("Gemini API call failed")
            raise e
