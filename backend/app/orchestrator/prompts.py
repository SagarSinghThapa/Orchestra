from app.developer.prompts.escaping import escape_prompt_data

CLASSIFIER_SYSTEM_PROMPT = (
    "You are Orchestra's Multi-Agent Intent Classifier. Your task is to accurately classify incoming user prompts "
    "into one of three mutually exclusive categories:\n"
    "1. 'developer': Tasks involving software engineering operations, repository file analysis, codebase inspection, "
    "code synthesis, refactoring, bug fixes, unified diffs, syntax/AST validation, or Git version control actions.\n"
    "2. 'research': Tasks requesting literature search, scientific paper synthesis, document information retrieval, "
    "verifiable citation evidence from indexed papers/PDFs, or deep factual topic exploration.\n"
    "3. 'direct_qa': General software conceptual questions, conversational greetings, explanations, math/logic queries, "
    "or general programming questions that do not require repository code changes or private document retrieval.\n\n"
    "Respond strictly with the required JSON schema matching IntentClassificationResult."
)

DIRECT_QA_SYSTEM_PROMPT = (
    "You are Orchestra's Engineering Assistant. Provide concise, clear, and technically accurate responses to user questions. "
    "Ground your explanations in proven software engineering principles. "
    "Do not hallucinate private files or pretend to perform filesystem mutations."
)


def build_classification_prompt(user_prompt: str) -> str:
    """Builds an injection-resistant classification prompt with escaped delimiters."""
    safe_input = escape_prompt_data(user_prompt)
    return (
        f"<SYSTEM_INSTRUCTIONS>\n"
        f"{CLASSIFIER_SYSTEM_PROMPT}\n"
        f"</SYSTEM_INSTRUCTIONS>\n"
        f"<USER_INPUT>\n"
        f"{safe_input}\n"
        f"</USER_INPUT>\n"
    )


def build_direct_qa_prompt(user_prompt: str, context: str = "") -> str:
    """Builds an injection-resistant Direct Q&A prompt with escaped delimiters."""
    safe_input = escape_prompt_data(user_prompt)
    context_section = ""
    if context:
        safe_context = escape_prompt_data(context)
        context_section = f"<ADDITIONAL_CONTEXT>\n{safe_context}\n</ADDITIONAL_CONTEXT>\n"

    return (
        f"<SYSTEM_INSTRUCTIONS>\n"
        f"{DIRECT_QA_SYSTEM_PROMPT}\n"
        f"</SYSTEM_INSTRUCTIONS>\n"
        f"{context_section}"
        f"<USER_QUERY>\n"
        f"{safe_input}\n"
        f"</USER_QUERY>\n"
    )
