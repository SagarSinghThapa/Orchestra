import asyncio
import json
import logging
import random
import time
from typing import Optional, Type, TypeVar
from urllib.parse import urlparse
import httpx
from pydantic import BaseModel, ValidationError

from app.research.exceptions import (
    AuthenticationError,
    ConfigurationError,
    LLMTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
    ResearchPipelineError,
)
from app.research.llm.base import LLMProvider

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleLLMProvider(LLMProvider):
    """
    OpenAI-compatible LLM provider communicating via HTTP client.
    Supports local models (vLLM, Ollama, LM Studio) and hosted OpenAI-compatible APIs
    (OpenAI, Groq, NVIDIA NIM, Google Gemini).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: float = 20.0,
        max_tokens: int = 2048,
        client: Optional[httpx.AsyncClient] = None,
        max_retries: int = 2,
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
        self.max_retries = max(0, max_retries)

    async def _post_chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
        response_format: Optional[dict] = None,
        deadline: Optional[float] = None,
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
        host = urlparse(self.base_url).netloc or "unknown-host"
        req_deadline = deadline or (time.monotonic() + self.timeout)

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            now = time.monotonic()
            remaining_time = req_deadline - now

            # If retrying and budget is below minimum threshold, abort immediately
            if attempt > 0 and remaining_time < 2.0:
                logger.warning(
                    "LLM retry aborted: remaining deadline budget %.2fs is below 2.0s floor (host=%s, model=%s)",
                    remaining_time,
                    host,
                    self.model,
                )
                if last_error:
                    raise last_error
                raise LLMTimeoutError(
                    f"LLM request deadline exceeded ({remaining_time:.1f}s remaining, minimum 2.0s needed)"
                )

            per_attempt_timeout = min(self.timeout, max(1.0, remaining_time))
            call_start = time.monotonic()

            try:
                if self._client is not None:
                    response = await self._client.post(
                        endpoint, json=payload, headers=headers, timeout=per_attempt_timeout
                    )
                else:
                    async with httpx.AsyncClient(timeout=per_attempt_timeout) as client:
                        response = await client.post(endpoint, json=payload, headers=headers)

                duration_ms = (time.monotonic() - call_start) * 1000.0

                # Safe structured log (strictly zero prompt or authorization token logging)
                logger.debug(
                    "LLM HTTP call completed: host=%s, model=%s, status=%d, duration=%.1fms, attempt=%d",
                    host,
                    self.model,
                    response.status_code,
                    duration_ms,
                    attempt + 1,
                )

                if response.status_code == 200:
                    try:
                        data = response.json()
                    except json.JSONDecodeError as exc:
                        raise ResearchPipelineError(f"Failed to decode LLM response JSON: {exc}") from exc

                    choices = data.get("choices", [])
                    if not choices:
                        raise ResearchPipelineError("LLM response contained no choices")

                    content = choices[0].get("message", {}).get("content")
                    if content is None:
                        raise ResearchPipelineError("LLM choice contained no message content")

                    return content

                # Normalized Error Handling Taxonomy
                status = response.status_code
                if status in (401, 403):
                    # Authentication failure: zero retries (fail fast)
                    raise AuthenticationError(
                        f"AI Provider authentication failed with HTTP status {status}: Invalid or unauthorized API key"
                    )
                elif status == 400:
                    # Bad Request / Context Overflow: zero retries (fail fast)
                    raise ResearchPipelineError(
                        f"AI Provider rejected request with HTTP status 400: {response.text[:200]}"
                    )
                elif status == 429:
                    # Rate limit or quota: retryable
                    last_error = RateLimitError(
                        f"AI Provider rate limit or quota exceeded with HTTP status 429: {response.text[:200]}"
                    )
                elif status in (502, 503, 504):
                    # Temporary provider unavailability: retryable
                    last_error = ProviderUnavailableError(
                        f"AI Provider temporarily unavailable with HTTP status {status}"
                    )
                else:
                    raise ResearchPipelineError(
                        f"LLM request failed with HTTP status {status}"
                    )

            except (AuthenticationError, ResearchPipelineError) as fatal_exc:
                # Fatal non-retryable errors
                if isinstance(fatal_exc, (RateLimitError, ProviderUnavailableError)):
                    last_error = fatal_exc
                else:
                    raise

            except httpx.TimeoutException as exc:
                duration_ms = (time.monotonic() - call_start) * 1000.0
                logger.warning(
                    "LLM request timed out after %.1fms (attempt %d/%d): host=%s, model=%s",
                    duration_ms,
                    attempt + 1,
                    self.max_retries + 1,
                    host,
                    self.model,
                )
                last_error = LLMTimeoutError(
                    f"LLM request timed out after {self.timeout}s: {exc}"
                )

            except httpx.RequestError as exc:
                duration_ms = (time.monotonic() - call_start) * 1000.0
                logger.warning(
                    "LLM network connection error after %.1fms (attempt %d/%d): host=%s, model=%s",
                    duration_ms,
                    attempt + 1,
                    self.max_retries + 1,
                    host,
                    self.model,
                )
                last_error = ResearchPipelineError(f"LLM network connection error: {exc}")

            # If more attempts remaining, apply jittered exponential backoff
            if attempt < self.max_retries:
                backoff = min(0.5 * (2 ** attempt) + random.uniform(0.1, 0.4), 3.0)
                if (req_deadline - time.monotonic() - backoff) < 1.0:
                    logger.warning(
                        "LLM retry aborted: backoff %.2fs exceeds remaining deadline budget",
                        backoff,
                    )
                    break
                await asyncio.sleep(backoff)

        if last_error:
            raise last_error
        raise ResearchPipelineError("LLM call failed with unknown error")

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
