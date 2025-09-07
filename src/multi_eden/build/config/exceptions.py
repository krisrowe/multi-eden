"""
Strongly-typed exceptions for environment loading with guidance properties.
"""


class ProjectIdNotFoundException(Exception):
    """Raised when a project ID cannot be found in .projects file."""
    
    def __init__(self, message: str, env_name: str = None, var_name: str = None, 
                 configured_layer: str = None, projects_file_exists: bool = False):
        super().__init__(message)
        self.env_name = env_name
        self.var_name = var_name or "PROJECT_ID"
        self.configured_layer = configured_layer
        self.projects_file_exists = projects_file_exists


class ProjectsFileNotFoundException(Exception):
    """Raised when .projects file is missing."""
    
    def __init__(self, message: str, env_name: str = None, var_name: str = None,
                 configured_layer: str = None):
        super().__init__(message)
        self.env_name = env_name
        self.var_name = var_name or "PROJECT_ID"
        self.configured_layer = configured_layer
        self.projects_file_exists = False


class SecretUnavailableException(Exception):
    """Raised when a secret cannot be loaded from the secrets manager."""
    
    def __init__(self, message: str, secret_name: str = None, var_name: str = None,
                 configured_layer: str = None):
        super().__init__(message)
        self.secret_name = secret_name
        self.var_name = var_name
        self.configured_layer = configured_layer


class EnvironmentLoadError(Exception):
    """Base exception for environment loading errors."""
    pass


class EnvironmentNotFoundError(Exception):
    """Raised when an environment layer is not found."""
    pass

