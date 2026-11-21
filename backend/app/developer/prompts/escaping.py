def escape_prompt_data(text: str) -> str:
    """
    Escapes structural XML/prompt delimiters in untrusted user, file, or metadata text.
    Replaces XML-sensitive characters (&, <, >) with standard XML entity representations
    (&amp;, &lt;, &gt;) to prevent untrusted input from emitting active delimiter tags
    (<SYSTEM_INSTRUCTIONS>, <UNTRUSTED_REPOSITORY_DATA>, <TASK_PROMPT>, etc.).
    """
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
