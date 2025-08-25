#!/usr/bin/env python3
"""
Base class for authentication providers.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class AuthProvider(ABC):
    """Abstract base class for authentication providers."""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the canonical name of this auth provider."""
        pass
    
    @abstractmethod
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate an authentication token and return user information.
        
        Args:
            token: The authentication token to validate
            
        Returns:
            Dict containing user information (email, uid, etc.)
            
        Raises:
            ValueError: If token is invalid or expired
        """
        pass
    
    @abstractmethod
    def get_test_token(self) -> Dict[str, Any]:
        """
        Generate a test token for testing purposes.
        
        Returns:
            Dict containing token and metadata
        """
        pass
