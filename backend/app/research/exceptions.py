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
