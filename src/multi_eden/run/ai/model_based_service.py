"""
Base service class for AI-powered services that need model and prompt configuration.
"""
import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Any, Dict, List
from .util import get_service_default_model
from multi_eden.run.config.providers import is_ai_mocked

logger = logging.getLogger(__name__)


class ModelBasedService(ABC):
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
        
        # Prompt template is now handled by ModelClient
        
        # Initialize the AI client based on provider configuration
        self._init_ai_client()

    def _init_ai_client(self):
        """Initialize the appropriate AI client based on provider configuration."""
        ai_mocked = is_ai_mocked()
        logger.debug(f"AI Model Mocked setting from providers: {ai_mocked}")
        
        if ai_mocked:
            # Use MockGeminiClient for mocked responses
            from multi_eden.run.ai.mock_gemini_client import MockGeminiClient
        
            # Use the test helper to get the test data directory path
            from tests.helpers.test_data_helper import get_unit_test_data_folder_path
            test_data_dir = get_unit_test_data_folder_path(self.operation, 'llm-output')
            self.ai_client = MockGeminiClient(str(test_data_dir), self.service_name)
            logger.debug(f"Using {type(self.ai_client).__name__} for mocked responses")
        else:
            # Use real GeminiClient with service-specific default model
            from multi_eden.run.ai.gemini_client import GeminiClient
            self.ai_client = GeminiClient(self.model_name, self.service_name)
            logger.debug(f"Using {type(self.ai_client).__name__} with model: {self.model_name}")
        
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
    
    @abstractmethod
    def _process_ai_response(self, function_name: str, args: Dict[str, Any]) -> Any:
        """
        Service-specific callback to process AI function call results.
        This is where domain-specific business logic happens.
        
        Args:
            function_name: Name of the function that was called
            args: Arguments returned by the AI function call
            
        Returns:
            Processed result
        """
        pass
    

    
    def process(self, user_input: str, **kwargs) -> 'ModelBasedServiceResponse':
        """
        Main processing method that CLI and API call.
        
        Args:
            user_input: The user input to process
            **kwargs: Additional arguments for the specific service
            
        Returns:
            ModelBasedServiceResponse with metadata and processed results
        """
        import time
        
        # Pass the user's original input to the AI client
        # The ModelClient will handle prompt template formatting
        
        # Get provider name (generic)
        provider_name = type(self.ai_client).__name__
        
        # Start timing the AI client process_prompt
        start_time = time.time()
        
        # Call AI client with the user's original input (schema is already set on the client)
        raw_result = self._call_ai_client(user_input, **kwargs)
        
        # End timing and calculate time in milliseconds
        end_time = time.time()
        processing_time_ms = (end_time - start_time) * 1000
        
        # Round to nearest ms if greater than 5ms, otherwise keep 2 decimal places
        if processing_time_ms > 5:
            processing_time_ms = round(processing_time_ms)
        else:
            processing_time_ms = round(processing_time_ms, 2)
        
        # Process the raw AI response through the child class's logic
        processed_result = self._process_ai_response("process", raw_result)
        
        # Import the response class
        from multi_eden.run.ai.services import ModelBasedServiceResponse
        
        # Create structured response with metadata
        if hasattr(processed_result, 'model_dump'):
            # If it's a Pydantic model, extract the data we need
            # Child classes return Pydantic models with items attribute
            items = processed_result.items
            status = processed_result.status
            
            # Return the actual ModelBasedServiceResponse instance
            return ModelBasedServiceResponse.create(
                provider=provider_name,
                model=self.model_name,
                items=items,
                status=status,
                time=processing_time_ms
            )
        elif isinstance(processed_result, dict) and 'items' in processed_result:
            # If the result already has items, use them directly
            items = processed_result.get('items', [])
            status = processed_result.get('status', 'success')
            
            # Return the actual ModelBasedServiceResponse instance
            return ModelBasedServiceResponse.create(
                provider=provider_name,
                model=self.model_name,
                items=items,
                status=status,
                time=processing_time_ms
            )
        else:
            # For other types, wrap them appropriately
            items = [processed_result] if not isinstance(processed_result, list) else processed_result
            status = 'success'
            
            return ModelBasedServiceResponse.create(
                provider=provider_name,
                model=self.model_name,
                items=items,
                status=status,
                time=processing_time_ms
            )
