"""
Process-level secret caching system for environment loading.
"""
import logging
from typing import Dict

from .exceptions import SecretUnavailableException

logger = logging.getLogger(__name__)

# Module-level cache: secret_name -> value
_secret_cache: Dict[str, str] = {}


def get_secret(secret_name: str) -> str:
    """
    Get secret with process-level caching.
    
    Args:
        secret_name: Name of the secret to retrieve
        
    Returns:
        Secret value
        
    Raises:
        SecretUnavailableException: If secret cannot be loaded
    """
    if secret_name in _secret_cache:
        logger.debug(f"Using cached secret '{secret_name}'")
        return _secret_cache[secret_name]
    
    # Load from secrets manager - let any exception bubble up
    logger.debug(f"Loading secret '{secret_name}' from secrets manager")
    try:
        from multi_eden.build.secrets.factory import get_secrets_manager
        manager = get_secrets_manager()
        response = manager.get_secret(secret_name, show=True)
        
        if response.meta.success and response.secret:
            _secret_cache[secret_name] = response.secret.value
            logger.debug(f"Successfully loaded and cached secret '{secret_name}'")
            return response.secret.value
        else:
            raise SecretUnavailableException(f"Secret '{secret_name}' not found", secret_name=secret_name)
            
    except Exception as e:
        logger.debug(f"Failed to load secret '{secret_name}': {e}")
        # Re-raise as-is - let the calling code handle it
        raise


def clear_secret_cache():
    """Clear the secret cache (useful for testing)."""
    global _secret_cache
    _secret_cache.clear()
    logger.debug("Secret cache cleared")