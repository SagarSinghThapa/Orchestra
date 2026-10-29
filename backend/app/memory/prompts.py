from app.developer.prompts.escaping import escape_prompt_data

SUMMARIZER_SYSTEM_PROMPT = (
    "You are Orchestra's Conversation Summarizer. Your task is to produce a concise, factual summary "
    "of a conversation between a user and an AI engineering assistant. "
    "Preserve key decisions, technical conclusions, action items, and important context. "
    "Omit greetings, filler, and redundant exchanges. "
    "Do not hallucinate information not present in the conversation. "
    "Do not include any secrets, API keys, passwords, or tokens in your summary. "
    "Respond strictly with the required JSON schema."
)


def build_summarization_prompt(
    messages: list[dict],
    existing_summary: str | None = None,
) -> str:
    """
    Builds an injection-resistant summarization prompt with escaped message content.
    Applies escape_prompt_data to message roles, content, and existing summaries.
    """
    msg_lines = []
    for msg in messages:
        role = escape_prompt_data(str(msg.get("role", "unknown")))
        content = escape_prompt_data(str(msg.get("content", "")))
        msg_lines.append(f"[{role}]: {content}")

    conversation_block = "\n".join(msg_lines)

    existing_block = ""
    if existing_summary:
        safe_existing = escape_prompt_data(existing_summary)
        existing_block = (
            f"<EXISTING_SUMMARY>\n{safe_existing}\n</EXISTING_SUMMARY>\n"
            "Incorporate the existing summary with the new messages below. "
            "Produce a single unified summary that covers the full conversation.\n\n"
        )

    return (
        f"<SYSTEM_INSTRUCTIONS>\n{SUMMARIZER_SYSTEM_PROMPT}\n</SYSTEM_INSTRUCTIONS>\n"
        f"{existing_block}"
        f"<CONVERSATION>\n{conversation_block}\n</CONVERSATION>\n"
        f"Produce a JSON summary following the SummarizationResponse schema."
    )

