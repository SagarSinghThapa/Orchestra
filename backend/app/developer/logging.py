import json
import re
from datetime import datetime, timezone
from typing import Any, Dict

SECRET_PATTERNS = [
    # JWT tokens
    (re.compile(r"eyJh[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[REDACTED_JWT]"),
    # Bearer tokens
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    # OpenAI / generic API keys
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "sk-[REDACTED_KEY]"),
    # GitHub personal / app tokens
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"), "gh_[REDACTED_TOKEN]"),
    # AWS Access Key ID
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA[REDACTED_AWS]"),
    # Private Key blocks
    (re.compile(r"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z ]+)?PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
]

SENSITIVE_KEY_NAMES = {
    "password", "token", "secret", "authorization", "api_key", "apikey",
    "access_key", "client_secret", "private_key"
}


def scrub_secrets(value: Any) -> Any:
    """Recursively scrub known sensitive patterns and keys from log payloads."""
    if isinstance(value, str):
        result = value
        for pattern, replacement in SECRET_PATTERNS:
            result = pattern.sub(replacement, result)
        return result
    elif isinstance(value, dict):
        sanitized = {}
        for k, v in value.items():
            if isinstance(k, str) and any(s in k.lower() for s in SENSITIVE_KEY_NAMES):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = scrub_secrets(v)
        return sanitized
    elif isinstance(value, list):
        return [scrub_secrets(item) for item in value]
    return value


class StructuredLogger:
    def __init__(self, subsystem: str):
        self.subsystem = subsystem

    def _log(self, level: str, message: str, trace_id: str = "N/A", context: dict = None):
        sanitized_message = scrub_secrets(message)
        sanitized_context = scrub_secrets(context or {})

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "subsystem": self.subsystem,
            "level": level,
            "message": sanitized_message,
            "context": sanitized_context
        }
        # Output structured JSON log
        print(json.dumps(log_entry))
        return log_entry

    def info(self, message: str, trace_id: str = "N/A", context: dict = None):
        return self._log("INFO", message, trace_id, context)

    def error(self, message: str, trace_id: str = "N/A", context: dict = None):
        return self._log("ERROR", message, trace_id, context)

    def warn(self, message: str, trace_id: str = "N/A", context: dict = None):
        return self._log("WARN", message, trace_id, context)

    def warning(self, message: str, trace_id: str = "N/A", context: dict = None):
        return self._log("WARN", message, trace_id, context)

    def debug(self, message: str, trace_id: str = "N/A", context: dict = None):
        return self._log("DEBUG", message, trace_id, context)


