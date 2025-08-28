"""
Secrets Management System

Provides centralized secrets management with support for:
- Google Secret Manager (cloud environments)
- Environment variables (local/testing)
- Ephemeral secrets (unit testing)
"""
import os
import json
import logging
import secrets
import string
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SecretDefinition:
    """Definition of a secret and how to load it."""
    name: str
    local_default: Optional[str] = None  # Local testing value with {app-id} and {env} placeholder support
    required_when: Optional[Dict[str, Any]] = None
    
    @property
    def env_var(self) -> str:
        """Derive environment variable name from secret name.
        
        Converts 'secret-name' to 'SECRET_NAME'
        """
        return self.name.replace('-', '_').upper()


@dataclass
class Authorization:
    """Authorization configuration."""
    all_authenticated_users: bool
    allowed_user_emails: List[str]


def load_secrets_manifest() -> List[SecretDefinition]:
    """Load secrets configuration from YAML manifest."""
    import yaml
    from pathlib import Path
    
    # Load from build package - build pkg knows structure, not specific names
    manifest_path = Path(__file__).parent.parent.parent / 'build' / 'config' / 'secrets.yaml'
    
    if not manifest_path.exists():
        raise FileNotFoundError(f"Required secrets manifest not found: {manifest_path}")
    
    try:
        with open(manifest_path, 'r') as f:
            config = yaml.safe_load(f)
            
        if not config or 'secrets' not in config:
            raise ValueError(f"Invalid secrets manifest: missing 'secrets' key in {manifest_path}")
            
        secrets = []
        for secret_config in config['secrets']:
            secrets.append(SecretDefinition(
                name=secret_config['name'],
                local_default=secret_config.get('local_default'),
                required_when=secret_config.get('required_when')
            ))
            
        return secrets
        
    except Exception as e:
        raise RuntimeError(f"Failed to load secrets manifest from {manifest_path}: {e}")














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
        secret_name: Name of the secret to retrieve (must match a name in SECRET_DEFINITIONS)
        
    Returns:
        Secret value as string.
        
    Raises:
        RuntimeError: If the secret is not available or invalid.
    """
    # Find the secret definition
    secret_definitions = load_secrets_manifest()
    secret_def = None
    for secret in secret_definitions:
        if secret.name == secret_name:
            secret_def = secret
            break
    
    if not secret_def:
        available_names = [s.name for s in secret_definitions]
        raise RuntimeError(f"Unknown secret name: {secret_name}. Available: {available_names}")
    
    # Get value from environment variable
    value = os.environ.get(secret_def.env_var)
    
    if not value:
        raise RuntimeError(f"Secret '{secret_name}' is required but not set (environment variable: {secret_def.env_var})")
    
    if not value.strip():
        raise RuntimeError(f"Secret '{secret_name}' is empty or contains only whitespace")
    
    return value.strip()
