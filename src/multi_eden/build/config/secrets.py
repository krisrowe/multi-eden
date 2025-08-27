"""
Secrets configuration for build/deploy operations.

This module loads secrets from JSON files during build/deploy/startup operations
and is separate from the runtime config that uses environment variables.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, List

from .models import SecretsConfig, Authorization


def load_secrets_from_file(secrets_path: Path) -> SecretsConfig:
    """Load secrets from a JSON file.
    
    Args:
        secrets_path: Path to the secrets.json file
        
    Returns:
        SecretsConfig instance
        
    Raises:
        FileNotFoundError: If secrets file doesn't exist
        json.JSONDecodeError: If secrets file is invalid JSON
        ValueError: If secrets file is missing required fields
    """
    if not secrets_path.exists():
        raise FileNotFoundError(f"Secrets file not found: {secrets_path}")
    
    with open(secrets_path, 'r') as f:
        config_dict = json.load(f)
    
    return SecretsConfig.from_dict(config_dict)


def load_secrets_from_env(env_name: str, repo_root: Path = None) -> SecretsConfig:
    """Load secrets from environment-specific secrets.json file.
    
    Args:
        env_name: Environment name (e.g., 'dev', 'prod', 'unit-testing')
        repo_root: Repository root path, defaults to current working directory
        
    Returns:
        SecretsConfig instance
        
    Raises:
        FileNotFoundError: If secrets file doesn't exist
        json.JSONDecodeError: If secrets file is invalid JSON
        ValueError: If secrets file is missing required fields
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    secrets_path = repo_root / 'config' / 'secrets' / env_name / 'secrets.json'
    return load_secrets_from_file(secrets_path)
