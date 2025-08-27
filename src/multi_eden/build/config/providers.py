"""
Provider configuration loading for build/deploy operations.

This module loads provider configuration from JSON files during build/deploy/startup operations
and is separate from the runtime config that uses environment variables.
"""
import json
from pathlib import Path
from typing import Dict, Any

from .models import ProviderConfig


def load_providers_from_file(providers_path: Path) -> ProviderConfig:
    """Load provider configuration from a JSON file.
    
    Args:
        providers_path: Path to the providers.json file
        
    Returns:
        ProviderConfig instance
        
    Raises:
        FileNotFoundError: If providers file doesn't exist
        json.JSONDecodeError: If providers file is invalid JSON
    """
    if not providers_path.exists():
        raise FileNotFoundError(f"Providers file not found: {providers_path}")
    
    with open(providers_path, 'r') as f:
        config_dict = json.load(f)
    
    return ProviderConfig.from_dict(config_dict)


def load_providers_from_env(env_name: str, repo_root: Path = None) -> ProviderConfig:
    """Load provider configuration from environment-specific providers.json file.
    
    Args:
        env_name: Environment name (e.g., 'dev', 'prod', 'unit-testing')
        repo_root: Repository root path, defaults to current working directory
        
    Returns:
        ProviderConfig instance
        
    Raises:
        FileNotFoundError: If providers file doesn't exist
        json.JSONDecodeError: If providers file is invalid JSON
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    providers_path = repo_root / 'config' / 'settings' / env_name / 'providers.json'
    return load_providers_from_file(providers_path)


