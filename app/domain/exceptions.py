"""Domain exceptions — raised by services, caught by middleware."""


class DomainError(Exception):
    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(DomainError):
    def __init__(self, entity: str, identifier: str):
        super().__init__(f"{entity} '{identifier}' not found", "NOT_FOUND")


class AuthError(DomainError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTH_ERROR")


class PermissionError(DomainError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, "PERMISSION_DENIED")


class ValidationError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class RateLimitError(DomainError):
    def __init__(self):
        super().__init__("Too many requests", "RATE_LIMITED")
