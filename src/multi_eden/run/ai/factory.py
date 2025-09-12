"""
AI model client factory.

Creates and manages AI model client instances based on configuration.
"""
import importlib
import logging
from typing import Dict, Optional, Type, List

from ..config.models import (
    get_available_providers, get_available_services, get_models_list,
    get_model_info
)
from .services import get_service_default_model, get_prompt

logger = logging.getLogger(__package__)


def _resolve_provider_and_model(model_id: Optional[str], service_name: str) -> tuple[str, str]:
    """Resolve provider and model from configuration."""
    if model_id is None:
        model_id = get_service_default_model(service_name)
    
    # Check if AI is mocked - if so, override to use mock provider
    from ..config.providers import is_ai_mocked
    if is_ai_mocked():
        logger.debug(f"AI is mocked, using mock provider for service {service_name}")
        return 'mock', model_id
    
    # Since our models are organized by provider in the YAML structure,
    # we need to find which provider contains this model
    from ..config.models import _load_model_config
    model_config = _load_model_config()
    providers = model_config.get('providers', {})
    
    # Find which provider contains this model
    provider = None
    for provider_name, provider_config in providers.items():
        models = provider_config.get('models', {})
        if model_id in models:
            provider = provider_name
            break
    
    if not provider:
        raise ValueError(f"Model '{model_id}' not found in any provider configuration")
    
    return provider, model_id

def _get_client_class(provider: str) -> Type['ModelClient']:
    """Get client class with proper error handling."""
    # For now, hardcode the provider class paths since we don't have provider config
    provider_class_paths = {
        'google': 'multi_eden.run.ai.google_client.GoogleClient',
        'mock': 'multi_eden.run.ai.mock_client.MockClient'
    }
    
    class_path = provider_class_paths.get(provider)
    if not class_path:
        raise ValueError(f"Provider '{provider}' not configured")
    
    try:
        # Import class using full class path
        client_class = _import_class(class_path)
        return client_class
        
    except Exception as e:
        raise RuntimeError(f"Failed to get client class for provider '{provider}': {e}")

def _import_class(class_path: str) -> Type['ModelClient']:
    """Import class using standard full class path pattern."""
    from .base_client import ModelClient
    try:
        module_name, class_name = class_path.rsplit('.', 1)
        module = importlib.import_module(module_name)
        client_class = getattr(module, class_name)
        
        if not isinstance(client_class, type):
            raise TypeError(f"'{class_path}' is not a class")
        
        if not issubclass(client_class, ModelClient):
            raise TypeError(f"'{class_path}' must inherit from ModelClient")
            
        return client_class
        
    except ValueError:
        raise ValueError(f"Invalid class path format: {class_path}")
    except ImportError as e:
        raise ImportError(f"Failed to import module '{module_name}': {e}")
    except AttributeError as e:
        raise AttributeError(f"Class '{class_name}' not found in '{module_name}': {e}")

def _instantiate_client(client_class: Type['ModelClient'], model_name: str, service_name: str) -> 'ModelClient':
    """Instantiate client with proper error handling."""
    try:
        # GoogleClient expects (model_name, service_name), MockClient expects (service_name)
        if hasattr(client_class, '__name__') and 'GoogleClient' in client_class.__name__:
            return client_class(model_name, service_name)
        else:
            return client_class(service_name)
    except Exception as e:
        raise RuntimeError(f"Failed to instantiate {client_class.__name__}: {e}")

def create(service_name: str, model_override: Optional[str] = None, operation: Optional[str] = None) -> 'ModelClient':
    """Create a model client for the specified service."""
    from .base_client import ModelClient
    
    # Determine provider and model
    provider, model_id = _resolve_provider_and_model(model_override, service_name)
    
    # Get client class
    client_class = _get_client_class(provider)
    
    # Create and validate client instance
    client = _instantiate_client(client_class, model_id, service_name)
    
    # Configure MockClient with operation context if available
    if hasattr(client, 'set_operation') and operation:
        client.set_operation(operation)
        logger.debug(f"Configured MockClient with operation: {operation}")
    
    logger.debug(f"Created {provider} client for {service_name} service")
    return client

def get_default_provider_class_name(service_name: str = None) -> str:
    """Get the default provider class name for a service."""
    if service_name:
        try:
            default_model = get_service_default_model(service_name)
            model_info = get_model_info(default_model)
            provider = model_info.get('provider', 'mock')
        except:
            provider = 'mock'
    else:
        provider = 'mock'
    
    # Map provider names to class names
    provider_class_names = {
        'google': 'GoogleClient',
        'mock': 'MockClient'
    }
    return provider_class_names.get(provider, 'MockClient')



def validate_configuration() -> bool:
    """Validate the entire configuration."""
    try:
        models = get_models_list()
        services = get_available_services()
        
        # Validate that all service default models exist
        for service_name in services:
            try:
                default_model = get_service_default_model(service_name)
                if default_model not in models:
                    raise ValueError(f"Service '{service_name}' references unknown model '{default_model}'")
            except Exception as e:
                raise ValueError(f"Service '{service_name}' has invalid default model: {e}")
        
        # Validate that all provider classes can be imported
        providers = get_available_providers()
        for provider_name in providers:
            try:
                # For now, hardcode the provider class paths
                provider_class_paths = {
                    'google': 'multi_eden.run.ai.google_client.GoogleClient',
                    'mock': 'multi_eden.run.ai.mock_client.MockClient'
                }
                class_path = provider_class_paths.get(provider_name)
                if class_path:
                    _import_class(class_path)
            except Exception as e:
                raise ValueError(f"Provider '{provider_name}' class cannot be imported: {e}")
        
        logger.info("AI configuration validation passed")
        return True
        
    except Exception as e:
        logger.error(f"AI configuration validation failed: {e}")
        raise ValueError(f"Configuration validation failed: {e}")

