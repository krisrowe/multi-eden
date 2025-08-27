"""
Host configuration loading for build/deploy operations.

This module loads host configuration from JSON files during build/deploy/startup operations
and is separate from the runtime config that uses environment variables.
"""
import json
from pathlib import Path
from typing import Dict, Any

from .models import HostConfig


def load_host_from_file(host_path: Path) -> HostConfig:
    """Load host configuration from a JSON file.
    
    Args:
        host_path: Path to the host.json file
        
    Returns:
        HostConfig instance
        
    Raises:
        FileNotFoundError: If host file doesn't exist
        json.JSONDecodeError: If host file is invalid JSON
    """
    if not host_path.exists():
        raise FileNotFoundError(f"Host file not found: {host_path}")
    
    with open(host_path, 'r') as f:
        config_dict = json.load(f)
    
    return HostConfig.from_dict(config_dict)


def load_host_from_env(env_name: str, repo_root: Path = None) -> HostConfig:
    """Load host configuration from environment-specific host.json file.
    
    Args:
        env_name: Environment name (e.g., 'dev', 'prod', 'unit-testing')
        repo_root: Repository root path, defaults to current working directory
        
    Returns:
        HostConfig instance
        
    Raises:
        FileNotFoundError: If host file doesn't exist
        json.JSONDecodeError: If host file is invalid JSON
    """
    if repo_root is None:
        repo_root = Path.cwd()
    
    host_path = repo_root / 'config' / 'settings' / env_name / 'host.json'
    return load_host_from_file(host_path)


