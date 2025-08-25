"""
Gemini client for real AI model interactions.
"""
import logging
import json
from typing import Dict, Any, Optional, List, Callable
from .base_client import ModelClient

logger = logging.getLogger(__name__)

# Suppress verbose logging from external libraries
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


class GeminiClient(ModelClient):
    """Real Gemini client that makes actual API calls to Google's Gemini model."""

    def __init__(self, model_name: str, service_name: str = None):
        """
        Initialize the Gemini client.
        
        Args:
            model_name: Name of the Gemini model to use
            service_name: Name of the service to load prompt template for. If None, prompt will be provided as is.
        """
        super().__init__(service_name)
        self.model_name = model_name
        self.client = None  # Will be lazily initialized
        logger.debug(f"Initialized GeminiClient with model: {model_name}, service: {service_name}")
    
    def _get_client(self):
        """
        Get or create the Gemini client instance.
        
        This method ensures the client is initialized before returning it.
        The API key must be set via GEMINI_API_KEY environment variable.
        """
        # If client already exists, return it
        if self.client is not None:
            return self.client
        
        # Create the client instance (API key must be set via GEMINI_API_KEY env var)
        try:
            from google import genai
            self.client = genai.Client()
            logger.debug("Successfully initialized Google GenAI client")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise
        
        return self.client
    
    def _process_prompt(self, formatted_prompt: str, function_declarations: Optional[List[Dict[str, Any]]] = None,
                       callback: Optional[Callable] = None, **kwargs) -> Any:
        """
        Process the formatted prompt using the real Gemini API.
        
        Args:
            formatted_prompt: The prompt with user input injected into the template
            function_declarations: Optional function declarations for structured output
            callback: Optional callback function to process results
            **kwargs: Additional arguments
            
        Returns:
            The processed result from Gemini API
        """
        logger.debug(f"GeminiClient processing prompt: {formatted_prompt[:100]}...")
        
        try:
            # Get the client (will initialize if needed)
            client = self._get_client()
            
            # Prepare the generation config
            generation_config = {}
            
            # Handle structured output
            if function_declarations:
                # Use function declarations for structured output
                generation_config["response_mime_type"] = "application/json"
                generation_config["response_schema"] = function_declarations
                logger.debug(f"Using function declarations for structured output: {len(function_declarations)} functions")
            elif self.get_schema():
                # Use stored schema for structured output
                generation_config["response_mime_type"] = "application/json"
                generation_config["response_schema"] = self.get_schema()
                logger.debug(f"Using stored schema for structured output: {type(self.get_schema())}")
            
            # Make the API call
            response = client.models.generate_content(
                model=self.model_name,
                contents=formatted_prompt,
                config=generation_config
            )
            
            logger.debug(f"Gemini API response received successfully")
            
            # Process the response
            if hasattr(response, 'parsed') and response.parsed is not None:
                # Return parsed structured output if available
                result = response.parsed
                logger.debug(f"Returning parsed structured output: {type(result)}")
            else:
                # Return text response
                result = response.text
                logger.debug(f"Returning text response: {len(result)} characters")
            
            # Apply callback if provided
            if callback:
                result = callback(result)
                logger.debug("Applied callback to result")
            
            return result
            
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise RuntimeError(f"Failed to process prompt with Gemini API: {e}")
