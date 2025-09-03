"""
Build package secrets management for multi-env SDK.

Provides functionality for managing secrets across different environments
with support for both Google Cloud Secret Manager and local encrypted storage.
"""

from .manifest import load_secrets_manifest
from .interface import SecretsManager
from .google_manager import GoogleSecretsManager
from .local_manager import LocalSecretsManager
from .factory import (
    get_secrets_manager,
    cleanup_secrets_manager,
    get_manager_type,
    get_secret,
    set_secret,
    list_secrets
)
from . import secret_utils

__all__ = [
    # Manifest
    'load_secrets_manifest',
    
    # Interface
    'SecretsManager',
    
    # Implementations
    'GoogleSecretsManager',
    'LocalSecretsManager', 
    
    # Factory and convenience functions
    'get_secrets_manager',
    'cleanup_secrets_manager',
    'get_manager_type',
    'get_secret',
    'set_secret',
    'list_secrets',
    
    # Utilities
    'secret_utils',
    
    # Legacy
    'get_secret_manager_value'
]
