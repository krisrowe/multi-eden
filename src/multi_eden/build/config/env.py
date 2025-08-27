"""
Environment variable loading for build/deploy operations.

This module loads configuration from JSON files and sets environment variables
during build/deploy/startup operations. It does not fail if settings are missing.
"""
import os
from pathlib import Path
from typing import Optional

from .secrets import load_secrets_from_env
from .providers import load_providers_from_env
from .host import load_host_from_env


def load_env(env_name: str, repo_root: Path = None) -> None:
    """Load configuration from JSON files and set environment variables.
    
    This function reads configuration files and sets environment variables.
    It fails fast if configuration files are missing or invalid.
    
    Args:
        env_name: Environment name (e.g., 'dev', 'prod', 'unit-testing')
        repo_root: Repository root path, defaults to current working directory
        
    Raises:
        FileNotFoundError: If required configuration files are missing
        json.JSONDecodeError: If configuration files contain invalid JSON
        ValueError: If configuration data is invalid
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    print(f"🔧 Loading environment configuration for: {env_name}")
    
    # Load provider configuration
    provider_config = load_providers_from_env(env_name, repo_root)
    
    # Set provider-related environment variables
    os.environ.setdefault('STUB_AI', str(provider_config.ai_provider == 'mocked').lower())
    os.environ.setdefault('STUB_DB', str(provider_config.data_provider == 'tinydb').lower())
    
    # Handle auth provider configuration
    if 'custom' in provider_config.auth_provider:
        os.environ.setdefault('CUSTOM_AUTH_ENABLED', 'true')
    else:
        os.environ.setdefault('CUSTOM_AUTH_ENABLED', 'false')
        
    print(f"   ✅ Providers loaded: AI={provider_config.ai_provider}, DB={provider_config.data_provider}, Auth={provider_config.auth_provider}")
    
    # Load host configuration (optional)
    try:
        host_config = load_host_from_env(env_name, repo_root)
        
        # Set host-related environment variables
        if host_config.project_id:
            os.environ.setdefault('CLOUD_PROJECT_ID', host_config.project_id)
            print(f"   ✅ Project ID set: {host_config.project_id}")
        
        if host_config.api_url:
            os.environ.setdefault('API_URL', host_config.api_url)
            print(f"   ✅ API URL set: {host_config.api_url}")
    except FileNotFoundError:
        print(f"   ⚠️  Host configuration not found (optional)")
    except Exception as e:
        print(f"   ⚠️  Host configuration error: {e}")
    
    # Load secrets configuration (optional)
    try:
        secrets_config = load_secrets_from_env(env_name, repo_root)
        
        # Set secrets-related environment variables
        if secrets_config.salt:
            os.environ.setdefault('CUSTOM_AUTH_SALT', secrets_config.salt)
            print(f"   ✅ Custom auth salt set")
        
        if secrets_config.google_api_key:
            os.environ.setdefault('GEMINI_API_KEY', secrets_config.google_api_key)
            print(f"   ✅ Gemini API key set")
        
        # Set authorization environment variables
        os.environ.setdefault('ALL_AUTHENTICATED_USERS', str(secrets_config.authorization.all_authenticated_users).lower())
        
        if secrets_config.authorization.allowed_user_emails:
            allowed_emails = ','.join(secrets_config.authorization.allowed_user_emails)
            os.environ.setdefault('ALLOWED_USER_EMAILS', allowed_emails)
            print(f"   ✅ Authorization settings loaded")
    except FileNotFoundError:
        print(f"   ⚠️  Secrets configuration not found (optional)")
    except Exception as e:
        print(f"   ⚠️  Secrets configuration error: {e}")
    
    print(f"🔧 Environment configuration loading complete")
