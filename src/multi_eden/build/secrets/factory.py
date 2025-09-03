"""Secrets manager factory with configuration-driven selection.

Provides a factory function to create the appropriate secrets manager
based on application configuration.
"""

import logging
import importlib
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from .interface import SecretsManager

logger = logging.getLogger(__name__)

# Global singleton instance
_secrets_manager_instance: Optional[SecretsManager] = None
_providers_config: Optional[Dict[str, Any]] = None


def _load_providers_config() -> Dict[str, Any]:
    """Load providers configuration from providers.yaml."""
    global _providers_config
    if _providers_config is not None:
        return _providers_config
    
    providers_file = Path(__file__).parent / "providers.yaml"
    try:
        with open(providers_file, 'r') as f:
            _providers_config = yaml.safe_load(f)
        logger.debug(f"Loaded providers config from {providers_file}")
        return _providers_config
    except Exception as e:
        logger.error(f"Failed to load providers config from {providers_file}: {e}")
        raise RuntimeError(f"Could not load providers configuration: {e}") from e


def _create_manager_instance(manager_type: str) -> SecretsManager:
    """Create a manager instance by type using dynamic import."""
    providers_config = _load_providers_config()
    providers = providers_config.get('providers', {})
    
    if manager_type not in providers:
        available = list(providers.keys())
        raise RuntimeError(f"Unknown secrets manager type: {manager_type}. Available: {available}")
    
    provider_config = providers[manager_type]
    class_path = provider_config['class']
    
    # Dynamic import: "module.path.ClassName" -> module.path + ClassName
    module_path, class_name = class_path.rsplit('.', 1)
    
    try:
        module = importlib.import_module(module_path)
        manager_class = getattr(module, class_name)
        return manager_class()
    except Exception as e:
        logger.error(f"Failed to create {manager_type} manager from {class_path}: {e}")
        raise RuntimeError(f"Could not create {manager_type} secrets manager: {e}") from e


def get_secrets_manager(force_reload: bool = False) -> SecretsManager:
    """Get the configured secrets manager instance.
    
    Args:
        force_reload: Force recreation of the singleton instance
        
    Returns:
        SecretsManager instance based on app.yaml configuration
        
    Raises:
        RuntimeError: If configuration is invalid or required dependencies are missing
    """
    global _secrets_manager_instance
    
    # Return cached instance unless force reload
    if _secrets_manager_instance is not None and not force_reload:
        return _secrets_manager_instance
    
    # Clean up existing instance if force reloading
    if force_reload and _secrets_manager_instance is not None:
        if hasattr(_secrets_manager_instance, 'cleanup'):
            _secrets_manager_instance.cleanup()
        _secrets_manager_instance = None
    
    # Load app.yaml to determine provider
    app_config = _load_app_config()
    secrets_config = app_config.get('secrets', {})
    
    # Get manager type from config or use default from providers.yaml
    providers_config = _load_providers_config()
    default_provider = providers_config.get('default_provider', 'google')
    manager_type = secrets_config.get('manager', default_provider)
    
    logger.debug(f"Creating secrets manager of type: {manager_type}")
    
    _secrets_manager_instance = _create_manager_instance(manager_type)
    
    logger.debug(f"Initialized {manager_type} secrets manager")
    return _secrets_manager_instance


def _load_app_config() -> dict:
    """Load application configuration from app.yaml."""
    try:
        import yaml
        from pathlib import Path
        
        # Look for app.yaml in current directory or config directory
        config_paths = [
            Path("config/app.yaml"),
            Path("app.yaml"),
            Path("../config/app.yaml"),  # For when running from subdirectories
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
                logger.debug(f"Loaded app configuration from: {config_path}")
                return config
        
        # No config file found, return empty config (will use defaults)
        logger.debug("No app.yaml found, using default configuration")
        return {}
        
    except Exception as e:
        logger.warning(f"Failed to load app configuration: {e}")
        return {}





def cleanup_secrets_manager():
    """Clean up the global secrets manager instance."""
    global _secrets_manager_instance
    
    if _secrets_manager_instance is not None:
        if hasattr(_secrets_manager_instance, 'cleanup'):
            _secrets_manager_instance.cleanup()
        _secrets_manager_instance = None
        logger.debug("Secrets manager instance cleaned up")


def get_manager_type() -> Optional[str]:
    """Get the type of the current secrets manager.
    
    Returns:
        Manager type string or None if no manager is initialized
    """
    if _secrets_manager_instance is not None:
        return _secrets_manager_instance.manager_type
    return None


# Convenience functions for direct secret access
def get_secret(secret_name: str) -> Optional[str]:
    """Get a secret value using the configured manager.
    
    Args:
        secret_name: Name of the secret to retrieve
        
    Returns:
        Secret value if found, None otherwise
    """
    manager = get_secrets_manager()
    return manager.get_secret(secret_name)


def set_secret(secret_name: str, secret_value: str) -> bool:
    """Set a secret value using the configured manager.
    
    Args:
        secret_name: Name of the secret
        secret_value: Value to store
        
    Returns:
        True if successful, False otherwise
    """
    manager = get_secrets_manager()
    return manager.set_secret(secret_name, secret_value)


def list_secrets() -> list:
    """List all secrets using the configured manager.
    
    Returns:
        List of secret names
    """
    manager = get_secrets_manager()
    return manager.list_secrets()
