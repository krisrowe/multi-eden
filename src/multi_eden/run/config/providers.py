#!/usr/bin/env python3
"""
Provider configuration and validation.

This module provides functions to determine which providers are configured
and active based on the current environment configuration.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Type
from functools import wraps
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Registry for provider friendly names
_provider_friendly_names: Dict[Type, str] = {}

def simple_provider_name(friendly_name: str) -> Callable:
    """
    Decorator to assign a friendly name to a provider class.
    
    Usage:
        @simple_provider_name("In Memory")
        class InMemoryAPITestClient:
            pass
    """
    def decorator(cls: Type) -> Type:
        _provider_friendly_names[cls] = friendly_name
        return cls
    return decorator

def get_provider_friendly_name(provider_class: Type) -> str:
    """
    Get the friendly name for a provider class.
    
    Args:
        provider_class: The provider class to get the friendly name for
        
    Returns:
        The friendly name if decorated, otherwise the class name
    """
    return _provider_friendly_names.get(provider_class, provider_class.__name__)


class ProviderConfigurationError(Exception):
    """Raised when provider configuration is invalid or missing required fields."""
    pass


class ProvidersFileNotFoundError(Exception):
    """Raised when providers.json file cannot be found."""
    pass


@dataclass
class ProviderConfig:
    """Provider configuration loaded from providers.json."""
    auth_provider: str
    data_provider: str
    ai_provider: str


class ProviderManager:
    """Manages provider configuration loading and caching."""
    
    def __init__(self):
        self._providers_data: Optional[Dict[str, Any]] = None
        self._providers_path: Optional[Path] = None
    
    def _get_settings_path(self) -> Path:
        """Get the settings path from CONFIG_ENV.
        
        Returns:
            Path to the settings directory containing host.json and providers.json
            
        Raises:
            ProviderConfigurationError: If CONFIG_ENV is not available or invalid
        """
        try:
            from .settings import _get_settings_folder_path
            return _get_settings_folder_path()
        except Exception as e:
            error_msg = f"Failed to get settings folder path: {e}"
            logger.error(f"Provider configuration failed: {error_msg}")
            raise ProviderConfigurationError(error_msg)
    
    def _load_providers_json(self) -> Dict[str, Any]:
        """Load and validate providers.json from settings directory.
        
        Returns:
            Dictionary containing provider configuration
            
        Raises:
            ProvidersFileNotFoundError: If providers.json cannot be loaded
            ProviderConfigurationError: If providers.json is invalid
        """
        if self._providers_data is not None:
            return self._providers_data
        
        try:
            settings_path = self._get_settings_path()
            providers_file = settings_path / "providers.json"
            
            if not providers_file.exists():
                error_msg = f"providers.json not found in settings directory: {providers_file}"
                logger.error(f"Provider configuration failed: {error_msg}")
                raise ProvidersFileNotFoundError(error_msg)
            
            with open(providers_file, 'r') as f:
                data = json.load(f)
            
            # Validate required fields
            required_fields = ['auth_provider', 'data_provider', 'ai_provider']
            for field in required_fields:
                if field not in data:
                    error_msg = f"Missing required field '{field}' in providers.json"
                    logger.error(f"Provider configuration failed: {error_msg}")
                    raise ProviderConfigurationError(error_msg)
            
            # Validate ai_provider value
            if data['ai_provider'] not in ['real', 'mocked']:
                error_msg = f"Invalid ai_provider value: {data['ai_provider']}. Must be 'real' or 'mocked'"
                logger.error(f"Provider configuration failed: {error_msg}")
                raise ProviderConfigurationError(error_msg)
            
            self._providers_data = data
            self._providers_path = providers_file
            logger.debug(f"Successfully loaded providers.json from: {providers_file}")
            return data
            
        except (json.JSONDecodeError, IOError) as e:
            error_msg = f"Failed to load providers.json: {e}"
            logger.error(f"Provider configuration failed: {error_msg}")
            raise ProvidersFileNotFoundError(error_msg)
    
    def is_db_in_memory(self) -> bool:
        """Check if database is configured to use in-memory storage.
        
        Priority:
        1. USE_IN_MEMORY_DB environment variable
        2. providers.json configuration
        
        Returns:
            True if database should use in-memory storage
            
        Raises:
            ProviderConfigurationError: If configuration cannot be loaded
        """
        # Check environment variable first
        env_value = os.environ.get('USE_IN_MEMORY_DB')
        if env_value is not None:
            return env_value.lower() in ('true', '1', 'yes', 'on')
        
        # Fall back to providers.json
        try:
            providers_data = self._load_providers_json()
            return providers_data['data_provider'] == 'tinydb'
        except Exception as e:
            logger.error(f"Failed to determine database in-memory status: {e}")
            raise ProviderConfigurationError(f"Failed to determine database in-memory status: {e}")
    
    def is_custom_auth_enabled(self) -> bool:
        """Check if custom authentication is enabled.
        
        Priority:
        1. CUSTOM_AUTH_ENABLED environment variable
        2. providers.json configuration
        
        Returns:
            True if custom authentication is enabled
            
        Raises:
            ProviderConfigurationError: If configuration cannot be loaded
        """
        # Check environment variable first
        env_value = os.environ.get('CUSTOM_AUTH_ENABLED')
        if env_value is not None:
            return env_value.lower() in ('true', '1', 'yes', 'on')
        
        # Fall back to providers.json
        try:
            providers_data = self._load_providers_json()
            auth_provider = providers_data['auth_provider']
            
            # Handle both string and array formats for backward compatibility
            if isinstance(auth_provider, list):
                return 'custom' in auth_provider
            else:
                return auth_provider == 'custom'
                
        except Exception as e:
            logger.error(f"Failed to determine custom auth status: {e}")
            raise ProviderConfigurationError(f"Failed to determine custom auth status: {e}")
    
    def is_ai_mocked(self) -> bool:
        """Check if AI model is configured to use mocked responses.
        
        Priority:
        1. AI_MODEL_MOCKED environment variable
        2. providers.json configuration
        
        Returns:
            True if AI model should use mocked responses
            
        Raises:
            ProviderConfigurationError: If configuration cannot be loaded
        """
        # Check environment variable first
        env_value = os.environ.get('AI_MODEL_MOCKED')
        if env_value is not None:
            return env_value.lower() in ('true', '1', 'yes', 'on')
        
        # Fall back to providers.json
        try:
            providers_data = self._load_providers_json()
            return providers_data['ai_provider'] == 'mocked'
        except Exception as e:
            logger.error(f"Failed to determine AI model mocked status: {e}")
            raise ProviderConfigurationError(f"Failed to determine AI model mocked status: {e}")
    
    def get_provider_config(self) -> ProviderConfig:
        """Get complete provider configuration.
        
        Returns:
            ProviderConfig instance with all provider settings
            
        Raises:
            ProviderConfigurationError: If configuration cannot be loaded
        """
        try:
            providers_data = self._load_providers_json()
            
            return ProviderConfig(
                auth_provider=providers_data['auth_provider'],
                data_provider=providers_data['data_provider'],
                ai_provider=providers_data['ai_provider']
            )
            
        except Exception as e:
            logger.error(f"Failed to get provider configuration: {e}")
            raise ProviderConfigurationError(f"Failed to get provider configuration: {e}")


# Global provider manager instance
_provider_manager: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    """Get the global provider manager instance.
    
    Returns:
        ProviderManager instance (singleton)
    """
    global _provider_manager
    
    # Ensure command line arguments have been parsed for --config-env if needed
    try:
        from .settings import _parse_command_line
        _parse_command_line()
    except Exception as e:
        logger.debug(f"Failed to parse command line arguments: {e}")
    
    if _provider_manager is None:
        _provider_manager = ProviderManager()
    return _provider_manager


# Convenience functions for direct access
def is_db_in_memory() -> bool:
    """Check if database is configured to use in-memory storage."""
    return get_provider_manager().is_db_in_memory()


def is_custom_auth_enabled() -> bool:
    """Check if custom authentication is enabled."""
    return get_provider_manager().is_custom_auth_enabled()


def is_ai_mocked() -> bool:
    """Check if AI model is configured to use mocked responses."""
    return get_provider_manager().is_ai_mocked()


def get_provider_config() -> ProviderConfig:
    """Get complete provider configuration."""
    return get_provider_manager().get_provider_config()
