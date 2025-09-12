"""
Google AI client for interacting with Google's AI models.
"""

import logging
import json
from typing import Dict, Any, Optional, List, Callable
from .base_client import ModelClient

logger = logging.getLogger(__package__)

# Suppress verbose logging from external libraries
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


class GoogleClient(ModelClient):
    """Google AI client for interacting with Google's AI models."""
    
    def __init__(self, model_name: str, service_name: str = None):
        """
        Initialize the Google AI client.
        
        Args:
            model_name: Name of the Gemini model to use
            service_name: Name of the service (e.g., 'meal_analysis', 'meal_segmentation')
        """
        super().__init__(service_name)
        self.model_name = model_name
        logger.debug(f"Initialized GoogleClient with model: {model_name}")
        
        # Initialize Gemini client
        try:
            from google import genai
            self.client = genai.Client()
            logger.debug("Successfully initialized Google GenAI client")
        except ImportError:
            logger.error("Google GenAI library not installed. Install with: pip install google-genai")
            raise ImportError("Google GenAI library required for GoogleClient")
        except Exception as e:
            logger.error(f"Failed to initialize Google AI client: {e}")
            raise
    
    def _process_prompt(self, formatted_prompt: str, function_declarations: Optional[List[Dict[str, Any]]] = None,
                       callback: Optional[Callable] = None, enable_grounding: bool = False, **kwargs) -> Any:
        """
        Process the formatted prompt using the real Gemini API.
        
        Args:
            formatted_prompt: The prompt with user input injected into the template
            function_declarations: Optional function declarations for structured output
            callback: Optional callback function to process results
            enable_grounding: Whether to enable Google Search grounding
            **kwargs: Additional arguments
            
        Returns:
            The processed result from Gemini API
        """
        logger.debug(f"GoogleClient processing prompt: {formatted_prompt[:100]}...")
        
        try:
            # Prepare the generation config
            generation_config = {}
            tools = []
            
            # Handle structured output vs grounding tools (mutually exclusive)
            has_structured_output = function_declarations or self.get_schema()
            
            if has_structured_output:
                # Use structured output (no grounding tools)
                if function_declarations:
                    generation_config["response_mime_type"] = "application/json"
                    generation_config["response_schema"] = function_declarations
                    logger.debug(f"Using function declarations for structured output: {len(function_declarations)} functions")
                elif self.get_schema():
                    generation_config["response_mime_type"] = "application/json"
                    generation_config["response_schema"] = self.get_schema()
                    logger.debug(f"Using stored schema for structured output: {type(self.get_schema())}")
            elif enable_grounding:
                # Use grounding tools (no structured output)
                try:
                    from google.genai import types
                    grounding_tool = types.Tool(
                        google_search=types.GoogleSearch()
                    )
                    tools.append(grounding_tool)
                    logger.debug("Added Google Search grounding tool")
                except ImportError:
                    logger.warning("Google GenAI types not available for grounding, proceeding without grounding")
                except Exception as e:
                    logger.warning(f"Failed to set up grounding tool: {e}, proceeding without grounding")
            
            # Prepare the config object
            config_kwargs = {}
            if tools:
                config_kwargs['tools'] = tools
            if generation_config:
                config_kwargs.update(generation_config)
            
            # Create the config object if we have any configuration
            if config_kwargs:
                from google.genai import types
                config = types.GenerateContentConfig(**config_kwargs)
            else:
                config = generation_config if generation_config else None
            
            # Make the API call
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=formatted_prompt,
                config=config
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

