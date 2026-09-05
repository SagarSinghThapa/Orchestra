from enum import Enum


class ErrorTaxonomy(str, Enum):
    VALIDATION_INPUT = "E1xx"
    AUTHENTICATION_AUTHORIZATION = "E2xx"
    DEPENDENCY_UPSTREAM = "E3xx"
    TIMEOUT = "E4xx"
    INTERNAL = "E5xx"


class DeveloperBaseException(Exception):
    def __init__(self, code: ErrorTaxonomy, message: str, context: dict = None):
        self.code = code
        self.message = message
        self.context = context or {}
        super().__init__(f"[{self.code.value}] {self.message}")


class ValidationError(DeveloperBaseException):
    def __init__(self, message: str, context: dict = None):
        super().__init__(ErrorTaxonomy.VALIDATION_INPUT, message, context)


class AuthError(DeveloperBaseException):
    def __init__(self, message: str, context: dict = None):
        super().__init__(ErrorTaxonomy.AUTHENTICATION_AUTHORIZATION, message, context)


class DependencyError(DeveloperBaseException):
    def __init__(self, message: str, context: dict = None):
        super().__init__(ErrorTaxonomy.DEPENDENCY_UPSTREAM, message, context)


class TimeoutError(DeveloperBaseException):
    def __init__(self, message: str, context: dict = None):
        super().__init__(ErrorTaxonomy.TIMEOUT, message, context)


class InternalError(DeveloperBaseException):
    def __init__(self, message: str, context: dict = None):
        super().__init__(ErrorTaxonomy.INTERNAL, message, context)
