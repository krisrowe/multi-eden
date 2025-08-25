"""
Multi-Environment SDK Environment Creation Module

Provides functionality to create new environment configurations with secure defaults.
"""

import json
import os
from pathlib import Path
from invoke import task
from typing import Optional

from multi_eden.run.auth.util import gen_jwt_key


class CreateConfigEnvError(Exception):
    """Base exception for environment creation errors."""
    pass


class EnvironmentExistsError(CreateConfigEnvError):
    """Raised when the environment already exists."""
    pass


class InvalidEnvironmentNameError(CreateConfigEnvError):
    """Raised when the environment name is invalid."""
    pass


@task
def config_env_create(ctx, env_name: str, project_id: Optional[str] = None) -> None:
    """
    Create a new environment configuration with secure defaults.
    
    This task creates the necessary configuration files for a new environment:
    - config/secrets/{env_name}/secrets.json with a secure JWT key
    - config/settings/{env_name}/providers.json with default provider settings
    - config/settings/{env_name}/values.json with environment-specific values
    
    Args:
        env_name: Name of the environment to create (e.g., 'staging', 'qa')
        project_id: Optional GCP project ID for this environment
        
    Raises:
        InvalidEnvironmentNameError: When environment name is invalid
        EnvironmentExistsError: When environment already exists
        CreateConfigEnvError: When creation fails
    """
    
    # Validate environment name
    if not env_name or not env_name.strip():
        raise InvalidEnvironmentNameError("Environment name cannot be empty")
    
    env_name = env_name.strip().lower()
    
    # Check for invalid characters
    if not env_name.replace('-', '').replace('_', '').isalnum():
        raise InvalidEnvironmentNameError("Environment name can only contain letters, numbers, hyphens, and underscores")
    
    # Get repository root
    repo_root = Path.cwd()
    config_dir = repo_root / "config"
    
    if not config_dir.exists():
        raise CreateConfigEnvError(f"Config directory not found at {config_dir}")
    
    # Check if environment already exists
    secrets_dir = config_dir / "secrets" / env_name
    settings_dir = config_dir / "settings" / env_name
    
    if secrets_dir.exists() or settings_dir.exists():
        raise EnvironmentExistsError(
            f"Environment '{env_name}' already exists. "
            f"Secrets dir: {secrets_dir.exists()}, Settings dir: {settings_dir.exists()}"
        )
    
    print(f"🔧 Creating environment configuration for '{env_name}'...")
    
    try:
        # Create directories
        secrets_dir.mkdir(parents=True, exist_ok=True)
        settings_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate secure JWT key
        jwt_key = gen_jwt_key()
        print(f"   🔑 Generated secure JWT key: {jwt_key[:8]}...")
        
        # Create secrets.json
        secrets_file = secrets_dir / "secrets.json"
        secrets_config = {
            "salt": jwt_key,
            "google_api_key": "REPLACE_WITH_GEMINI_API_KEY",
            "authorization": {
                "all_authenticated_users": True,
                "allowed_user_emails": []
            }
        }
        
        with open(secrets_file, 'w') as f:
            json.dump(secrets_config, f, indent=2)
        print(f"   ✅ Created {secrets_file}")
        
        # Create providers.json
        providers_file = settings_dir / "providers.json"
        providers_config = {
            "auth": {
                "provider": "custom",
                "custom_auth_enabled": True
            },
            "data": {
                "provider": "tinydb",
                "use_in_memory_db": True
            },
            "ai": {
                "provider": "gemini",
                "ai_model_mocked": True
            },
            "api": {
                "in_memory_api": True
            }
        }
        
        with open(providers_file, 'w') as f:
            json.dump(providers_config, f, indent=2)
        print(f"   ✅ Created {providers_file}")
        
        # Create values.json
        values_file = settings_dir / "values.json"
        values_config = {
            "project_id": project_id or "REPLACE_WITH_PROJECT_ID",
            "environment": env_name,
            "logging": {
                "level": "INFO"
            }
        }
        
        with open(values_file, 'w') as f:
            json.dump(values_config, f, indent=2)
        print(f"   ✅ Created {values_file}")
        
        print(f"   🎯 Environment '{env_name}' configuration created successfully!")
        print(f"   📁 Secrets: {secrets_file}")
        print(f"   📁 Providers: {providers_file}")
        print(f"   📁 Values: {values_file}")
        print(f"   🔑 JWT Key: {jwt_key[:8]}... (stored in secrets.json)")
        
        if not project_id:
            print(f"   ⚠️  Remember to update the project_id in {values_file}")
        
        print(f"   ⚠️  Remember to update the google_api_key in {secrets_file}")
        
    except Exception as e:
        # Clean up on failure
        if secrets_dir.exists():
            import shutil
            shutil.rmtree(secrets_dir)
        if settings_dir.exists():
            import shutil
            shutil.rmtree(settings_dir)
        
        raise CreateConfigEnvError(f"Failed to create environment '{env_name}': {e}")


@task
def config_env_list(ctx) -> None:
    """
    List all available environments in the config directory.
    """
    repo_root = Path.cwd()
    config_dir = repo_root / "config"
    
    if not config_dir.exists():
        print("❌ Config directory not found")
        return
    
    secrets_dir = config_dir / "secrets"
    settings_dir = config_dir / "settings"
    
    environments = set()
    
    # Check secrets directory
    if secrets_dir.exists():
        for env_dir in secrets_dir.iterdir():
            if env_dir.is_dir() and (env_dir / "secrets.json").exists():
                environments.add(env_dir.name)
    
    # Check settings directory
    if settings_dir.exists():
        for env_dir in settings_dir.iterdir():
            if env_dir.is_dir() and (env_dir / "providers.json").exists():
                environments.add(env_dir.name)
    
    if not environments:
        print("📁 No environments found")
        return
    
    print("🔧 Available environments:")
    for env in sorted(environments):
        print(f"   • {env}")
