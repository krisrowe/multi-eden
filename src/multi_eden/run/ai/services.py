"""
Generic data models for AI services.
"""

import logging
import os
from pathlib import Path
from typing import Generic, TypeVar, Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field

# Import data model classes for type hints
try:
    from core.data_models import ProcessedFood, NutritionalInfo
except ImportError:
    # Fallback for when running outside the main project context
    ProcessedFood = Any
    NutritionalInfo = Any

logger = logging.getLogger(__package__)

# Generic type for items in ModelBasedServiceResponse
T = TypeVar('T')


def _load_services_config() -> dict:
    """Load services configuration from the app's app.yaml.
    
    Returns:
        Services configuration dict, or empty dict if not available
    """
    try:
        # Import here to avoid circular imports
        from multi_eden.run.config.settings import _load_app_config
        
        app_config = _load_app_config()
        
        if 'services' not in app_config:
            logger.debug("No 'services' section found in app.yaml, using empty services config")
            return {'services': {}}
            
        # Wrap in the expected format
        return {'services': app_config['services']}
        
    except Exception as e:
        logger.debug(f"Could not load services configuration from app.yaml: {e}")
        return {'services': {}}


def get_service_default_model(service_name: str, class_default: str = None) -> str:
    """Get the default model for a specific service.
    
    Priority order:
    1. app.yaml service config (if exists)
    2. class_default (if provided)
    3. fallback default
    
    Args:
        service_name: The service name
        class_default: Class-level default model (optional)
        
    Returns:
        The default model name for the service
    """
    try:
        services_config = _load_services_config()
        if services_config:
            services = services_config.get('services', {})
            service_config = services.get(service_name, {})
            app_default = service_config.get('default_model')
            if app_default:
                logger.debug(f"Using app.yaml default model for {service_name}: {app_default}")
                return app_default
    except Exception as e:
        logger.debug(f"Could not load services config: {e}")
    
    # Fall back to class default or system default
    if class_default:
        logger.debug(f"Using class default model for {service_name}: {class_default}")
        return class_default
    
    # Final fallback
    fallback_model = 'gemini-2.5-flash'
    logger.debug(f"Using fallback default model for {service_name}: {fallback_model}")
    return fallback_model


def get_prompt(service_name: str) -> str:
    """Get a prompt template by service name.
    
    Args:
        service_name: The service name
        
    Returns:
        The prompt template string, or default for services that don't need templates
    """
    try:
        services_config = _load_services_config()
        if services_config:
            services = services_config.get('services', {})
            service_config = services.get(service_name, {})
            prompt_template = service_config.get('prompt')
            if prompt_template:
                logger.debug(f"Using app.yaml prompt template for {service_name}")
                return prompt_template
    except Exception as e:
        logger.debug(f"Could not load prompt template from app.yaml: {e}")
    
    # For services that don't need templates (like PromptService), return a pass-through template
    if service_name == 'prompt':
        logger.debug(f"Using default pass-through template for {service_name}")
        return '{user_input}'  # Simple pass-through for generic prompts
    
    # For other services, this is an error
    logger.error(f"No prompt template found for service {service_name}")
    raise RuntimeError(
        f"Prompt template for service '{service_name}' not found. "
        f"Please ensure config/app.yaml contains a 'services.{service_name}.prompt' setting."
    )


def get_service_grounding(service_name: str) -> bool:
    """Get grounding configuration for a service.
    
    Args:
        service_name: The service name
        
    Returns:
        True if grounding is enabled for this service, False otherwise
    """
    try:
        services_config = _load_services_config()
        if services_config:
            services = services_config.get('services', {})
            service_config = services.get(service_name, {})
            grounding = service_config.get('grounding', False)
            logger.debug(f"Service {service_name} grounding: {grounding}")
            return grounding
    except Exception as e:
        logger.debug(f"Could not load grounding config from app.yaml: {e}")
    
    # Default to False if no configuration found
    return False


