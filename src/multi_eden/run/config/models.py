"""
AI Model Configuration Management
Simple YAML-based configuration loading.
"""
import logging
import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

def _load_model_config() -> dict:
    """Load model configuration from models.yaml."""
    try:
        model_path = 'models.yaml'
        if not os.path.exists(model_path):
            return {}
        
        with open(model_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Error loading models.yaml: {e}")
        return {}


def get_models_list() -> list:
    """Get list of available model IDs for /api/models endpoint."""
    model_config = _load_model_config()
    providers = model_config.get('providers', {})
    available_models = providers.get('google', {}).get('models', {})
    
    if not available_models:
        import os
        model_path = 'models.yaml'
        absolute_path = os.path.abspath(model_path)
        raise RuntimeError(
            f"No AI models configured. Please ensure {absolute_path} contains a 'providers.google.models' section "
            "with available models."
        )
    
    return list(available_models.keys())


def get_default_model() -> str:
    """Get the default model name for /api/models endpoint and Gemini client.
    
    DEPRECATED: Use get_service_default_model() for service-specific models.
    """
    model_config = _load_model_config()
    providers = model_config.get('providers', {})
    google_models = providers.get('google', {}).get('models', {})
    
    if not google_models:
        raise RuntimeError(
            "No AI models configured. Please ensure config/models.yaml contains a 'providers.google.models' section."
        )
    
    # Use the first available model as default
    default_model = list(google_models.keys())[0]
    
    return default_model




def validate_model(model_id: str) -> None:
    """Validate that a model ID is available. Raises ValueError if invalid."""

    available_models = get_models_list()
    
    if model_id not in available_models:
        raise ValueError(
            f"Invalid model '{model_id}'. Available models: {', '.join(available_models)}"
        )







def get_model_info(model_id: str) -> dict:
    """Get detailed information about a specific model for /api/models endpoint."""
    validate_model(model_id)  # This will raise ValueError if invalid
    

    model_config = _load_model_config()
    available_models = model_config.get('providers', {}).get('google', {}).get('models', {})
    return available_models[model_id]


def get_available_providers() -> List[str]:
    """Get list of available provider names from models.yaml."""
    model_config = _load_model_config()
    providers = model_config.get('providers', {})
    return list(providers.keys())

def get_available_services() -> List[str]:
    """Get list of available service names from models.yaml."""
    model_config = _load_model_config()
    services = model_config.get('services', {})
    return list(services.keys())

def validate_configuration() -> bool:
    """
    Validate the entire AI configuration.
    
    Returns:
        True if configuration is valid
        
    Raises:
        ValueError: If configuration is invalid
    """
    try:
        # Check that models.yaml can be loaded
        model_config = _load_model_config()
        if not model_config:
            raise ValueError("models.yaml is empty or could not be loaded")
        
        # Check that required sections exist
        ai_models = model_config.get('ai_models', {})
        services = model_config.get('services', {})
        
        if not ai_models.get('available'):
            raise ValueError("No AI models configured in models.yaml")
        
        if not services:
            raise ValueError("No services configured in models.yaml")
        
        # Validate that all service default models exist
        available_models = list(ai_models.get('available', {}).keys())
        for service_name, service_config in services.items():
            default_model = service_config.get('default_model')
            if not default_model:
                raise ValueError(f"Service '{service_name}' has no default_model configured")
            if default_model not in available_models:
                raise ValueError(f"Service '{service_name}' references unknown model '{default_model}'")
        
        logger.info("AI configuration validation passed")
        return True
        
    except Exception as e:
        logger.error(f"AI configuration validation failed: {e}")
        raise ValueError(f"Configuration validation failed: {e}")


