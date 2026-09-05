import json
from datetime import datetime, timezone


class StructuredLogger:
    def __init__(self, subsystem: str):
        self.subsystem = subsystem

    def _log(self, level: str, message: str, trace_id: str = "N/A", context: dict = None):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "subsystem": self.subsystem,
            "level": level,
            "message": message,
            "context": context or {}
        }
        # In a real system, this would output to stdout or a file ingestion pipeline
        print(json.dumps(log_entry))
        return log_entry

    def info(self, message: str, trace_id: str = "N/A", context: dict = None):
        return self._log("INFO", message, trace_id, context)

    def error(self, message: str, trace_id: str = "N/A", context: dict = None):
        return self._log("ERROR", message, trace_id, context)

    def warn(self, message: str, trace_id: str = "N/A", context: dict = None):
        return self._log("WARN", message, trace_id, context)

    def debug(self, message: str, trace_id: str = "N/A", context: dict = None):
        return self._log("DEBUG", message, trace_id, context)

