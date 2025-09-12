"""
Base client for AI model interactions.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from .services import get_prompt

logger = logging.getLogger(__package__)


class ModelClient(ABC):
    """
    Base class for AI model clients.
    
    Handles prompt template injection and provides access to the original user prompt.
    """
    
    interface_type: str = "llm"  # Interface type for test data
    
    def __init__(self, service_name: str):
        """
        Initialize the model client.
        
        Args:
            service_name: Name of the service.
                         If None, no prompt template will be loaded.
        """
        self.service_name = service_name
        self.original_prompt = None  # Will store the user's original input
        self._schema = None  # Will store the loaded schema
        
        # Load the prompt template for this service (only if service_name is provided)
        if service_name is not None:
            try:
                self.prompt_template = get_prompt(service_name)
                logger.debug(f"Loaded prompt template for service {service_name}")
            except Exception as e:
                logger.error(f"Failed to get prompt template for service {service_name}: {e}")
                raise
        else:
            self.prompt_template = None
            logger.debug("No service name provided, skipping prompt template loading")
    
    def set_schema(self, schema: Dict[str, Any]) -> None:
        """
        Set the schema for structured output.
        
        Args:
            schema: The schema dictionary to use for structured output
        """
        self._schema = schema
        logger.debug(f"Schema set for {self.service_name}: {type(schema)}")
    
    def get_schema(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently set schema.
        
        Returns:
            The schema dictionary or None if no schema is set
        """
        return self._schema
    
    def process_prompt(self, user_prompt: str, function_declarations: Optional[List[Dict[str, Any]]] = None, 
                      callback: Optional[Callable] = None, enable_grounding: bool = False, **kwargs) -> Any:
        """
        Process a prompt by injecting it into the template and delegating to child class.
        
        Args:
            user_prompt: The user's original input prompt
            function_declarations: Optional function declarations for structured output
            callback: Optional callback function to process results
            enable_grounding: Whether to enable Google Search grounding
            **kwargs: Additional arguments passed to child class
            
        Returns:
            The result from the child class's _process_prompt method
        """
        # Store the original user prompt for child classes to access
        self.original_prompt = user_prompt
        
        # Inject the user prompt into the template (if template exists)
        if self.prompt_template is not None:
            formatted_prompt = self.prompt_template.format(user_input=user_prompt)
            logger.debug(f"Original user prompt: {user_prompt}")
            logger.debug(f"Formatted prompt: {formatted_prompt}")
        else:
            # No template available, use user prompt directly
            formatted_prompt = user_prompt
            logger.debug(f"No prompt template available, using user prompt directly: {user_prompt}")
        
        # Delegate to child class implementation
        return self._process_prompt(formatted_prompt, function_declarations, callback, enable_grounding, **kwargs)
    
    @abstractmethod
    def _process_prompt(self, formatted_prompt: str, function_declarations: Optional[List[Dict[str, Any]]] = None,
                       callback: Optional[Callable] = None, enable_grounding: bool = False, **kwargs) -> Any:
        """
        Process the formatted prompt. Override this method in child classes.
        
        Args:
            formatted_prompt: The prompt with user input injected into the template
            function_declarations: Optional function declarations for structured output
            callback: Optional callback function to process results
            enable_grounding: Whether to enable Google Search grounding
            **kwargs: Additional arguments
            
        Returns:
            The processed result
        """
        pass
    
    def get_original_prompt(self) -> Optional[str]:
        """
        Get the original user prompt that was passed to process_prompt.
        
        Returns:
            The original user prompt or None if not set
        """
        return self.original_prompt
