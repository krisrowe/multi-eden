"""
Base validator class for configuration validation.

This module provides the abstract base class that all configuration validators
must inherit from. Validators are used to validate staged environment variables
before they are applied to the environment.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ..models import StagedVariable, LoadParams


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
    def validate(self, staged_vars: Dict[str, StagedVariable], 
                params: LoadParams) -> None:
        """Validate staged variables.
        
        This method should check if the required conditions are met. If the conditions
        are not met (e.g., the variable that triggers this validator is not present),
        the method should simply return without doing anything. If the conditions are
        met but validation fails, raise a ConfigException.
        
        Args:
            staged_vars: Dictionary of staged environment variables with metadata
            params: Load parameters providing context for validation
            
        Raises:
            ConfigException: If validation fails when conditions are met
        """
        pass
