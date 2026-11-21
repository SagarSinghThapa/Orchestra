import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from pythonjsonlogger.json import JsonFormatter
except ImportError:
    from pythonjsonlogger.jsonlogger import JsonFormatter

from app.core.context import get_request_id

# Common secret regex patterns
SECRET_PATTERNS = [
    # JWT tokens
    (re.compile(r"eyJh[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[REDACTED_JWT]"),
    # Bearer tokens
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    # OpenAI / generic API keys
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "sk-[REDACTED_KEY]"),
    # Anthropic API keys
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "sk-ant-[REDACTED_KEY]"),
    # GitHub personal / app tokens
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"), "gh_[REDACTED_TOKEN]"),
    # AWS Access Key ID
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA[REDACTED_AWS]"),
    # Private Key blocks
    (re.compile(r"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z ]+)?PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
]

SENSITIVE_KEY_NAMES = {
    "password", "token", "secret", "authorization", "api_key", "apikey",
    "access_key", "client_secret", "private_key", "cookie", "set-cookie",
    "prompt", "message", "query", "document", "content"
}


def scrub_secrets(value: Any) -> Any:
    """
    Recursively scrub known sensitive patterns and sensitive dictionary keys from log payloads.
    Guarantees that sensitive strings and keys are replaced with redaction placeholders.
    """
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
    elif isinstance(value, (list, tuple, set)):
        scrubbed_list = [scrub_secrets(item) for item in value]
        return type(value)(scrubbed_list) if not isinstance(value, set) else set(scrubbed_list)
    return value


class OrchestraJsonFormatter(JsonFormatter):
    """
    Custom JSON formatter ensuring request correlation ID and UTC ISO timestamp
    are attached to every emitted log record, with automatic secret scrubbing.
    """

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        # Ensure standard ISO timestamp
        if "timestamp" not in log_record:
            log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        # Add request_id from context if not already explicitly supplied
        if "request_id" not in log_record:
            log_record["request_id"] = get_request_id()
        # Ensure log level is upper case
        if "level" not in log_record and hasattr(record, "levelname"):
            log_record["level"] = record.levelname.upper()
        # Scrub all record fields for secrets and sensitive key names
        for k in list(log_record.keys()):
            if k in ("timestamp", "request_id", "level"):
                continue
            if isinstance(k, str) and any(s in k.lower() for s in SENSITIVE_KEY_NAMES):
                if k == "message":
                    log_record[k] = scrub_secrets(log_record[k])
                else:
                    log_record[k] = "[REDACTED]"
            else:
                log_record[k] = scrub_secrets(log_record[k])


_logging_configured = False


def configure_logging(level: str = "INFO") -> None:
    """
    Configures the root logger with the standard Orchestra structured JSON formatter.
    Idempotent: prevents duplicate handlers across repeated application startup cycles.
    """
    global _logging_configured
    if _logging_configured:
        return

    root_logger = logging.getLogger()
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Avoid duplicating stdout handlers
    has_orchestra_handler = any(
        isinstance(getattr(h, "formatter", None), OrchestraJsonFormatter)
        for h in root_logger.handlers
    )

    if not has_orchestra_handler:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(OrchestraJsonFormatter())
        root_logger.addHandler(handler)

    _logging_configured = True


class StructuredLogger:
    """
    Backward-compatible structured logger re-exported for Developer subsystem.
    """

    def __init__(self, subsystem: str):
        self.subsystem = subsystem
        self._logger = logging.getLogger(f"orchestra.{subsystem}")

    def _log(self, level: str, message: str, trace_id: str = "N/A", context: dict = None) -> dict:
        req_id = get_request_id()
        if trace_id == "N/A" and req_id != "req_untracked":
            trace_id = req_id

        sanitized_message = scrub_secrets(message)
        sanitized_context = scrub_secrets(context or {})

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "request_id": req_id,
            "subsystem": self.subsystem,
            "level": level.upper(),
            "message": sanitized_message,
            "context": sanitized_context,
        }
        # Print for backward compatibility with previous Developer tests that inspect stdout
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
