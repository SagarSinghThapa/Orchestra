import json
import logging
from typing import Optional, Type, TypeVar
import httpx
from pydantic import BaseModel, ValidationError

from app.research.exceptions import ConfigurationError, ResearchPipelineError
from app.research.llm.base import LLMProvider

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleLLMProvider(LLMProvider):
    """
    OpenAI-compatible LLM provider communicating via HTTP client.
    Supports local models (vLLM, Ollama, LM Studio) and hosted OpenAI-compatible APIs.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: float = 20.0,
        max_tokens: int = 2048,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        raw_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
            raise ConfigurationError(
                f"LLM base URL must start with 'http://' or 'https://', got '{raw_url}'"
            )
        self.base_url = raw_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self._client = client

    async def _post_chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
        response_format: Optional[dict] = None,
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        endpoint = f"{self.base_url}/chat/completions"

        try:
            if self._client is not None:
                response = await self._client.post(endpoint, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)

            if response.status_code != 200:
                raise ResearchPipelineError(
                    f"LLM request failed with HTTP status {response.status_code}"
                )

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise ResearchPipelineError("LLM response contained no choices")

            content = choices[0].get("message", {}).get("content")
            if content is None:
                raise ResearchPipelineError("LLM choice contained no message content")

            return content

        except httpx.TimeoutException as exc:
            raise ResearchPipelineError(
                f"LLM request timed out after {self.timeout}s: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ResearchPipelineError(
                f"LLM request returned HTTP status {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise ResearchPipelineError(f"LLM network connection error: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ResearchPipelineError(f"Failed to decode LLM response JSON: {exc}") from exc

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return await self._post_chat(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> T:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        raw_content = await self._post_chat(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        return self._parse_structured_output(raw_content, schema)

    def _parse_structured_output(self, raw_content: str, schema: Type[T]) -> T:
        text = raw_content.strip()

        # 1. Strip explicit markdown fences without greedy regex
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # 2. Try direct validation
        try:
            return schema.model_validate_json(text)
        except (ValidationError, ValueError) as direct_exc:
            # 3. If surrounding text exists, find first '{' and last '}'
            start_idx = text.find("{")
            end_idx = text.rfind("}")
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                bracket_text = text[start_idx : end_idx + 1]
                try:
                    return schema.model_validate_json(bracket_text)
                except (ValidationError, ValueError):
                    pass

            raise ResearchPipelineError(
                f"Failed to validate model response as {schema.__name__}: {direct_exc}"
            ) from direct_exc
