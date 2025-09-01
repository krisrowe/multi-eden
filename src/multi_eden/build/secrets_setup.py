"""
Secrets setup utilities for build tasks.

Provides functions for setting up secrets environment variables
during build task execution.
"""

import os
import logging
from typing import Any

logger = logging.getLogger(__name__)


def setup_secrets_environment(settings: Any) -> None:
    """Set up environment variables for secrets based on execution context.
    
    Args:
        settings: Settings object with configuration
    """
    from multi_eden.build.secrets.manifest import load_secrets_manifest
    
    logger.debug(f"Setting up secrets environment for settings: {settings}")
    
    secret_definitions = load_secrets_manifest()
    for secret_def in secret_definitions:
        logger.debug(f"Checking secret {secret_def.name}")
        
        # Check if secret is required for current settings
        if not _is_secret_required(secret_def, settings):
            logger.debug(f"Skipping secret {secret_def.name} - not required for current settings")
            continue
            
        logger.debug(f"Secret {secret_def.name} is required")
        
        # Skip secrets without local default when API is out-of-process
        if not secret_def.local_default and not settings.test_api_in_memory:
            logger.debug(f"Skipping secret {secret_def.name} - no local default and API is out-of-process")
            continue
            
        logger.debug(f"Setting up secret {secret_def.name}")
        
        # Set up the environment variable
        try:
            _setup_secret_env_var(secret_def, settings)
            logger.debug(f"Successfully set up secret {secret_def.name}")
        except Exception as e:
            print(f"❌ Failed to setup secret {secret_def.name}: {e}")
            raise


def ensure_jwt_secret_available() -> None:
    """Ensure JWT secret is available in environment variables."""
    from multi_eden.build.secrets.manifest import load_secrets_manifest
    
    # Find JWT secret definition
    secret_definitions = load_secrets_manifest()
    jwt_secret_def = None
    for secret_def in secret_definitions:
        if secret_def.name == 'jwt-secret-key':
            jwt_secret_def = secret_def
            break
    
    if not jwt_secret_def:
        raise RuntimeError("JWT secret definition not found in secrets manifest")
    
    # Check if already set
    if os.getenv(jwt_secret_def.env_var):
        return
    
    # Generate ephemeral JWT secret
    import secrets
    import string
    ephemeral_secret = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    os.environ[jwt_secret_def.env_var] = ephemeral_secret
    logger.debug("Generated ephemeral JWT secret")


def _is_secret_required(secret_def: Any, settings: Any) -> bool:
    """Check if a secret is required based on current settings."""
    if not secret_def.required_when:
        return True
        
    for key, expected_value in secret_def.required_when.items():
        setting_value = getattr(settings, key, None)
        if setting_value != expected_value:
            return False
            
    return True


def _setup_secret_env_var(secret_def: Any, settings: Any) -> None:
    """Set up environment variable for a specific secret."""
    # Skip if already set
    if os.getenv(secret_def.env_var):
        logger.debug(f"Secret {secret_def.name} already set in environment")
        return
    
    project_id = settings.project_id
    is_local = settings.local
    
    # Priority 1: project_id always takes precedence (Secret Manager)
    if project_id:
        from multi_eden.build.secrets.secrets_manager import get_secret_manager_value
        value = get_secret_manager_value(project_id, secret_def.name)
        if not value:
            raise RuntimeError(f"Secret '{secret_def.name}' not found in Secret Manager for project '{project_id}'")
        os.environ[secret_def.env_var] = value
        logger.debug(f"Loaded secret {secret_def.name} from Secret Manager")
        return
    
    # Priority 2: local default (only if local: true AND local_default exists)
    if is_local:
        if not secret_def.local_default:
            raise RuntimeError(
                f"Secret '{secret_def.name}' requires local_default in secrets manifest when no project_id is specified."
            )
        value = _expand_local_default(secret_def.local_default, settings)
        os.environ[secret_def.env_var] = value
        logger.debug(f"Set secret {secret_def.name} from local default")
        return
    
    # No valid configuration - always fail
    raise RuntimeError(
        f"Secret '{secret_def.name}' requires either project_id for Secret Manager "
        f"or local: true with local_default in secrets manifest."
    )


def _expand_local_default(local_default: str, settings: Any) -> str:
    """Expand placeholders in local_default string.
    
    Supported placeholders:
    - {app-id}: application ID from settings
    """
    app_id = settings.app_id or 'multi-eden-app'
    expanded = local_default.replace('{app-id}', app_id)
    return expanded
