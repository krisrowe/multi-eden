"""
Strongly-typed exceptions for environment loading system.
"""


class EnvironmentLoadError(Exception):
    """Raised when environment cannot be loaded."""
    pass


class EnvironmentNotFoundError(EnvironmentLoadError):
    """Raised when environment name not found."""
    pass


class SecretUnavailableException(Exception):
    """Raised when a secret cannot be loaded."""
    pass


class ProjectIdNotFoundException(Exception):
    """Raised when a project ID cannot be found in .projects file."""
    pass


class ProjectsFileNotFoundException(Exception):
    """Raised when .projects file is missing."""
    pass