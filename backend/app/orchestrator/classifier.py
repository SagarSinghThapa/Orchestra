import logging
import re
from typing import Optional

from app.orchestrator.prompts import CLASSIFIER_SYSTEM_PROMPT, build_classification_prompt
from app.orchestrator.schemas import IntentClassificationResult, IntentType
from app.research.llm.base import LLMProvider

logger = logging.getLogger("intent-classifier")

# Deterministic fast-path regex patterns
DEVELOPER_PATTERNS = [
    re.compile(r"\bgit\s+(status|diff|log|commit|branch)\b", re.IGNORECASE),
    re.compile(r"\b(refactor|codebase|ast|syntax error|write file|read file|repo tree)\b", re.IGNORECASE),
    re.compile(r"\b(fix bug|patch file|coding agent|repository agent)\b", re.IGNORECASE),
    re.compile(r"\b[\w\-_\/]+\.(py|ts|js|tsx|jsx|json|yaml|yml|toml|html|css)\b", re.IGNORECASE),
]

RESEARCH_PATTERNS = [
    re.compile(r"\b(citation|citations|cite sources?|cite papers?)\b", re.IGNORECASE),
    re.compile(r"\b(scientific paper|research paper|literature review)\b", re.IGNORECASE),
    re.compile(r"\b(document chunks?|retrieval evidence|qdrant|vector search)\b", re.IGNORECASE),
    re.compile(r"\b(what does the document say|according to the uploaded)\b", re.IGNORECASE),
]

DIRECT_QA_PATTERNS = [
    re.compile(r"^(hi|hello|hey|greetings|good morning|good evening)[!\.\s]*$", re.IGNORECASE),
    re.compile(r"^(what is|how do|explain|tell me about)\s+[a-zA-Z0-9\s\?]+$", re.IGNORECASE),
]


class IntentClassifier:
    """
    Intelligent query intent classifier with fast-path deterministic heuristics
    and bounded LLM-assisted disambiguation.
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider

    def classify_heuristic(self, prompt: str) -> Optional[IntentClassificationResult]:
        """
        Fast-path evaluation: returns a decisive classification result with 0 LLM calls
        if patterns match unambiguously.
        """
        text = prompt.strip()
        dev_matches = any(p.search(text) for p in DEVELOPER_PATTERNS)
        res_matches = any(p.search(text) for p in RESEARCH_PATTERNS)

        # Conflicting/overlapping keywords require LLM disambiguation
        if dev_matches and res_matches:
            return None

        if dev_matches:
            return IntentClassificationResult(
                intent=IntentType.DEVELOPER,
                confidence=1.0,
                rationale="Heuristic pattern match for developer intelligence task."
            )

        if res_matches:
            return IntentClassificationResult(
                intent=IntentType.RESEARCH,
                confidence=1.0,
                rationale="Heuristic pattern match for research intelligence task."
            )

        for p in DIRECT_QA_PATTERNS:
            if p.match(text):
                return IntentClassificationResult(
                    intent=IntentType.DIRECT_QA,
                    confidence=1.0,
                    rationale="Heuristic pattern match for conversational or general inquiry."
                )

        return None

    async def classify(self, prompt: str, forced_intent: Optional[IntentType] = None) -> IntentClassificationResult:
        """
        Classifies prompt into RESEARCH, DEVELOPER, or DIRECT_QA.
        Respects optional forced_intent, checks heuristics first, and falls back to LLM.
        """
        if forced_intent is not None:
            logger.info(f"Using explicitly forced intent: {forced_intent.value}")
            return IntentClassificationResult(
                intent=forced_intent,
                confidence=1.0,
                rationale="Explicit user-provided intent override."
            )

        # 1. Fast-path heuristic check (0 cost)
        heuristic = self.classify_heuristic(prompt)
        if heuristic:
            logger.info(f"Intent classified via heuristic: {heuristic.intent.value}")
            return heuristic

        # 2. LLM-assisted disambiguation (at most 1 LLM call)
        if self.llm_provider:
            try:
                formatted_prompt = build_classification_prompt(prompt)
                result = await self.llm_provider.generate_structured(
                    prompt=formatted_prompt,
                    schema=IntentClassificationResult,
                    system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                    temperature=0.0
                )
                if isinstance(result, IntentClassificationResult):
                    logger.info(f"Intent classified via LLMProvider: {result.intent.value}")
                    return result
            except Exception as e:
                logger.warning(f"LLM classification failure, falling back to DIRECT_QA: {e}")

        # 3. Safe fallback default
        logger.info("Defaulting intent to DIRECT_QA due to ambiguous input / provider fallback.")
        return IntentClassificationResult(
            intent=IntentType.DIRECT_QA,
            confidence=0.5,
            rationale="Default fallback for ambiguous or unclassified input."
        )
