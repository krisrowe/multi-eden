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
    from .settings import load_settings
    
    logger.debug(f"Loading environment configuration for: {env_name}")
    
    try:
        # Load unified settings and environment variables manifest
        settings = load_settings(env_name)
        from .env_vars_manifest import load_env_vars_manifest
        env_vars_manifest = load_env_vars_manifest()
        
        # Set up environment variables from manifest
        env_vars_info = []
        
        # Process each manifest entry
        for env_def in env_vars_manifest:
            env_value = None
            
            source_info = "environments.yaml"  # Default source
            
            if env_def.source == "setting":
                # Auto-derive setting_key: "PROJECT_ID" -> "project_id"
                setting_key = env_def.setting_key or env_def.name.lower()
                
                value = getattr(settings, setting_key, None)
                if value is None:
                    continue  # Skip if setting not present
                    
                # Transform booleans to lowercase strings
                if isinstance(value, bool):
                    env_value = str(value).lower()
                else:
                    env_value = str(value)
                
                source_info = "environments.yaml"
                    
            elif env_def.source == "derived":
                # Check condition first
                if env_def.condition:
                    condition_met = all(
                        getattr(settings, k) == v 
                        for k, v in env_def.condition.items()
                    )
                    if not condition_met:
                        continue  # Skip if condition not met
                
                # Call method on settings
                method = getattr(settings, env_def.method)
                env_value = method()
                source_info = f"{env_def.method}()"
            
            # Set environment variable
            if env_value is not None:
                os.environ.setdefault(env_def.name, env_value)
                env_vars_info.append((env_def.name, env_value, source_info))
        
        # Display environment variables table
        if env_vars_info:
            print("\n" + "=" * 85)
            print("🔧 ENVIRONMENT VARIABLES")
            print("=" * 85)
            print(f"{'VARIABLE':<25} {'VALUE':<34} {'SOURCE':<19}")
            print("-" * 85)
            for env_var, value, source in env_vars_info:
                # Truncate long values for display (max 34 chars)
                display_value = value if len(value) <= 34 else value[:31] + "..."
                # Use source as-is (already descriptive)
                display_source = source
                print(f"{env_var:<25} {display_value:<34} {display_source:<19}")
            print("=" * 85)
        
        if not settings.project_id:
            print(f"   ✅ No project ID - using local configuration")
        
        # Set up secrets environment
        _setup_secrets_environment(settings, env_name)
        
        if settings.project_id:
            pass  # Secrets loaded from Secret Manager
        elif settings.local:
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
        api_in_memory = settings.api_in_memory
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
    
    project_id = settings.project_id
    is_local = settings.local
    
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
        setting_value = getattr(settings, key, None)
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
