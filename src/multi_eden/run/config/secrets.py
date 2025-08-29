"""
Secrets Management System - Runtime Package

Provides runtime access to secrets via environment variables only.
The run package does not use manifest files or build-time configuration.
"""
import os
import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class Authorization:
    """Authorization configuration."""
    all_authenticated_users: bool
    allowed_user_emails: List[str]


# Known secret environment variables - must match build/config/secrets.yaml
SECRET_ENV_VARS = {
    "jwt-secret-key": "JWT_SECRET_KEY",
    "allowed-user-emails": "ALLOWED_USER_EMAILS", 
    "gemini-api-key": "GEMINI_API_KEY"
}














def get_authorization_config() -> Authorization:
    """Get authorization configuration from environment variables.
    
    Returns:
        Authorization configuration loaded from environment.
        
    Raises:
        RuntimeError: If authorization configuration cannot be loaded.
    """
    try:
        # Try to get allowed user emails from secret (comma-separated)
        try:
            allowed_emails_str = get_secret('allowed-user-emails')
        except Exception:
            # Secret not available (testing environment) - use empty defaults
            # Tests will inject their own authorization settings
            allowed_emails_str = None
            
        if allowed_emails_str:
            allowed_user_emails = [email.strip() for email in allowed_emails_str.split(',')]
            # Check if wildcard "*" is present for all authenticated users
            all_authenticated_users = '*' in allowed_user_emails
        else:
            # Default for testing - tests will override as needed
            allowed_user_emails = []
            all_authenticated_users = False
        
        return Authorization(
            all_authenticated_users=all_authenticated_users,
            allowed_user_emails=allowed_user_emails
        )
        
    except Exception as e:
        raise RuntimeError(f"Failed to load authorization configuration: {e}")


def get_secret(secret_name: str) -> str:
    """Get a secret value by name with proper validation.
    
    Args:
        secret_name: Name of the secret to retrieve
        
    Returns:
        Secret value as string.
        
    Raises:
        RuntimeError: If the secret is not available or invalid.
    """
    # Look up environment variable name
    env_var = SECRET_ENV_VARS.get(secret_name)
    
    if not env_var:
        available_names = list(SECRET_ENV_VARS.keys())
        raise RuntimeError(f"Unknown secret name: {secret_name}. Available: {available_names}")
    
    # Get value from environment variable
    value = os.environ.get(env_var)
    
    if not value:
        raise RuntimeError(f"Secret '{secret_name}' is required but not set (environment variable: {env_var})")
    
    if not value.strip():
        raise RuntimeError(f"Secret '{secret_name}' is empty or contains only whitespace")
    
    return value.strip()
