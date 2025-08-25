"""
Model-specific translators for converting AI responses to domain models.

Each translator handles the specific response format and structure
of different AI model families (Gemini, OpenAI, Claude, etc.).
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, TypeVar, Generic, Type
from pydantic import BaseModel, ValidationError
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class ModelTranslator(ABC, Generic[T]):
    """Abstract base class for model-specific translators."""
    
    @abstractmethod
    def translate_response(self, ai_response: Dict[str, Any], target_model: Type[T]) -> T:
        """Translate AI response to target domain model.
        
        Args:
            ai_response: Raw response from AI model
            target_model: Pydantic model class to translate to
            
        Returns:
            Validated domain model instance
            
        Raises:
            ValidationError: If translation fails
        """
        pass

class GeminiTranslator(ModelTranslator):
    """Translator for Gemini model responses.
    
    Works for both real Gemini API responses and MockGemini responses
    since they return the same format.
    """
    
    def translate_response(self, ai_response: Dict[str, Any], target_model: Type[T]) -> T:
        """Translate Gemini response to target domain model.
        
        Gemini returns function call arguments directly, so we can
        usually pass them through with minimal transformation.
        """
        try:
            # Gemini returns function call args directly
            # For most cases, this maps 1:1 to our domain models
            translated = target_model.model_validate(ai_response)
            logger.debug(f"✅ Gemini response translated to {target_model.__name__}")
            return translated
        except ValidationError as e:
            logger.error(f"❌ Gemini translation failed: {e}")
            raise ValidationError(f"Gemini response translation failed: {e}")

# Registry of translators by model family
TRANSLATORS = {
    "gemini": GeminiTranslator(),
    # Add more translators as needed for different model families:
    # "openai": OpenAITranslator(),
    # "claude": ClaudeTranslator(),
}

def get_translator(model_family: str) -> ModelTranslator:
    """Get the appropriate translator for a model family.
    
    Args:
        model_family: Name of the model family (e.g., "gemini", "openai")
        
    Returns:
        Translator instance for the model family
        
    Raises:
        ValueError: If no translator exists for the model family
    """
    if model_family not in TRANSLATORS:
        raise ValueError(f"No translator available for model family: {model_family}")
    
    return TRANSLATORS[model_family]
