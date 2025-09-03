"""
Abstract interface for secrets management.

Defines the contract for different secrets storage implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List


class PassphraseRequiredException(Exception):
    """Raised when a passphrase is required but not provided."""
    pass


class InvalidPassphraseException(Exception):
    """Raised when an invalid passphrase is provided."""
    pass


class SecretsManager(ABC):
    """Abstract base class for secrets management implementations."""
    
    @abstractmethod
    def get_secret(self, secret_name: str, passphrase: Optional[str] = None) -> Optional[str]:
        """Get a secret value by name.
        
        Args:
            secret_name: Name of the secret to retrieve
            passphrase: Optional passphrase for encrypted storage
            
        Returns:
            Secret value if found, None otherwise
            
        Raises:
            PassphraseRequiredException: If passphrase is required but not provided
            InvalidPassphraseException: If provided passphrase is invalid
        """
        pass
    
    @abstractmethod
    def set_secret(self, secret_name: str, secret_value: str, passphrase: Optional[str] = None) -> bool:
        """Set a secret value.
        
        Args:
            secret_name: Name of the secret
            secret_value: Value to store
            passphrase: Optional passphrase for encrypted storage
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            PassphraseRequiredException: If passphrase is required but not provided
            InvalidPassphraseException: If provided passphrase is invalid
        """
        pass
    
    @abstractmethod
    def delete_secret(self, secret_name: str, passphrase: Optional[str] = None) -> bool:
        """Delete a secret.
        
        Args:
            secret_name: Name of the secret to delete
            passphrase: Optional passphrase for encrypted storage
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            PassphraseRequiredException: If passphrase is required but not provided
            InvalidPassphraseException: If provided passphrase is invalid
        """
        pass
    
    @abstractmethod
    def list_secrets(self, passphrase: Optional[str] = None) -> List[str]:
        """List all available secret names.
        
        Args:
            passphrase: Optional passphrase for encrypted storage
            
        Returns:
            List of secret names
            
        Raises:
            PassphraseRequiredException: If passphrase is required but not provided
            InvalidPassphraseException: If provided passphrase is invalid
        """
        pass
    
    @abstractmethod
    def exists(self, secret_name: str, passphrase: Optional[str] = None) -> bool:
        """Check if a secret exists.
        
        Args:
            secret_name: Name of the secret to check
            passphrase: Optional passphrase for encrypted storage
            
        Returns:
            True if secret exists, False otherwise
            
        Raises:
            PassphraseRequiredException: If passphrase is required but not provided
            InvalidPassphraseException: If provided passphrase is invalid
        """
        pass
    
    @property
    @abstractmethod
    def manager_type(self) -> str:
        """Return the type of secrets manager (e.g., 'google', 'local')."""
        pass
