"""
Authentication Configuration

Provides auth-specific configuration using the unified settings system.
"""
from dataclasses import dataclass
from typing import List, Optional
from multi_eden.run.config.settings import get_setting, SettingValueNotFoundException

# Global override for testing
_authorization_override: Optional['Authorization'] = None


@dataclass
class Authorization:
    """Authorization configuration for user access control."""
    all_authenticated_users: bool
    allowed_user_emails: list[str]


def get_authorization_config() -> Authorization:
    """Get authorization configuration from settings.
    
    Returns:
        Authorization configuration loaded from settings.
        
    Raises:
        RuntimeError: If authorization configuration cannot be loaded.
    """
    # Check for testing override first
    global _authorization_override
    if _authorization_override is not None:
        return _authorization_override
        
    try:
        # Try to get allowed user emails from setting (comma-separated)
        try:
            allowed_emails_str = get_setting('allowed-user-emails')
        except SettingValueNotFoundException:
            # Setting not available (testing environment) - use empty defaults
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


def is_custom_auth_enabled() -> bool:
    """Check if custom authentication is enabled.
    
    Returns:
        True if custom auth is enabled, False otherwise
    """
    return get_setting('custom-auth-enabled') == 'true'


def set_authorization(authorization: Authorization) -> None:
    """Set authorization configuration for testing.
    
    This temporarily overrides the authorization configuration
    for testing purposes using a global override mechanism.
    
    Args:
        authorization: Authorization instance to set
    """
    global _authorization_override
    _authorization_override = authorization


def reset_authorization() -> None:
    """Reset authorization to use environment variables (clear override).
    
    This restores normal authorization loading from environment variables
    without modifying any environment variables in the process.
    """
    global _authorization_override
    _authorization_override = None
