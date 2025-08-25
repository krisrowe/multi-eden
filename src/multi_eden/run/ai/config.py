"""
AI model configuration management.

Loads and validates AI model configurations from models.yaml.
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml

logger = logging.getLogger(__name__)


class ModelConfig:
    """Configuration for a single AI model."""
    
    def __init__(self, name: str, description: str, provider: str, **kwargs):
        self.name = name
        self.description = description
        self.provider = provider
        self.max_tokens = kwargs.get('max_tokens')
        self.cost_per_1k_tokens = kwargs.get('cost_per_1k_tokens')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {
            'name': self.name,
            'description': self.description,
            'provider': self.provider,
            'max_tokens': self.max_tokens,
            'cost_per_1k_tokens': self.cost_per_1k_tokens
        }


class ProviderConfig:
    """Configuration for an AI provider."""
    
    def __init__(self, class_path: str, description: str, models: Dict[str, ModelConfig], 
                 enabled: bool = True, priority: int = 1):
        self.class_path = class_path
        self.description = description
        self.models = models
        self.enabled = enabled
        self.priority = priority
    
    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """Get a specific model by ID."""
        return self.models.get(model_id)


class ServiceConfig:
    """Configuration for an AI service."""
    
    def __init__(self, default_model: str, prompt: str, schema_path: Optional[str] = None):
        self.default_model = default_model
        self.prompt = prompt
        self.schema_path = schema_path


class AIConfig:
    """Main AI configuration manager."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize AI configuration.
        
        Args:
            config_path: Path to models.yaml. Defaults to $cwd/models.yaml
        """
        if config_path is None:
            config_path = Path.cwd() / "models.yaml"
        
        self.config_path = Path(config_path)
        self._config_data: Optional[Dict[str, Any]] = None
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"AI configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config_data = yaml.safe_load(f)
            logger.debug(f"Loaded AI configuration from {self.config_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to load AI configuration: {e}")
    
    def get_providers(self) -> Dict[str, ProviderConfig]:
        """Get all configured AI providers."""
        if not self._config_data or 'providers' not in self._config_data:
            return {}
        
        providers = {}
        for provider_name, provider_data in self._config_data['providers'].items():
            models = {}
            for model_id, model_data in provider_data.get('models', {}).items():
                models[model_id] = ModelConfig(
                    name=model_data['name'],
                    description=model_data['description'],
                    provider=provider_name,
                    max_tokens=model_data.get('max_tokens'),
                    cost_per_1k_tokens=model_data.get('cost_per_1k_tokens')
                )
            
            providers[provider_name] = ProviderConfig(
                class_path=provider_data['class_path'],
                description=provider_data['description'],
                models=models,
                enabled=provider_data.get('enabled', True),
                priority=provider_data.get('priority', 1)
            )
        
        return providers
    
    def get_models(self) -> Dict[str, ModelConfig]:
        """Get all available AI models across all providers."""
        models = {}
        providers = self.get_providers()
        
        for provider_name, provider_config in providers.items():
            if provider_config.enabled:
                for model_id, model_config in provider_config.models.items():
                    models[model_id] = model_config
        
        return models
    
    def get_models_list(self) -> List[str]:
        """Get list of available model IDs for backward compatibility."""
        return list(self.get_models().keys())
    
    def get_services(self) -> Dict[str, ServiceConfig]:
        """Get all configured AI services."""
        if not self._config_data or 'services' not in self._config_data:
            return {}
        
        services = {}
        for service_name, service_data in self._config_data['services'].items():
            services[service_name] = ServiceConfig(
                default_model=service_data['default_model'],
                prompt=service_data['prompt'],
                schema_path=service_data.get('schema_path')
            )
        
        return services
    
    def get_provider_for_model(self, model_id: str) -> Optional[str]:
        """Get the provider name for a specific model."""
        models = self.get_models()
        if model_id in models:
            return models[model_id].provider
        return None
    
    def get_model_info(self, model_id: str) -> Optional[ModelConfig]:
        """Get information about a specific model."""
        return self.get_models().get(model_id)
    
    def get_service_info(self, service_name: str) -> Optional[ServiceConfig]:
        """Get information about a specific service."""
        return self.get_services().get(service_name)
    
    def get_service_default_model(self, service_name: str) -> str:
        """Get the default model for a specific service."""
        service_info = self.get_service_info(service_name)
        if not service_info:
            available_services = list(self.get_services().keys())
            raise RuntimeError(
                f"No default model configured for service '{service_name}'. "
                f"Available services: {', '.join(available_services) if available_services else 'none'}. "
                f"Please ensure models.yaml contains a 'services.{service_name}.default_model' setting."
            )
        return service_info.default_model
    
    def get_prompt(self, service_name: str) -> str:
        """Get a prompt template by service name."""
        service_info = self.get_service_info(service_name)
        if not service_info:
            available_services = list(self.get_services().keys())
            raise RuntimeError(
                f"Prompt template for service '{service_name}' not found. "
                f"Available services: {', '.join(available_services) if available_services else 'none'}. "
                f"Please ensure models.yaml contains a 'services.{service_name}.prompt' setting."
            )
        return service_info.prompt
    
    def validate_model(self, model_id: str) -> None:
        """Validate that a model ID is available. Raises ValueError if invalid."""
        available_models = self.get_models_list()
        
        if model_id not in available_models:
            raise ValueError(
                f"Invalid model '{model_id}'. Available models: {', '.join(available_models)}"
            )
    
    def get_enabled_providers(self) -> List[str]:
        """Get list of enabled providers, sorted by priority."""
        providers = self.get_providers()
        enabled = [name for name, config in providers.items() if config.enabled]
        return sorted(enabled, key=lambda x: providers[x].priority)
