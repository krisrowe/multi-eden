"""
AI Model Configuration Management
Provider-agnostic model configuration loading and validation.
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

# Import the new factory system
try:
    from multi_eden.run.ai.config import AIConfig
    from multi_eden.run.ai.factory import ModelClientFactory
    _FACTORY_AVAILABLE = True
except ImportError:
    _FACTORY_AVAILABLE = False
    _ai_config = None
    _factory = None

logger = logging.getLogger(__name__)

# Global instances for caching
_ai_config: Optional[AIConfig] = None
_factory: Optional[ModelClientFactory] = None


def _get_ai_config() -> AIConfig:
    """Get or create AI configuration instance."""
    global _ai_config
    if _ai_config is None and _FACTORY_AVAILABLE:
        try:
            _ai_config = AIConfig()
        except Exception as e:
            logger.warning(f"Failed to load AI configuration: {e}")
            raise
    return _ai_config


def _get_factory() -> ModelClientFactory:
    """Get or create factory instance."""
    global _factory
    if _factory is None and _FACTORY_AVAILABLE:
        try:
            config = _get_ai_config()
            _factory = ModelClientFactory(config)
        except Exception as e:
            logger.warning(f"Failed to create factory: {e}")
            raise
    return _factory


def _load_model_config() -> dict:
    """
    Load model configuration from models.yaml.
    
    DEPRECATED: Use _get_ai_config() instead.
    """
    if _FACTORY_AVAILABLE:
        try:
            config = _get_ai_config()
            # Convert to old format for backward compatibility
            old_format = {
                'ai_models': {
                    'available': {}
                },
                'services': {}
            }
            
            # Convert providers to old ai_models format
            providers = config.get_providers()
            for provider_name, provider_config in providers.items():
                for model_id, model_config in provider_config.models.items():
                    old_format['ai_models']['available'][model_id] = {
                        'name': model_config.name,
                        'description': model_config.description,
                        'provider': provider_name
                    }
            
            # Add services
            services = config.get_services()
            for service_name, service_config in services.items():
                old_format['services'][service_name] = {
                    'default_model': service_config.default_model,
                    'prompt': service_config.prompt
                }
            
            return old_format
        except Exception as e:
            logger.warning(f"Failed to load new config format: {e}")
            return {}
    
    # Fallback to old loading method if new system not available
    try:
        import yaml
        model_path = 'models.yaml'
        if not os.path.exists(model_path):
            return {}
        
        with open(model_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[MODEL_CONFIG] ⚠️  Warning: Error loading models.yaml: {e}")
        return {}


def get_models_list() -> list:
    """Get list of available model IDs for /api/models endpoint."""
    if _FACTORY_AVAILABLE:
        try:
            factory = _get_factory()
            return factory.get_available_models()
        except Exception as e:
            logger.warning(f"Failed to get models from factory: {e}")
    
    # Fallback to old method
    model_config = _load_model_config()
    ai_models = model_config.get('ai_models', {})
    available_models = ai_models.get('available', {})
    
    if not available_models:
        import os
        model_path = 'models.yaml'  # Same path used in _load_model_config()
        absolute_path = os.path.abspath(model_path)
        raise RuntimeError(
            f"No AI models configured. Please ensure {absolute_path} contains an 'ai_models' section "
            "with 'available' models."
        )
    
    return list(available_models.keys())


def get_default_model() -> str:
    """Get the default model name for /api/models endpoint and Gemini client.
    
    DEPRECATED: Use get_service_default_model() for service-specific models.
    """
    if _FACTORY_AVAILABLE:
        try:
            # Try to get default from first available service
            config = _get_ai_config()
            services = config.get_services()
            if services:
                first_service = list(services.keys())[0]
                return config.get_service_default_model(first_service)
        except Exception as e:
            logger.warning(f"Failed to get default model from factory: {e}")
    
    # Fallback to old method
    model_config = _load_model_config()
    ai_models = model_config.get('ai_models', {})
    default_model = ai_models.get('default')
    
    if not default_model:
        # If no explicit default, use the first available model
        available_models = ai_models.get('available', {})
        if available_models:
            default_model = list(available_models.keys())[0]
        else:
            raise RuntimeError(
                "No AI models configured. Please ensure config/models.yaml contains an 'ai_models.available' section."
            )
    
    return default_model


def get_service_default_model(service_name: str) -> str:
    """Get the default model for a specific service.
    
    Args:
        service_name: The service name
        
    Returns:
        The default model name for the service
        
    Raises:
        RuntimeError: If no default model is configured for the service
    """
    if _FACTORY_AVAILABLE:
        try:
            config = _get_ai_config()
            return config.get_service_default_model(service_name)
        except Exception as e:
            logger.warning(f"Failed to get service default model from factory: {e}")
    
    # Fallback to old method
    model_config = _load_model_config()
    services = model_config.get('services', {})
    service_config = services.get(service_name, {})
    
    default_model = service_config.get('default_model')
    
    if not default_model:
        available_services = list(services.keys())
        raise RuntimeError(
            f"No default model configured for service '{service_name}'. "
            f"Available services: {', '.join(available_services) if available_services else 'none'}. "
            f"Please ensure config/models.yaml contains a 'services.{service_name}.default_model' setting."
        )
    
    return default_model

def validate_model(model_id: str) -> None:
    """Validate that a model ID is available. Raises ValueError if invalid."""
    if _FACTORY_AVAILABLE:
        try:
            config = _get_ai_config()
            config.validate_model(model_id)
            return
        except Exception as e:
            logger.warning(f"Failed to validate model with factory: {e}")
    
    # Fallback to old method
    available_models = get_models_list()
    
    if model_id not in available_models:
        raise ValueError(
            f"Invalid model '{model_id}'. Available models: {', '.join(available_models)}"
        )


def get_prompt(service_name: str) -> str:
    """Get a prompt template by service name.
    
    Args:
        service_name: The service name
        
    Returns:
        The prompt template string
        
    Raises:
        RuntimeError: If the prompt is not found
    """
    if _FACTORY_AVAILABLE:
        try:
            config = _get_ai_config()
            return config.get_prompt(service_name)
        except Exception as e:
            logger.warning(f"Failed to get prompt from factory: {e}")
    
    # Fallback to old method
    model_config = _load_model_config()
    services = model_config.get('services', {})
    service_config = services.get(service_name, {})
    
    prompt_template = service_config.get('prompt', '')
    
    if not prompt_template:
        available_services = list(services.keys())
        raise RuntimeError(
            f"Prompt template for service '{service_name}' not found. "
            f"Available services: {', '.join(available_services) if available_services else 'none'}. "
            f"Please ensure config/models.yaml contains a 'services.{service_name}.prompt' setting."
        )
    
    return prompt_template


def get_service_config(service_name: str) -> dict:
    """Get the complete configuration for a service.
    
    Args:
        service_name: The service name
        
    Returns:
        Dictionary containing service configuration
        
    Raises:
        RuntimeError: If the service is not found
    """
    if _FACTORY_AVAILABLE:
        try:
            config = _get_ai_config()
            service_info = config.get_service_info(service_name)
            if service_info:
                return {
                    'default_model': service_info.default_model,
                    'prompt': service_info.prompt,
                    'schema_path': service_info.schema_path
                }
        except Exception as e:
            logger.warning(f"Failed to get service config from factory: {e}")
    
    # Fallback to old method
    model_config = _load_model_config()
    services = model_config.get('services', {})
    service_config = services.get(service_name, {})
    
    if not service_config:
        available_services = list(services.keys())
        raise RuntimeError(
            f"Service '{service_name}' not found. "
            f"Available services: {', '.join(available_services) if available_services else 'none'}. "
            f"Please ensure config/models.yaml contains a 'services.{service_name}' section."
        )
    
    return service_config

def get_model_info(model_id: str) -> dict:
    """Get detailed information about a specific model for /api/models endpoint."""
    validate_model(model_id)  # This will raise ValueError if invalid
    
    if _FACTORY_AVAILABLE:
        try:
            config = _get_ai_config()
            model_info = config.get_model_info(model_id)
            if model_info:
                return model_info.to_dict()
        except Exception as e:
            logger.warning(f"Failed to get model info from factory: {e}")
    
    # Fallback to old method
    model_config = _load_model_config()
    available_models = model_config.get('ai_models', {}).get('available', {})
    return available_models[model_id]


# New factory-based functions
def create_model_client(provider: Optional[str] = None, 
                       model_id: Optional[str] = None):
    """
    Create a model client using the new factory system.
    
    Args:
        provider: Provider name (e.g., 'google')
        model_id: Specific model ID
        service_name: Service name
        
    Returns:
        Configured ModelClient instance
        
    Raises:
        RuntimeError: If factory system is not available
    """
    if not _FACTORY_AVAILABLE:
        raise RuntimeError("AI factory system not available. Please ensure all dependencies are installed.")
    
    factory = _get_factory()
    return factory.create_model_client(provider, model_id, service_name)


def get_available_providers() -> List[str]:
    """Get list of available provider names."""
    if not _FACTORY_AVAILABLE:
        return []
    
    try:
        factory = _get_factory()
        return factory.get_enabled_providers()
    except Exception as e:
        logger.warning(f"Failed to get providers: {e}")
        return []


def get_available_services() -> List[str]:
    """Get list of available service names."""
    if not _FACTORY_AVAILABLE:
        return []
    
    try:
        factory = _get_factory()
        return factory.get_available_services()
    except Exception as e:
        logger.warning(f"Failed to get services: {e}")
        return []


def validate_configuration() -> bool:
    """
    Validate the entire AI configuration.
    
    Returns:
        True if configuration is valid
        
    Raises:
        RuntimeError: If factory system is not available
        ValueError: If configuration is invalid
    """
    if not _FACTORY_AVAILABLE:
        raise RuntimeError("AI factory system not available. Please ensure all dependencies are installed.")
    
    factory = _get_factory()
    return factory.validate_configuration()


