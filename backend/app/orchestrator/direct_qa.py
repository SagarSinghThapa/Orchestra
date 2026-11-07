import logging
from typing import AsyncIterator, Optional

from app.developer.logging import scrub_secrets
from app.orchestrator.prompts import DIRECT_QA_SYSTEM_PROMPT, build_direct_qa_prompt
from app.research.llm.base import LLMProvider

logger = logging.getLogger("direct-qa")


class DirectQAEngine:
    """
    Lightweight, bounded conversational answering engine.
    Executes at most 1 LLM call with 0 tool authority and 0 filesystem access.
    """

    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider

    async def answer(self, prompt: str, context: Optional[str] = None) -> str:
        """
        Synthesizes an immediate answer to a conversational or conceptual inquiry.
        """
        logger.info("Executing Direct Q&A synthesis (0 tools, max 1 LLM call)")
        formatted_prompt = build_direct_qa_prompt(prompt, context=context or "")

        try:
            raw_answer = await self.llm_provider.generate_text(
                prompt=formatted_prompt,
                system_prompt=DIRECT_QA_SYSTEM_PROMPT,
                temperature=0.2
            )
            clean_answer = scrub_secrets(raw_answer.strip())
            return clean_answer
        except Exception as e:
            clean_err = scrub_secrets(str(e))
            logger.error(f"Direct Q&A synthesis error: {clean_err}")
            raise

    async def answer_stream(self, prompt: str, context: Optional[str] = None) -> AsyncIterator[str]:
        """
        Streams an immediate answer to a conversational or conceptual inquiry.
        """
        logger.info("Executing Direct Q&A streaming synthesis (0 tools, max 1 LLM call)")
        formatted_prompt = build_direct_qa_prompt(prompt, context=context or "")

        try:
            if hasattr(self.llm_provider, "stream_text"):
                async for chunk in self.llm_provider.stream_text(
                    prompt=formatted_prompt,
                    system_prompt=DIRECT_QA_SYSTEM_PROMPT,
                    temperature=0.2,
                ):
                    yield chunk
            else:
                ans = await self.answer(prompt, context=context)
                yield ans
        except Exception as e:
            clean_err = scrub_secrets(str(e))
            logger.error(f"Direct Q&A streaming synthesis error: {clean_err}")
            raise

