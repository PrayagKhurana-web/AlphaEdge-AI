"""Domain exceptions for authentication."""


class AuthenticationError(Exception):
    """Base authentication exception."""


class EmailAlreadyRegisteredError(AuthenticationError):
    """Raised when registration uses an existing email."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are invalid."""


class InactiveUserError(AuthenticationError):
    """Raised when an inactive account attempts authentication."""


class InvalidAccessTokenError(AuthenticationError):
    """Raised when an access token cannot be validated."""