def get_service_config(service_name: str) -> dict:
    """Get the complete configuration for a service.
    
    Args:
        service_name: The service name
        
    Returns:
        Dictionary containing service configuration
        
    Raises:
        RuntimeError: If the service is not found
    """
    services_config = _load_services_config()
    services = services_config.get('services', {})
    service_config = services.get(service_name, {})
    
    if not service_config:
        available_services = list(services.keys())
        raise RuntimeError(
            f"Service '{service_name}' not found. "
            f"Available services: {', '.join(available_services) if available_services else 'none'}. "
            f"Please ensure config/app.yaml contains a 'services.{service_name}' section."
        )
    
    return service_config


class MetaModelResponse(BaseModel):
    """Metadata about the AI model used and processing details."""
    model: str = Field(description="Name of the AI model used")
    provider: str = Field(description="Name of the AI provider/client used")
    time: Optional[float] = Field(None, description="Processing time in milliseconds")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetaModelResponse':
        """Create MetaModelResponse from dictionary data."""
        return cls(**data)


class ModelBasedServiceResponse(BaseModel):
    """Base class for structured responses from model-based services with metadata."""
    meta: MetaModelResponse = Field(description="Service metadata including provider, model, and timing")
    status: str = Field(description="Service status")


class ModelBasedService:
    """
    Base class for services that use AI models with configuration-driven defaults.
    
    Subclasses must define:
    - service_name: str - The service name as defined in models.yaml
    - operation: str - The operation type
    - schema_name: str - The schema file path for AI structured output
    """
    
    service_name: str  # Must be defined by subclasses
    operation: str  # Must be defined by subclasses
    schema_name: str  # Must be defined by subclasses
    default_model: str = None  # Optional class-level default model
    interface_type: str = "service"  # Interface type for test data 
    
    def __init__(self, model_override: Optional[str] = None):
        """
        Initialize the service with model configuration.
        
        Args:
            model_override: Optional model name to override the service default
        """
        if not hasattr(self, 'service_name'):
            raise NotImplementedError(f"Subclass {self.__class__.__name__} must define service_name")
        
        if not hasattr(self, 'operation'):
            raise NotImplementedError(f"Subclass {self.__class__.__name__} must define operation")
        
        if not hasattr(self, 'schema_name'):
            raise NotImplementedError(f"Subclass {self.__class__.__name__} must define schema_name (schema file path)")
        
        # Get the default model for this service
        if model_override:
            self.model_name = model_override
            logger.debug(f"Using model override: {model_override}")
        else:
            # Pass class default to the resolution function
            class_default = getattr(self, 'default_model', None)
            self.model_name = get_service_default_model(self.service_name, class_default)
            logger.debug(f"Using resolved default model: {self.model_name}")
        
        # Get grounding configuration for this service
        self._enable_grounding = get_service_grounding(self.service_name)
        logger.debug(f"Service {self.service_name} grounding enabled: {self._enable_grounding}")
        
        # Initialize the AI client based on provider configuration
        self._init_ai_client()
    
    def _init_ai_client(self):
        """Initialize the appropriate AI client based on provider configuration."""
        # Use the factory to create the appropriate client
        from .factory import create
        
        self.ai_client = create(
            service_name=self.service_name,
            model_override=self.model_name
        )
        
        # Load and set the schema for this service
        self._load_and_set_schema()
    
    def _load_and_set_schema(self):
        """Load the schema file and set it on the AI client."""
        try:
            import json
            from pathlib import Path
            
            # Resolve the schema path
            schema_filename = self.schema_name
            
            # Add .json extension if not present
            if not schema_filename.endswith('.json'):
                schema_filename = f"{schema_filename}.json"
            
            schema_file = Path(schema_filename)
            if not schema_file.is_absolute():
                # If relative path, assume it's relative to core/schemas
                schema_file = Path("core/schemas") / schema_filename
            
            if not schema_file.exists():
                raise FileNotFoundError(f"Schema file not found: {schema_file}")
            
            # Load the schema
            with open(schema_file, 'r') as f:
                schema = json.load(f)
            
            # Set the schema on the AI client
            self.ai_client.set_schema(schema)
            logger.debug(f"Loaded and set schema from {schema_file} for {self.service_name}")
            
        except Exception as e:
            logger.error(f"Failed to load schema for {self.service_name}: {e}")
            raise RuntimeError(f"Failed to load schema for {self.service_name}: {e}")
    
    def _call_ai_client(self, prompt: str, schema: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        logger.debug(f"About to call AI client process_prompt, schema provided: {bool(schema)}")
        try:
            # Use provided schema if available, otherwise the AI client will use its stored schema
            if schema:
                result = self.ai_client.process_prompt(prompt, function_declarations=[schema], **kwargs)
            else:
                result = self.ai_client.process_prompt(prompt, **kwargs)
            logger.debug(f"AI client returned: {type(result)}")
            
            # If we got structured output (JSON string), parse it
            if isinstance(result, str):
                try:
                    import json
                    parsed_result = json.loads(result)
                    logger.debug(f"✅ Parsed structured output: {type(parsed_result)}")
                    return parsed_result
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse structured output as JSON: {e}")
                    return result
            
            return result
        except Exception as e:
            logger.error(f"AI client raised exception: {type(e).__name__}: {e}", exc_info=True)
            raise
    
    def _process_ai_response(self, ai_response: Dict[str, Any], meta: 'MetaModelResponse') -> 'ModelBasedServiceResponse':
        """
        Service-specific callback to process AI function call results.
        This is where domain-specific business logic happens.
        
        Args:
            ai_response: Response returned by the AI function call
            meta: Metadata about the AI model and processing time
            
        Returns:
            Processed result as a ModelBasedServiceResponse subclass
        """
        # This is a base implementation - subclasses should override
        raise NotImplementedError("Subclasses must implement _process_ai_response method")
    
    def process(self, user_input: str, **kwargs) -> 'ModelBasedServiceResponse':
        """
        Process user input using the AI model.
        
        This is the main entry point for AI services. It handles:
        1. Prompt processing through the AI client
        2. Response validation and parsing
        3. Metadata creation
        4. Response formatting
        
        Args:
            user_input: The user's input text
            **kwargs: Additional arguments for the AI client
            
        Returns:
            ModelBasedServiceResponse with processed results and metadata
        """
        import time
        start_time = time.time()
        
        try:
            # Process the input through the AI client with grounding if enabled
            ai_response = self.ai_client.process_prompt(user_input, enable_grounding=self._enable_grounding, **kwargs)
            
            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000
            
            # Get provider information
            provider_name = type(self.ai_client).__name__
            
            # Create metadata
            meta = MetaModelResponse(
                provider=provider_name,
                model=self.model_name,
                time=processing_time
            )
            
            # Process the AI response through the child class
            if hasattr(self, '_process_ai_response'):
                processed_result = self._process_ai_response(ai_response, meta)
            else:
                # Default processing - just return the raw response
                processed_result = ai_response
            
            # The child class must return a proper response object
            if isinstance(processed_result, ModelBasedServiceResponse):
                return processed_result
            else:
                # Child class failed to return proper response type
                raise RuntimeError(f"Child class returned unexpected type: {type(processed_result)}")
                
        except Exception as e:
            # Calculate processing time even for errors
            processing_time = (time.time() - start_time) * 1000
            
            # Create metadata for error response
            meta = MetaModelResponse(
                provider=type(self.ai_client).__name__,
                model=self.model_name,
                time=processing_time
            )
            
            # Child classes must handle their own error responses
            # The base class cannot assume what fields child classes need
            raise RuntimeError(f"Child class failed to handle error: {str(e)}")
