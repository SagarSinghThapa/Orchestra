class ResearchPipelineError(Exception):
    """Base exception for all research pipeline errors."""
    pass


class ParserError(ResearchPipelineError):
    """Raised when document parsing, validation, or extraction fails."""
    pass


class ConfigurationError(ResearchPipelineError):
    """Raised when pipeline configuration or dimension contract is invalid or mismatched."""
    pass


class VectorStoreError(ResearchPipelineError):
    """Raised when vector database operations fail."""
    pass


class AuthenticationError(ResearchPipelineError):
    """Raised when provider authentication fails (e.g. HTTP 401/403 invalid API key)."""
    pass


class RateLimitError(ResearchPipelineError):
    """Raised when provider rate limits or quotas are exceeded (HTTP 429)."""
    pass


class ProviderUnavailableError(ResearchPipelineError):
    """Raised when upstream AI provider is temporarily unavailable (HTTP 502/503/504)."""
    pass


class LLMTimeoutError(ResearchPipelineError):
    """Raised when provider request exceeds deadline budget or connection timeout."""
    pass
