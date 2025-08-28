"""
Secret loading utilities for build tasks.

Handles loading secrets from Secret Manager or generating ephemeral values
based on the manifest configuration.
"""

import os
import logging
from typing import Dict, Any, Optional

from ...run.config.secrets import load_secrets_manifest

logger = logging.getLogger(__name__)


def load_env(env_name: str, repo_root=None) -> None:
    """Load configuration and set up all environment variables for build tasks.
    
    Args:
        env_name: Environment name (e.g., 'dev', 'prod', 'unit-testing')
        repo_root: Repository root path (unused, kept for compatibility)
    """
    from pathlib import Path
    from ...run.config.unified_settings import get_environment_settings
    
    logger.debug(f"Loading environment configuration for: {env_name}")
    
    try:
        # Get unified environment settings
        settings = get_environment_settings(env_name)
        
        # Collect environment variables and their sources for table display
        env_vars_info = []
        
        # Set environment variables from settings (skip special keys)
        for key, value in settings.items():
            if key in ['local', 'project_id']:  # Skip special keys
                continue
            env_var = key.upper()
            was_set = env_var in os.environ
            os.environ.setdefault(env_var, str(value))
            source = "Pre-existing" if was_set else "Test suite setting"
            env_vars_info.append((env_var, str(value), source))
        
        # Handle project ID if set
        if settings.get('project_id'):
            was_set = 'PROJECT_ID' in os.environ
            os.environ.setdefault('PROJECT_ID', settings['project_id'])
            source = "Pre-existing" if was_set else "Test suite setting"
            env_vars_info.append(('PROJECT_ID', settings['project_id'], source))
        
        # Display environment variables table
        if env_vars_info:
            print("\n" + "=" * 65)
            print("🔧 ENVIRONMENT VARIABLES")
            print("=" * 65)
            print(f"{'VARIABLE':<25} {'VALUE':<12} {'SOURCE':<20}")
            print("-" * 65)
            for env_var, value, source in env_vars_info:
                # Truncate long values for display (max 12 chars)
                display_value = value if len(value) <= 12 else value[:9] + "..."
                print(f"{env_var:<25} {display_value:<12} {source:<20}")
            print("=" * 65)
        
        if not settings.get('project_id'):
            print(f"   ✅ No project ID - using local configuration")
        
        # Set up secrets environment
        _setup_secrets_environment(settings, env_name)
        
        if settings.get('project_id'):
            pass  # Secrets loaded from Secret Manager
        elif settings.get('local'):
            pass  # Local default secrets configured for testing
        else:
            pass  # No secrets configured (none required)
        
        # Authorization is now handled through allowed-user-emails secret
        
    except Exception as e:
        print(f"   ❌ Failed to load environment configuration: {e}")
        raise RuntimeError(f"Environment configuration failed: {e}")


def _setup_secrets_environment(settings: Dict[str, Any], config_env: str) -> None:
    """Set up environment variables for secrets based on execution context."""
    secrets_manifest = load_secrets_manifest()
    
    for secret in secrets_manifest:
        # Check if secret is required for current settings
        if not _is_secret_required(secret, settings):
            pass  # Skipping secret - not required for current settings
            continue
            
        # Skip secrets without local default when API is out-of-process
        api_in_memory = settings.get('api_in_memory', True)
        if not secret.local_default and not api_in_memory:
            pass  # Skipping secret - no local default and API is out-of-process
            continue
            
        # Set up the environment variable
        try:
            _setup_secret_env_var(secret, settings, config_env)
        except Exception as e:
            print(f"❌ Failed to setup secret {secret.name}: {e}")
            raise


def _setup_secret_env_var(secret_def, settings: Dict[str, Any], config_env: str) -> None:
    """Set up environment variable for a specific secret."""
    # Skip if already set
    if os.getenv(secret_def.env_var):
        pass  # Environment variable already set
        return
    
    project_id = settings.get('project_id')
    is_local = settings.get('local', False)
    
    # Priority 1: project_id always takes precedence (Secret Manager)
    if project_id:
        value = _get_secret_from_manager(project_id, secret_def.name)
        if not value:
            raise RuntimeError(f"Secret '{secret_def.name}' not found in Secret Manager for project '{project_id}'")
        os.environ[secret_def.env_var] = value
        pass  # Loaded secret from Secret Manager
        return
    
    # Priority 2: local default (only if local: true AND local_default exists)
    if is_local:
        if not secret_def.local_default:
            raise RuntimeError(
                f"Secret '{secret_def.name}' requires local_default in secrets manifest when no project_id is specified."
            )
        value = _expand_local_default(secret_def.local_default, config_env)
        os.environ[secret_def.env_var] = value
        pass  # Set secret from local default
        return
    
    # No valid configuration - always fail
    raise RuntimeError(
        f"Secret '{secret_def.name}' requires either project_id for Secret Manager "
        f"or local: true with local_default in secrets manifest."
    )


def _is_secret_required(secret, settings: Dict[str, Any]) -> bool:
    """Check if a secret is required based on current settings."""
    if not secret.required_when:
        return True
        
    for key, expected_value in secret.required_when.items():
        setting_value = settings.get(key)
        if setting_value != expected_value:
            return False
            
    return True


# Removed _generate_ephemeral_secret_value - now using local_override approach


def _get_secret_from_manager(project_id: str, secret_name: str) -> Optional[str]:
    """Get secret value from Google Secret Manager."""
    try:
        from google.cloud import secretmanager
        
        client = secretmanager.SecretManagerServiceClient()
        secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        
        pass  # Fetching secret from Secret Manager
        response = client.access_secret_version(request={"name": secret_path})
        
        secret_value = response.payload.data.decode("UTF-8")
        pass  # Successfully retrieved secret from Secret Manager
        return secret_value
        
    except ImportError:
        pass  # Google Cloud Secret Manager library not available
        return None
    except Exception as e:
        print(f"❌ Failed to retrieve secret '{secret_name}' from Secret Manager: {e}")
        raise RuntimeError(f"Secret Manager access failed: {e}")


def _expand_local_default(local_default: str, config_env: str) -> str:
    """Expand placeholders in local_default string.
    
    Supported placeholders:
    - {env}: config environment name
    - {app-id}: application ID from app.yaml
    """
    app_id = _get_app_id()
    expanded = local_default.replace('{env}', config_env)
    expanded = expanded.replace('{app-id}', app_id)
    return expanded


def _get_app_id() -> str:
    """Get application ID from app.yaml."""
    try:
        import yaml
        from pathlib import Path
        
        app_yaml_path = Path.cwd() / 'config' / 'app.yaml'
        if not app_yaml_path.exists():
            # Fallback to generic app ID
            return 'multi-eden-app'
            
        with open(app_yaml_path, 'r') as f:
            app_config = yaml.safe_load(f)
            
        app_id = app_config.get('app_id') or app_config.get('id')
        if not app_id:
            # Fallback to generic app ID
            return 'multi-eden-app'
            
        return app_id
        
    except Exception as e:
        # Silently fallback to generic app ID
        return 'multi-eden-app'
