"""
Generic prompt service for AI interactions without schemas.

This service provides a simple interface for sending prompts to AI models
without requiring structured output schemas. It's designed to be a sibling
of domain-specific services like MealAnalysisService.
"""

import logging
from typing import Optional, Dict, Any
from pydantic import Field
from .services import ModelBasedService, ModelBasedServiceResponse, MetaModelResponse

logger = logging.getLogger(__name__)


class PromptResponse(ModelBasedServiceResponse):
    """Response model for generic prompt service."""
    content: str = Field(description="The AI model's response content")


class PromptService(ModelBasedService):
    """
    Generic service for AI prompt interactions without structured schemas.
    
    This service is designed for simple prompt-response interactions where
    you don't need structured output. It's a sibling to domain-specific
    services like MealAnalysisService and MealSegmentationService.
    """
    
    service_name = 'prompt'
    operation = 'prompt'
    schema_name = None  # No schema required for generic prompts
    default_model = 'gemini-2.5-flash'  # Class-level default
    
    def __init__(self, model_override: Optional[str] = None, service_name: str = 'prompt'):
        """
        Initialize the prompt service.
        
        Args:
            model_override: Optional model name to override the service default
            service_name: Service name to use for configuration lookup (default: 'prompt')
        """
        # Allow service_name to be overridden for flexibility
        self.service_name = service_name
        super().__init__(model_override)
    
    def _load_and_set_schema(self):
        """Override to skip schema loading for generic prompts."""
        # Generic prompts don't need schemas
        logger.debug(f"Skipping schema loading for generic prompt service '{self.service_name}'")
    
    def process(self, user_input: str, **kwargs) -> PromptResponse:
        """Process user input with validation for empty prompts."""
        # Validate input
        if not user_input or not user_input.strip():
            raise ValueError("Prompt text cannot be empty or whitespace-only")
        
        # Call parent process method
        return super().process(user_input, **kwargs)
    
    def _process_ai_response(self, ai_response: Any, meta: MetaModelResponse) -> PromptResponse:
        """
        Process AI response for generic prompts.
        
        Args:
            ai_response: Raw response from the AI model
            meta: Metadata about the AI model and processing time
            
        Returns:
            PromptResponse with the AI's content
        """
        logger.debug("Processing AI response for generic prompt")
        
        try:
            # Handle different response types
            if isinstance(ai_response, str):
                content = ai_response
            elif isinstance(ai_response, dict) and 'content' in ai_response:
                content = ai_response['content']
            elif isinstance(ai_response, dict) and 'text' in ai_response:
                content = ai_response['text']
            else:
                # Convert to string as fallback
                content = str(ai_response)
            
            return PromptResponse(
                meta=meta,
                status='success',
                content=content.strip()
            )
            
        except Exception as e:
            logger.error(f"Failed to process AI response: {e}")
            return PromptResponse(
                meta=meta,
                status='error',
                content=f"Error processing response: {str(e)}"
            )
