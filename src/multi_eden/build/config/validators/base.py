"""
Base validator class for configuration validation.

This module provides the abstract base class that all configuration validators
must implement. Validators are called during the load_env process to validate
staged variables before they are applied to the environment.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional


class BaseValidator(ABC):
    """Abstract base class for configuration validators.
    
    Validators are called during the load_env process to validate staged variables
    before they are applied to the environment. Each validator can check for
    specific configuration requirements and raise ConfigException if validation fails.
    """
    
    def __init__(self, name: str = None):
        """Initialize the validator.
        
        Args:
            name: Optional name for the validator (defaults to class name)
        """
        self.name = name or self.__class__.__name__
    
    @abstractmethod
    def validate(self, staged_vars: Dict[str, Tuple[str, str]], 
                top_layer: str, target_profile: Optional[str] = None) -> None:
        """Validate staged variables.
        
        Args:
            staged_vars: Dictionary of staged environment variables with source info
            top_layer: The primary environment layer being loaded
            target_profile: Optional target profile for side-loading
            
        Raises:
            ConfigException: If validation fails
        """
        pass
    
    def should_validate(self, staged_vars: Dict[str, Tuple[str, str]], 
                       top_layer: str, target_profile: Optional[str] = None) -> bool:
        """Determine if this validator should run for the given configuration.
        
        Override this method to make validation conditional. By default, all validators run.
        
        Args:
            staged_vars: Dictionary of staged environment variables with source info
            top_layer: The primary environment layer being loaded
            target_profile: Optional target profile for side-loading
            
        Returns:
            bool: True if validation should run, False otherwise
        """
        return True

