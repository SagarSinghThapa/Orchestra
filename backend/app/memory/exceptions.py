class MemoryException(Exception):
    """Base exception for memory subsystem errors."""
    pass


class StaleWriteError(MemoryException):
    """Raised when an optimistic concurrency version check fails during summary update."""
    pass


class WatermarkRegressionError(MemoryException):
    """Raised when an attempt is made to move a watermark backwards."""
    pass

