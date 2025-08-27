"""
Runtime secrets configuration from environment variables.

This module provides runtime access to secrets via environment variables.
For build/deploy operations that need to load from JSON files, use the build package.
"""
import os
from dataclasses import dataclass
from typing import List


@dataclass
class Authorization:
    """Authorization configuration from environment variables."""
    all_authenticated_users: bool
    allowed_user_emails: List[str]


@dataclass
class SecretsConfig:
    """Runtime secrets configuration from environment variables.
    
    Contains all secrets loaded from environment variables.
    This is separate from the build package that loads from JSON files.
    """
    salt: str
    google_api_key: str  # Kept for backward compatibility but not used
    authorization: Authorization
    
    @classmethod
    def from_environment(cls) -> 'SecretsConfig':
        """Create SecretsConfig from environment variables.
        
        Returns:
            SecretsConfig instance
            
        Raises:
            ValueError: If required environment variables are missing
        """
        # Get salt from environment variable
        salt = os.environ.get('CUSTOM_AUTH_SALT')
        if not salt:
            raise ValueError("CUSTOM_AUTH_SALT environment variable is required but not set")
        
        # Get authorization settings from environment variables
        all_authenticated_users = os.environ.get('ALL_AUTHENTICATED_USERS', 'false').lower() in ('true', '1', 'yes', 'on')
        
        # Get allowed user emails from environment variable (comma-separated)
        allowed_emails_str = os.environ.get('ALLOWED_USER_EMAILS', '')
        allowed_user_emails = [email.strip() for email in allowed_emails_str.split(',') if email.strip()] if allowed_emails_str else []
        
        # Create authorization object
        authorization = Authorization(
            all_authenticated_users=all_authenticated_users,
            allowed_user_emails=allowed_user_emails
        )
        
        return cls(
            salt=salt,
            google_api_key="",  # No longer used, but kept for backward compatibility
            authorization=authorization
        )
