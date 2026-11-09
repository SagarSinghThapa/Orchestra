import re
import unicodedata


class TextNormalizer:
    """
    Standardizes text canonically using Unicode NFC without destructive decomposition.
    
    Guarantees:
    - Normalizes Unicode to canonical NFC (preserving ligatures, subscripts, math symbols).
    - Standardizes line endings (\r\n and \r -> \n).
    - Removes non-printable control characters except tab and newline.
    - Strips trailing whitespace per line and compresses >= 3 newlines to \n\n.
    - Preserves casing, punctuation, quotes, and mathematical formulas verbatim.
    """

    def __init__(self) -> None:
        # Regex to match control chars: 0x00-0x1F and 0x7F-0x9F except \t (0x09) and \n (0x0A)
        self._control_char_re = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
        self._excess_newlines_re = re.compile(r"\n{3,}")

    def normalize(self, text: str) -> str:
        if not text:
            return ""

        # 1. Canonical Unicode NFC normalization (CRITICAL: Do NOT use NFKC)
        normalized = unicodedata.normalize("NFC", text)

        # 2. Line ending normalization
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

        # 3. Strip control characters (preserving \t and \n)
        normalized = self._control_char_re.sub("", normalized)

        # 4. Strip trailing whitespace from each line
        lines = [line.rstrip() for line in normalized.split("\n")]
        normalized = "\n".join(lines)

        # 5. Compress 3 or more consecutive newlines to 2 newlines
        normalized = self._excess_newlines_re.sub("\n\n", normalized)

        return normalized
