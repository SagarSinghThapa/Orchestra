def escape_prompt_data(text: str) -> str:
    """
    Escapes structural XML/prompt delimiters in untrusted user or document text.
    Replaces XML-sensitive characters (&, <, >) with their standard XML entity representations
    (&amp;, &lt;, &gt;) to prevent untrusted input from emitting active delimiter tags
    (<USER_QUESTION>, <SYSTEM_INSTRUCTIONS>, <UNTRUSTED_RETRIEVED_EVIDENCE>, <evidence>).
    """
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
