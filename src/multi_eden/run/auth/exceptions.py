"""
Custom exceptions for the authentication module.
"""

class AuthError(Exception):
    """Base exception for all authentication and authorization errors."""
    pass

class AuthenticationError(AuthError):
    """Raised when a token is invalid, expired, or malformed."""
    pass

class TokenExpiredError(AuthenticationError):
    """Raised when a token has expired."""
    pass

class TokenSignatureError(AuthenticationError):
    """Raised when a token has an invalid signature."""
    pass

class TokenMalformedError(AuthenticationError):
    """Raised when a token is malformed or unparseable."""
    pass

class TokenIssuerError(AuthenticationError):
    """Raised when a token has an unknown or invalid issuer."""
    pass

class AuthorizationError(AuthError):
    """Raised when a user is authenticated but not authorized to access a resource."""
    pass
