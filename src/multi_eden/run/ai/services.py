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

logger = logging.getLogger(__name__)

# Generic type for items in ModelBasedServiceResponse
T = TypeVar('T')


def _load_services_config() -> dict:
    """Load services configuration from the SDK's services.yaml."""
    try:
        # Look for services.yaml in the current package directory
        current_file = Path(__file__)
        services_path = current_file.parent / 'services.yaml'
        
        if not services_path.exists():
            raise RuntimeError(f"Services configuration file not found at {services_path}")
        
        with open(services_path, 'r', encoding='utf-8') as f:
            import yaml
            return yaml.safe_load(f) or {}
    except Exception as e:
        raise RuntimeError(f"Failed to load services configuration: {e}")


def get_service_default_model(service_name: str) -> str:
    """Get the default model for a specific service.
    
    Args:
        service_name: The service name
        
    Returns:
        The default model name for the service
        
    Raises:
        RuntimeError: If no default model is configured for the service
    """
    services_config = _load_services_config()
    services = services_config.get('services', {})
    service_config = services.get(service_name, {})
    
    default_model = service_config.get('default_model')
    
    if not default_model:
        available_services = list(services.keys())
        raise RuntimeError(
            f"No default model configured for service '{service_name}'. "
            f"Available services: {', '.join(available_services) if available_services else 'none'}. "
            f"Please ensure the SDK's services.yaml contains a 'services.{service_name}.default_model' setting."
        )
    
    return default_model


def get_prompt(service_name: str) -> str:
    """Get a prompt template by service name.
    
    Args:
        service_name: The service name
        
    Returns:
        The prompt template string
        
    Raises:
        RuntimeError: If the prompt is not found
    """
    services_config = _load_services_config()
    services = services_config.get('services', {})
    service_config = services.get(service_name, {})
    
    prompt_template = service_config.get('prompt', '')
    
    if not prompt_template:
        available_services = list(services.keys())
        raise RuntimeError(
            f"Prompt template for service '{service_name}' not found. "
            f"Available services: {', '.join(available_services) if available_services else 'none'}. "
            f"Please ensure the SDK's services.yaml contains a 'services.{service_name}.prompt' setting."
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
    services_config = _load_services_config()
    services = services_config.get('services', {})
    service_config = services.get(service_name, {})
    
    if not service_config:
        available_services = list(services.keys())
        raise RuntimeError(
            f"Service '{service_name}' not found. "
            f"Available services: {', '.join(available_services) if available_services else 'none'}. "
            f"Please ensure the SDK's services.yaml contains a 'services.{service_name}' section."
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


class MealAnalysisResponse(ModelBasedServiceResponse):
    """Response model for meal analysis service."""
    items: List['ProcessedFood'] = Field(description="List of analyzed food items")
    totals: 'NutritionalInfo' = Field(description="Aggregated nutritional totals")
    verified_calculation: bool = Field(description="Whether calculations were verified")


class MealSegmentationResponse(ModelBasedServiceResponse):
    """Response model for meal segmentation service."""
    items: List[str] = Field(description="List of segmented food item descriptions")


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
            try:
                self.model_name = get_service_default_model(self.service_name)
                logger.debug(f"Using service default model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to get default model for service {self.service_name}: {e}")
                raise
        
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
            # Process the input through the AI client
            ai_response = self.ai_client.process_prompt(user_input, **kwargs)
            
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
