#!/usr/bin/env python3
"""
Provider configuration and validation.

This module provides functions to determine which providers are configured
and active based on environment variables.
"""

import os
import logging
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


@dataclass
class ProviderConfig:
    """Provider configuration from environment variables."""
    auth_provider: str
    data_provider: str
    ai_provider: str


class ProviderManager:
    """Manages provider configuration from environment variables."""
    
    def is_db_in_memory(self) -> bool:
        """Check if database is configured to use in-memory storage.
        
        Uses STUB_DB environment variable, defaults to False.
        
        Returns:
            True if database should use in-memory storage
        """
        env_value = os.environ.get('STUB_DB', 'false')
        return env_value.lower() in ('true', '1', 'yes', 'on')
    
    def is_custom_auth_enabled(self) -> bool:
        """Check if custom authentication is enabled.
        
        Uses settings system to read custom-auth-enabled setting.
        
        Returns:
            True if custom authentication is enabled
        """
        from . import get_setting
        return get_setting('custom-auth-enabled').lower() == 'true'
    
    def is_ai_mocked(self) -> bool:
        """Check if AI model is configured to use mocked responses.
        
        Uses STUB_AI environment variable, defaults to False.
        
        Returns:
            True if AI model should use mocked responses
        """
        env_value = os.environ.get('STUB_AI', 'false')
        return env_value.lower() in ('true', '1', 'yes', 'on')
    
    def get_provider_config(self) -> ProviderConfig:
        """Get complete provider configuration from environment variables.
        
        Returns:
            ProviderConfig instance with all provider settings
        """
        # Determine providers based on environment variables
        if self.is_ai_mocked():
            ai_provider = 'mocked'
        else:
            ai_provider = 'real'
        
        if self.is_db_in_memory():
            data_provider = 'tinydb'
        else:
            data_provider = 'firestore'
        
        if self.is_custom_auth_enabled():
            auth_provider = 'custom'
        else:
            auth_provider = 'firebase'
        
        return ProviderConfig(
            auth_provider=auth_provider,
            data_provider=data_provider,
            ai_provider=ai_provider
        )


# Global provider manager instance
_provider_manager: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    """Get the global provider manager instance.
    
    Returns:
        ProviderManager instance (singleton)
    """
    global _provider_manager
    
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
