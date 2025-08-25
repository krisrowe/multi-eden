"""
AI model client factory.

Creates and manages AI model client instances based on configuration.
"""
import importlib
import logging
from typing import Dict, Optional, Type, List

from .config import AIConfig, ProviderConfig

logger = logging.getLogger(__name__)


# TODO: Revisit the architecture of the ai module to remove the circular import
# that necessitates the use of string-based type hints for 'ModelClient'.
# This likely involves moving the ModelClient class to a more foundational module.
class ModelClientFactory:
    """Factory for creating AI model clients with proper error handling."""
    
    def __init__(self, config: Optional[AIConfig] = None):
        """
        Initialize the factory.
        
        Args:
            config: AI configuration instance. If None, creates a new one.
        """
        self.config = config or AIConfig()
        self._client_cache: Dict[str, 'ModelClient'] = {}
        self._import_cache: Dict[str, Type['ModelClient']] = {}
    
    def create(self, service_name: str, model_override: Optional[str] = None) -> 'ModelClient':
        from .base_client import ModelClient
        """
        Create a model client instance with proper validation.
        
        Args:
            provider: Provider name. If None, uses service default.
            model_id: Specific model ID. If None, uses service default.
            service_name: Service name for prompt templates.
            
        Returns:
            Configured ModelClient instance
            
        Raises:
            ValueError: For configuration issues
            ImportError: For module/class import issues
            TypeError: For type validation issues
        """
        # Determine provider and model
        provider, model_id = self._resolve_provider_and_model(provider, model_id, service_name)
        
        # Get or create client class
        client_class = self._get_client_class(provider)
        
        # Create and validate client instance
        client = self._instantiate_client(client_class, service_name)
        
        # Cache the client
        cache_key = f"{provider}:{service_name}"
        self._client_cache[cache_key] = client
        
        logger.debug(f"Created {provider} client for {service_name} service")
        return client
    
    def _resolve_provider_and_model(self, provider: Optional[str], 
                                  model_id: Optional[str], 
                                  service_name: str) -> tuple[str, str]:
        """Resolve provider and model from configuration."""
        if provider is None:
            if model_id is None:
                service_info = self.config.get_service_info(service_name)
                if not service_info:
                    raise ValueError(f"Service '{service_name}' not found")
                model_id = service_info.default_model
            
            provider = self.config.get_provider_for_model(model_id)
            if not provider:
                raise ValueError(f"Model '{model_id}' not found")
        
        return provider, model_id
    
    def _get_client_class(self, provider: str) -> Type['ModelClient']:
        """Get client class with caching and proper error handling."""
        if provider in self._import_cache:
            return self._import_cache[provider]
        
        provider_config = self.config.get_providers().get(provider)
        if not provider_config:
            raise ValueError(f"Provider '{provider}' not configured")
        
        if not provider_config.enabled:
            raise ValueError(f"Provider '{provider}' is disabled")
        
        try:
            # Import class using full class path
            client_class = self._import_class(provider_config.class_path)
            
            # Cache the class
            self._import_cache[provider] = client_class
            return client_class
            
        except Exception as e:
            raise RuntimeError(f"Failed to get client class for provider '{provider}': {e}")
    
    def _import_class(self, class_path: str) -> Type['ModelClient']:
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
    
    def _instantiate_client(self, client_class: Type['ModelClient'], 
                           service_name: str) -> 'ModelClient':
        """Instantiate client with proper error handling."""
        try:
            return client_class(service_name)
        except Exception as e:
            raise RuntimeError(f"Failed to instantiate {client_class.__name__}: {e}")
    
    def get_enabled_providers(self) -> List[str]:
        """Get list of enabled providers, sorted by priority."""
        return self.config.get_enabled_providers()
    
    def get_available_models(self) -> List[str]:
        """Get list of available model IDs."""
        return self.config.get_models_list()
    
    def get_available_services(self) -> List[str]:
        """Get list of available service names."""
        return list(self.config.get_services().keys())
    
    def create_fallback_client(self, service_name: str) -> Optional['ModelClient']:
        """Create client from highest priority enabled provider."""
        enabled_providers = self.get_enabled_providers()
        if not enabled_providers:
            return None
        
        try:
            return self.create_model_client(provider=enabled_providers[0], service_name=service_name)
        except Exception as e:
            logger.warning(f"Failed to create fallback client: {e}")
            return None
    
    def validate_configuration(self) -> bool:
        """
        Validate the entire configuration.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        try:
            providers = self.config.get_providers()
            models = self.config.get_models()
            services = self.config.get_services()
            
            # Validate that all service default models exist
            for service_name, service_info in services.items():
                if service_info.default_model not in models:
                    raise ValueError(f"Service '{service_name}' references unknown model '{service_info.default_model}'")
            
            # Validate that all provider classes can be imported
            for provider_name, provider_config in providers.items():
                if provider_config.enabled:
                    try:
                        self._import_class(provider_config.class_path)
                    except Exception as e:
                        raise ValueError(f"Provider '{provider_name}' class cannot be imported: {e}")
            
            logger.info("AI configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"AI configuration validation failed: {e}")
            raise ValueError(f"Configuration validation failed: {e}")


# Convenience function for quick client creation
def create_model_client(provider: Optional[str] = None, 
                       model_id: Optional[str] = None,
                       service_name: str = None) -> 'ModelClient':
    """
    Convenience function to create a model client.
    
    Args:
        provider: Provider name (e.g., 'google')
        model_id: Specific model ID
        service_name: Service name
        
    Returns:
        Configured ModelClient instance
    """
    factory = ModelClientFactory()
    return factory.create_model_client(provider, model_id, service_name)
